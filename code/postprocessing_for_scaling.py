from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import trimesh


def _as_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def _require_file(path: str | Path) -> Path:
    file_path = _as_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input PLY not found: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(f"Input path is not a file: {file_path}")
    return file_path


def _load_vertices_and_colors(input_path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    loaded = trimesh.load(input_path, process=False)
    if isinstance(loaded, trimesh.Scene):
        geometries = list(loaded.geometry.values())
        if not geometries:
            raise ValueError(f"No geometry found in PLY scene: {input_path}")
        loaded = trimesh.util.concatenate(geometries)

    vertices = np.asarray(getattr(loaded, "vertices", None))
    if vertices.size == 0:
        raise ValueError(f"PLY has no vertices: {input_path}")

    colors = None
    visual = getattr(loaded, "visual", None)
    if visual is not None and hasattr(visual, "vertex_colors"):
        raw_colors = np.asarray(visual.vertex_colors)
        if len(raw_colors) == len(vertices):
            colors = raw_colors

    return vertices, colors


def process_gaussian_ply(
    input_path: str | Path,
    output_path: str | Path,
    z_min: float = -0.1,
    z_max: float = 0.01,
) -> dict[str, Any]:
    input_file = _require_file(input_path)
    output_file = _as_path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"[scale-ply] input: {input_file}")
    vertices, colors = _load_vertices_and_colors(input_file)
    print(f"[scale-ply] original points: {len(vertices)}")

    z_mask = (vertices[:, 2] >= float(z_min)) & (vertices[:, 2] <= float(z_max))
    filtered_vertices = vertices[z_mask]
    filtered_colors = colors[z_mask] if colors is not None else None

    if len(filtered_vertices) == 0:
        raise ValueError(
            "Z filtering removed every point. "
            f"input={input_file}, z_min={z_min}, z_max={z_max}"
        )

    export_pc = trimesh.points.PointCloud(
        vertices=filtered_vertices,
        colors=filtered_colors,
    )
    export_pc.export(output_file)

    report = {
        "input_file": str(input_file),
        "output_file": str(output_file),
        "z_min": float(z_min),
        "z_max": float(z_max),
        "original_point_count": int(len(vertices)),
        "filtered_point_count": int(len(filtered_vertices)),
        "has_colors": bool(filtered_colors is not None),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a checkerboard/scale PLY from a 2DGS Gaussian PLY by Z range."
    )
    parser.add_argument("--input", required=True, help="Input 2DGS PLY path.")
    parser.add_argument("--output", required=True, help="Output filtered scale PLY path.")
    parser.add_argument("--z-min", type=float, default=-0.1)
    parser.add_argument("--z-max", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    process_gaussian_ply(
        input_path=args.input,
        output_path=args.output,
        z_min=args.z_min,
        z_max=args.z_max,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
