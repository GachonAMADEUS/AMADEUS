from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from mesh_pipeline import (
    DEFAULT_FLOATING_BED_TOLERANCE,
    DEFAULT_SIMPLIFY_THRESHOLD,
    DEFAULT_TARGET_TRIANGLES,
    inspect_stl,
    load_mesh,
    process_stl,
    resolve_floating_regions,
)
from scale_from_ply import (
    DEFAULT_RESOLUTION,
    DEFAULT_SQUARE_REAL_SIZE_MM,
    compute_scale_factor_from_ply,
)
from slicer import slice_with_orca_legacy_cli_safe


DEFAULT_BAMBU_X1C_BED_LIMIT_MM = (256.0, 256.0, 250.0)


def _as_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def _require_file(path: str | Path, label: str) -> Path:
    file_path = _as_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"{label} not found: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {file_path}")
    return file_path


def _write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    output_file = _as_path(path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_file


def _extents_exceed_bed(
    extents: list[float],
    bed_limit_mm: tuple[float, float, float],
) -> bool:
    return any(float(value) > float(limit) for value, limit in zip(extents, bed_limit_mm))


def _format_extents(extents: list[float]) -> str:
    return " x ".join(f"{float(value):.3f}" for value in extents)


def inspect_stl_with_geometry(path: str | Path) -> dict[str, Any]:
    report = inspect_stl(path)
    mesh = load_mesh(path)
    bounds = mesh.bounds.tolist()
    report["bounds"] = bounds
    report["extents"] = [
        float(bounds[1][axis]) - float(bounds[0][axis])
        for axis in range(3)
    ]
    return report


def apply_scale_to_stl(
    input_stl: str | Path,
    output_stl: str | Path,
    scale_factor: float,
) -> dict[str, Any]:
    input_file = _require_file(input_stl, "Input STL")
    output_file = _as_path(output_stl)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    mesh = load_mesh(input_file)
    before_bounds = mesh.bounds.tolist()
    mesh.apply_scale(float(scale_factor))
    mesh.export(output_file)

    return {
        "input_file": str(input_file),
        "output_file": str(output_file),
        "scale_factor": float(scale_factor),
        "before_bounds": before_bounds,
        "after": inspect_stl_with_geometry(output_file),
    }


def finalize_print_pipeline(
    input_stl: str | Path,
    scale_ply: str | Path,
    output_dir: str | Path,
    video_name: str,
    square_real_size_mm: float = DEFAULT_SQUARE_REAL_SIZE_MM,
    scale_resolution: int = DEFAULT_RESOLUTION,
    simplify_threshold: int = DEFAULT_SIMPLIFY_THRESHOLD,
    target_triangles: int = DEFAULT_TARGET_TRIANGLES,
    floating_bed_tolerance: float = DEFAULT_FLOATING_BED_TOLERANCE,
    slicer_timeout_seconds: int = 900,
    skip_slicing: bool = False,
) -> dict[str, Any]:
    input_file = _require_file(input_stl, "Postprocessed STL")
    scale_file = _require_file(scale_ply, "Scale PLY")
    root = _as_path(output_dir)
    mesh_dir = root / "mesh"
    scale_dir = root / "scale"
    slicer_dir = root / "slicer"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    scale_dir.mkdir(parents=True, exist_ok=True)
    slicer_dir.mkdir(parents=True, exist_ok=True)

    copied_input_stl = mesh_dir / f"{video_name}_postprocessed_input.stl"
    if input_file.resolve() != copied_input_stl.resolve():
        shutil.copy2(input_file, copied_input_stl)

    print("[Step 3-3a] STL repair/simplify/floating cleanup")
    processed = process_stl(
        copied_input_stl,
        mesh_dir,
        simplify_threshold=int(simplify_threshold),
        target_triangles=int(target_triangles),
        floating_bed_tolerance=float(floating_bed_tolerance),
    )

    print("[Step 3-3b] checkerboard scale factor 계산")
    scale_report = compute_scale_factor_from_ply(
        scale_file,
        output_dir=scale_dir,
        resolution=int(scale_resolution),
        square_real_size_mm=float(square_real_size_mm),
    )
    scale_factor = float(scale_report["scale_factor"])

    scaled_raw_stl = mesh_dir / f"{video_name}_scaled_raw.stl"
    print("[Step 3-3c] STL scale 적용")
    scale_apply_report = apply_scale_to_stl(
        processed["final_file"],
        scaled_raw_stl,
        scale_factor,
    )

    scaled_final_stl = mesh_dir / f"{video_name}_scaled_final.stl"
    print("[Step 3-3d] scaled STL floating cleanup")
    scaled_floating = resolve_floating_regions(
        scaled_raw_stl,
        scaled_final_stl,
        bed_tolerance=float(floating_bed_tolerance),
    )
    scaled_final_report = inspect_stl_with_geometry(scaled_final_stl)
    support_recommended = bool(
        processed.get("support_recommended", False)
        or scaled_floating.get("support_recommended", False)
    )

    slice_report: dict[str, Any] | None = None
    sliced_3mf = root / f"{video_name}_sliced.3mf"
    scaled_extents = [
        float(value)
        for value in scaled_final_report.get("extents", [])
    ]
    bed_limit_mm = DEFAULT_BAMBU_X1C_BED_LIMIT_MM
    slicing_blocked_reason = None

    manifest = {
        "video_name": video_name,
        "input_stl": str(input_file),
        "copied_input_stl": str(copied_input_stl),
        "scale_ply": str(scale_file),
        "output_dir": str(root),
        "processed": processed,
        "scale_report": scale_report,
        "scale_apply": scale_apply_report,
        "scaled_floating": scaled_floating,
        "scaled_final_report": scaled_final_report,
        "scaled_extents_mm": scaled_extents,
        "bed_limit_mm": list(bed_limit_mm),
        "slicing_blocked_reason": slicing_blocked_reason,
        "support_recommended": support_recommended,
        "scaled_final_stl": str(scaled_final_stl),
        "sliced_3mf": None,
        "slice_report": None,
    }

    if scaled_extents and _extents_exceed_bed(scaled_extents, bed_limit_mm):
        slicing_blocked_reason = (
            "Scaled STL exceeds Bambu X1C build volume. "
            f"scaled_extents_mm={_format_extents(scaled_extents)}, "
            f"bed_limit_mm={_format_extents(list(bed_limit_mm))}. "
            "This indicates a scale or coordinate-system issue; automatic downscaling is disabled."
        )
        manifest["slicing_blocked_reason"] = slicing_blocked_reason
        _write_json(root / "pipeline_manifest.json", manifest)
        if skip_slicing:
            print(f"[Warn] {slicing_blocked_reason}")
        else:
            raise RuntimeError(slicing_blocked_reason)

    if skip_slicing:
        print("[Step 3-3e] slicing skipped")
    else:
        print("[Step 3-3e] Orca legacy slicing")
        slice_report = slice_with_orca_legacy_cli_safe(
            input_stl=scaled_final_stl,
            output_3mf=sliced_3mf,
            safe_profile_dir=slicer_dir / "cli_safe_profiles_orca_legacy",
            enable_support=support_recommended,
            timeout_seconds=int(slicer_timeout_seconds),
        )
        manifest["sliced_3mf"] = str(sliced_3mf)
        manifest["slice_report"] = slice_report

    manifest_path = _write_json(root / "pipeline_manifest.json", manifest)
    manifest["manifest_file"] = str(manifest_path)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize 2DGS foot STL into real-scale printable STL and sliced 3MF."
    )
    parser.add_argument("--input-stl", required=True)
    parser.add_argument("--scale-ply", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--video-name", required=True)
    parser.add_argument("--square-real-size-mm", type=float, default=DEFAULT_SQUARE_REAL_SIZE_MM)
    parser.add_argument("--scale-resolution", type=int, default=DEFAULT_RESOLUTION)
    parser.add_argument("--simplify-threshold", type=int, default=DEFAULT_SIMPLIFY_THRESHOLD)
    parser.add_argument("--target-triangles", type=int, default=DEFAULT_TARGET_TRIANGLES)
    parser.add_argument("--floating-bed-tolerance", type=float, default=DEFAULT_FLOATING_BED_TOLERANCE)
    parser.add_argument("--slicer-timeout-seconds", type=int, default=900)
    parser.add_argument("--skip-slicing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    finalize_print_pipeline(
        input_stl=args.input_stl,
        scale_ply=args.scale_ply,
        output_dir=args.output_dir,
        video_name=args.video_name,
        square_real_size_mm=args.square_real_size_mm,
        scale_resolution=args.scale_resolution,
        simplify_threshold=args.simplify_threshold,
        target_triangles=args.target_triangles,
        floating_bed_tolerance=args.floating_bed_tolerance,
        slicer_timeout_seconds=args.slicer_timeout_seconds,
        skip_slicing=args.skip_slicing,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
