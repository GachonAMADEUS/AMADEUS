import argparse
import shutil
import subprocess
from pathlib import Path


REQUIRED_MODEL_FILES = ("cameras.bin", "images.bin", "points3D.bin")


def has_colmap_model(path: Path) -> bool:
    return path.is_dir() and all((path / name).exists() for name in REQUIRED_MODEL_FILES)


def default_output_path(input_path: Path) -> Path:
    if input_path.name == "0" and input_path.parent.name == "sparse":
        return input_path.parent.parent / "undistorted"
    return input_path.parent / "undistorted"


def backup_candidates(input_path: Path) -> list[Path]:
    candidates = [Path(str(input_path).rstrip("/\\")).with_name(input_path.name + "_backup")]

    if input_path.name == "0" and input_path.parent.name == "sparse":
        candidates.append(input_path.parent.parent / "sparse_backup" / "0")

    return candidates


def select_input_model(input_path: Path) -> Path:
    for candidate in backup_candidates(input_path):
        if has_colmap_model(candidate):
            print(f">>> Using sparse backup: {candidate}")
            return candidate

    if has_colmap_model(input_path):
        print(f">>> Using sparse input: {input_path}")
        return input_path

    checked = "\n".join(f"  - {path}" for path in [input_path, *backup_candidates(input_path)])
    raise FileNotFoundError(
        "No valid COLMAP sparse model found. Checked:\n"
        f"{checked}\n"
        f"Required files: {', '.join(REQUIRED_MODEL_FILES)}"
    )


def prepare_output_path(output_path: Path, overwrite: bool) -> None:
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        return

    if not overwrite:
        raise FileExistsError(
            f"Output path already exists: {output_path}\n"
            "Pass --overwrite to replace it."
        )

    backup_path = Path(str(output_path).rstrip("/\\") + "_backup")
    if not backup_path.exists():
        print(f">>> Creating output backup: {backup_path}")
        shutil.copytree(output_path, backup_path)
    else:
        print(f">>> Output backup already exists: {backup_path}")

    print(f">>> Clearing output path: {output_path}")
    shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)


def find_undistorted_sparse(output_path: Path) -> Path:
    candidates = [output_path / "sparse", output_path / "sparse" / "0"]
    for candidate in candidates:
        if has_colmap_model(candidate):
            return candidate

    checked = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        "COLMAP undistortion finished, but no undistorted sparse model was found. Checked:\n"
        f"{checked}"
    )


def ensure_sparse_zero_layout(output_path: Path) -> Path:
    sparse_path = output_path / "sparse"
    sparse_zero_path = sparse_path / "0"

    if has_colmap_model(sparse_zero_path):
        return sparse_zero_path

    if not has_colmap_model(sparse_path):
        return find_undistorted_sparse(output_path)

    print(f">>> Normalizing sparse layout for 2DGS: {sparse_path} -> {sparse_zero_path}")
    sparse_zero_path.mkdir(parents=True, exist_ok=True)
    for item in sparse_path.iterdir():
        if item == sparse_zero_path:
            continue
        shutil.move(str(item), str(sparse_zero_path / item.name))

    return sparse_zero_path


def run_image_undistorter(image_path: Path, input_path: Path, output_path: Path, copy_policy: str) -> None:
    cmd = [
        "colmap",
        "image_undistorter",
        "--image_path",
        str(image_path),
        "--input_path",
        str(input_path),
        "--output_path",
        str(output_path),
        "--output_type",
        "COLMAP",
        "--copy_policy",
        copy_policy,
    ]

    print(">>> Running COLMAP image_undistorter...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Undistort a COLMAP sparse model before auto alignment / 2DGS training."
    )
    parser.add_argument(
        "--input_path",
        required=True,
        type=Path,
        help="Path to COLMAP sparse folder, e.g. colmap_work_xxx/sparse/0.",
    )
    parser.add_argument(
        "--image_path",
        default=Path("colmap/input"),
        type=Path,
        help="Path to original images used by COLMAP.",
    )
    parser.add_argument(
        "--output_path",
        default=None,
        type=Path,
        help="Output folder for undistorted COLMAP dataset. Default: <work_dir>/undistorted.",
    )
    parser.add_argument(
        "--copy_policy",
        default="copy",
        choices=("copy", "soft-link", "hard-link"),
        help="How COLMAP should place undistorted images in the output folder.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output folder after creating <output_path>_backup once.",
    )
    args = parser.parse_args()

    input_path = args.input_path.resolve()
    image_path = args.image_path.resolve()
    output_path = (args.output_path.resolve() if args.output_path else default_output_path(input_path).resolve())

    if not image_path.is_dir():
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    selected_input = select_input_model(input_path)
    prepare_output_path(output_path, overwrite=args.overwrite)
    run_image_undistorter(image_path, selected_input, output_path, args.copy_policy)

    undistorted_sparse = ensure_sparse_zero_layout(output_path)
    print(">>> Undistortion complete.")
    print(f">>> Undistorted images: {output_path / 'images'}")
    print(f">>> Sparse for auto_align_colmap.py: {undistorted_sparse}")


if __name__ == "__main__":
    main()
