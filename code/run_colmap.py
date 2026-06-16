import subprocess
from pathlib import Path
import sys
import argparse


# ============================================================
# 설정
# ============================================================

USE_XVFB = True  # xvfb-run 사용 여부. 필요 없으면 False로 변경.

BASE_DIR = Path(".").resolve()

DATABASE_PATH = BASE_DIR / "colmap_work_tmp" / "database.db"
IMAGE_PATH = BASE_DIR / "colmap" / "input"
IMAGE_LIST_PATH = BASE_DIR / "colmap_work_tmp" / "image_list.txt"
SPARSE_OUTPUT_PATH = BASE_DIR / "colmap_work_tmp" / "sparse"
VOCAB_TREE_PATH = BASE_DIR / "vocab_tree_flickr100K_words32K.bin"

import shutil

RESET_WORKSPACE = True  # 처음부터 다시 돌릴 때 True
MATCHER_TYPE = "sequential"  # 기본 matcher. CLI의 --exhaustive가 우선한다.
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]


def reset_workspace():
    if not RESET_WORKSPACE:
        print("[초기화 건너뜀] 기존 database/sparse 유지")
        return

    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        print(f"[삭제 완료] {DATABASE_PATH}")

    if SPARSE_OUTPUT_PATH.exists():
        shutil.rmtree(SPARSE_OUTPUT_PATH)
        print(f"[삭제 완료] {SPARSE_OUTPUT_PATH}")

    SPARSE_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    print(f"[폴더 생성 완료] {SPARSE_OUTPUT_PATH}")


def get_top_level_image_files():
    """
    COLMAP 입력 폴더 바로 아래의 이미지 파일만 사용한다.
    yolo_seg 같은 확인용 하위 폴더가 섞이면 reconstruction이 불안정해지고 매우 느려진다.
    """

    return sorted(
        [
            p for p in IMAGE_PATH.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda p: p.name,
    )


def write_image_list(image_files):
    """
    COLMAP image_list_path에 들어갈 파일명을 생성한다.
    image_path 기준 상대 경로를 넣어야 하며, 여기서는 top-level 파일명만 기록한다.
    """

    IMAGE_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_LIST_PATH.write_text(
        "\n".join(p.name for p in image_files) + "\n",
        encoding="utf-8",
    )
    print(f"[이미지 목록 생성] {IMAGE_LIST_PATH} ({len(image_files)}장)")

def get_colmap_help(command_name):
    result = subprocess.run(
        ["colmap", command_name, "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.stdout + result.stderr


def pick_gpu_option(command_name, old_option, new_option):
    """
    현재 COLMAP 명령어가 지원하는 GPU 옵션명을 자동으로 선택한다.
    old_option 예: --SiftExtraction.use_gpu
    new_option 예: --FeatureExtraction.use_gpu
    """

    help_text = get_colmap_help(command_name)

    if new_option in help_text:
        print(f"[옵션 감지] {command_name}: {new_option} 사용")
        return new_option

    if old_option in help_text:
        print(f"[옵션 감지] {command_name}: {old_option} 사용")
        return old_option

    print(f"[옵션 감지] {command_name}: GPU 옵션을 찾지 못했습니다. GPU 옵션 없이 실행합니다.")
    return None

# ============================================================
# 공통 실행 함수
# ============================================================

def run_command(cmd, use_xvfb=False):
    """
    COLMAP 명령어를 실행한다.
    실패하면 RuntimeError를 발생시켜 파이프라인을 중단한다.
    """

    cmd = list(map(str, cmd))

    if use_xvfb:
        cmd = ["xvfb-run", "-a"] + cmd

    print("\n" + "=" * 80)
    print("[실행 명령어]")
    print(" ".join(cmd))
    print("=" * 80)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    returncode = process.wait()

    if returncode != 0:
        raise RuntimeError(
            f"명령어 실행 실패, return code={returncode}\n"
            f"{' '.join(cmd)}"
        )


# ============================================================
# 사전 경로 확인
# ============================================================

def check_inputs():
    """
    입력 경로와 vocab tree 파일 존재 여부를 확인한다.
    """

    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"이미지 폴더가 없습니다: {IMAGE_PATH}")

    image_files = get_top_level_image_files()

    if len(image_files) == 0:
        raise FileNotFoundError(f"이미지 폴더에 이미지 파일이 없습니다: {IMAGE_PATH}")

    if not VOCAB_TREE_PATH.exists():
        raise FileNotFoundError(f"vocab tree 파일이 없습니다: {VOCAB_TREE_PATH}")

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPARSE_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    write_image_list(image_files)

    print("[입력 확인 완료]")
    print(f"BASE_DIR          : {BASE_DIR}")
    print(f"DATABASE_PATH     : {DATABASE_PATH}")
    print(f"IMAGE_PATH        : {IMAGE_PATH}")
    print(f"IMAGE_COUNT       : {len(image_files)}")
    print(f"IMAGE_LIST_PATH   : {IMAGE_LIST_PATH}")
    print(f"SPARSE_OUTPUT_PATH: {SPARSE_OUTPUT_PATH}")
    print(f"VOCAB_TREE_PATH   : {VOCAB_TREE_PATH}")


# ============================================================
# 1. Feature Extraction
# ============================================================

def feature_extraction(strong=False):
    cmd = [
        "colmap", "feature_extractor",
        "--database_path", DATABASE_PATH,
        "--image_path", IMAGE_PATH,
        "--image_list_path", IMAGE_LIST_PATH,
        "--ImageReader.camera_model", "SIMPLE_RADIAL",
        "--ImageReader.single_camera", "1",
    ]

    if strong:
        cmd += [
            "--SiftExtraction.max_num_features", "20000",
            "--SiftExtraction.peak_threshold", "0.003",
            "--SiftExtraction.edge_threshold", "10",
        ]

    gpu_option = pick_gpu_option(
        command_name="feature_extractor",
        old_option="--SiftExtraction.use_gpu",
        new_option="--FeatureExtraction.use_gpu",
    )

    if gpu_option is not None:
        cmd += [gpu_option, "1"]

    run_command(cmd, use_xvfb=USE_XVFB)


# =====================
# 3. Exhaustive Matcher
# =====================

def exhaustive_matcher():
    cmd = [
        "colmap", "exhaustive_matcher",
        "--database_path", DATABASE_PATH,
    ]

    gpu_option = pick_gpu_option(
        command_name="exhaustive_matcher",
        old_option="--SiftMatching.use_gpu",
        new_option="--FeatureMatching.use_gpu",
    )

    if gpu_option is not None:
        cmd += [gpu_option, "1"]

    run_command(cmd, use_xvfb=USE_XVFB)

# ============================================================
# 2. Sequential Matcher
# ============================================================

def sequential_matcher():
    cmd = [
        "colmap", "sequential_matcher",
        "--database_path", DATABASE_PATH,
        "--SequentialMatching.overlap", "20", # 45까지 했음
        "--SequentialMatching.loop_detection", "1",
        # "--SequentialMatching.vocab_tree_path", VOCAB_TREE_PATH,
    ]

    gpu_option = pick_gpu_option(
        command_name="sequential_matcher",
        old_option="--SiftMatching.use_gpu",
        new_option="--FeatureMatching.use_gpu",
    )

    if gpu_option is not None:
        cmd += [gpu_option, "1"]

    run_command(cmd, use_xvfb=USE_XVFB)


# ============================================================
# 3. Sparse 결과 폴더 생성
# ============================================================

def make_sparse_folder():
    SPARSE_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    print(f"\n[폴더 생성 완료] {SPARSE_OUTPUT_PATH}")


# ============================================================
# 4. Mapper
# ============================================================

def mapper():
    cmd = [
        "colmap", "mapper",
        "--database_path", DATABASE_PATH,
        "--image_path", IMAGE_PATH,
        "--output_path", SPARSE_OUTPUT_PATH,
        "--Mapper.ba_use_gpu", "1",
        "--Mapper.multiple_models", "0",
    ]

    run_command(cmd, use_xvfb=False)


# ============================================================
# 5. 결과 확인
# ============================================================

def check_sparse_result():
    """
    COLMAP mapper 결과를 확인한다.
    일반적으로 sparse/0 안에 cameras.bin, images.bin, points3D.bin이 생성된다.
    """

    print("\n" + "=" * 80)
    print("[COLMAP 결과 확인]")
    print("=" * 80)

    if not SPARSE_OUTPUT_PATH.exists():
        raise FileNotFoundError(f"sparse 결과 폴더가 없습니다: {SPARSE_OUTPUT_PATH}")

    reconstruction_dirs = [
        p for p in SPARSE_OUTPUT_PATH.iterdir()
        if p.is_dir()
    ]

    if len(reconstruction_dirs) == 0:
        raise FileNotFoundError(
            f"mapper 결과 reconstruction 폴더가 없습니다: {SPARSE_OUTPUT_PATH}\n"
            "보통 sparse/0 폴더가 생성되어야 합니다."
        )

    valid_results = []

    for recon_dir in reconstruction_dirs:
        cameras_file = recon_dir / "cameras.bin"
        images_file = recon_dir / "images.bin"
        points3d_file = recon_dir / "points3D.bin"

        if cameras_file.exists() and images_file.exists() and points3d_file.exists():
            valid_results.append(recon_dir)

    if len(valid_results) == 0:
        raise FileNotFoundError(
            "유효한 sparse reconstruction 결과를 찾지 못했습니다.\n"
            "필요 파일: cameras.bin, images.bin, points3D.bin"
        )

    print("[Sparse reconstruction 결과 확인 완료]")

    for result_dir in valid_results:
        print(f"\n결과 폴더: {result_dir}")
        print(f"  - {result_dir / 'cameras.bin'}")
        print(f"  - {result_dir / 'images.bin'}")
        print(f"  - {result_dir / 'points3D.bin'}")

    print("\nCOLMAP sparse SfM이 정상적으로 완료되었습니다.")


# ============================================================
# 전체 파이프라인
# ============================================================

def main(strong=False, exhaustive=False):
    print("\nCOLMAP SfM 파이프라인 시작")

    check_inputs()
    reset_workspace()
    feature_extraction(strong=strong)
    matcher_type = "exhaustive" if exhaustive else MATCHER_TYPE
    if matcher_type == "exhaustive":
        exhaustive_matcher()
    elif matcher_type == "sequential":
        sequential_matcher()
    else:
        raise ValueError(f"지원하지 않는 MATCHER_TYPE입니다: {matcher_type}")
    make_sparse_folder()
    mapper()
    check_sparse_result()

    print("\n전체 파이프라인 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run COLMAP SfM pipeline")
    parser.add_argument(
        "--strong",
        action="store_true",
        help="Use stronger SIFT extraction settings for more features",
    )
    parser.add_argument(
        "--exhaustive",
        action="store_true",
        help="Use exhaustive matcher instead of the default sequential matcher",
    )
    args = parser.parse_args()

    main(strong=args.strong, exhaustive=args.exhaustive)
