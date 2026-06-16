#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [--from_step_2] [--exhaustive] \"video_name.mp4\""
  echo
  echo "Options:"
  echo "  --from_step_2  Skip COLMAP/dataset preparation and run 2DGS/postprocess only"
  echo "  --exhaustive   Pass --exhaustive to run_colmap.py from the first COLMAP attempt"
  echo
  echo "Example:"
  echo "  $0 \"태량오른발.mp4\""
  echo "  $0 --exhaustive \"태량오른발.mp4\""
  echo "  $0 --from_step_2 \"태량오른발.mp4\""
  echo "  $0 --from_step_2"
}

FROM_STEP_2=0
COLMAP_EXHAUSTIVE=0

POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from_step_2)
      FROM_STEP_2=1
      shift
      ;;
    --exhaustive)
      COLMAP_EXHAUSTIVE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        POSITIONAL_ARGS+=("$1")
        shift
      done
      ;;
    -*)
      echo "[Error] 알 수 없는 옵션입니다: $1" >&2
      usage
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}"

if [[ "$FROM_STEP_2" -eq 0 && $# -ne 1 ]]; then
  usage
  exit 1
fi

if [[ "$FROM_STEP_2" -eq 1 && $# -gt 1 ]]; then
  usage
  exit 1
fi

VIDEO_PATH="${1:-}"
STATE_FILE=".run_pipeline_state"
DOCKER_IMAGE="2dgs-cu118:0614"
SCENE_NAME=""

set_scene_name() {
  if [[ -z "${VIDEO_NAME:-}" ]]; then
    echo "[Error] VIDEO_NAME이 비어 있어 SCENE_NAME을 정할 수 없습니다." >&2
    exit 1
  fi

  SCENE_NAME="foot_scene_$VIDEO_NAME"
}

activate_amadeus_conda() {
  local conda_base=""
  local conda_sh=""

  if command -v conda >/dev/null 2>&1; then
    conda_base="$(conda info --base 2>/dev/null || true)"
    if [[ -n "$conda_base" && -f "$conda_base/etc/profile.d/conda.sh" ]]; then
      conda_sh="$conda_base/etc/profile.d/conda.sh"
    fi
  fi

  if [[ -z "$conda_sh" && -n "${CONDA_EXE:-}" ]]; then
    conda_base="$(dirname "$(dirname "$CONDA_EXE")")"
    if [[ -f "$conda_base/etc/profile.d/conda.sh" ]]; then
      conda_sh="$conda_base/etc/profile.d/conda.sh"
    fi
  fi

  if [[ -z "$conda_sh" ]]; then
    for conda_sh in \
      "$HOME/miniconda3/etc/profile.d/conda.sh" \
      "$HOME/anaconda3/etc/profile.d/conda.sh" \
      "/opt/conda/etc/profile.d/conda.sh"; do
      if [[ -f "$conda_sh" ]]; then
        break
      fi
    done
  fi

  if [[ -z "$conda_sh" || ! -f "$conda_sh" ]]; then
    echo "[Info] conda 초기화 스크립트를 찾지 못했습니다. 현재 Python 환경을 사용합니다."
    return
  fi

  # shellcheck source=/dev/null
  source "$conda_sh"

  if conda env list | awk '{print $1}' | grep -Fxq "amadeus"; then
    conda activate amadeus
    echo "[Info] Conda environment activated: amadeus"
  else
    echo "[Info] Conda environment 'amadeus'가 없어 현재 Python 환경을 사용합니다."
  fi
}

set_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    return
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "[Error] python 또는 python3 실행 파일을 찾을 수 없습니다." >&2
    exit 1
  fi
}

if [[ "$FROM_STEP_2" -eq 0 && ! -f "$VIDEO_PATH" ]]; then
  ASSET_VIDEO_PATH="assets/$VIDEO_PATH"
  if [[ -f "$ASSET_VIDEO_PATH" ]]; then
    echo "[Info] 입력 영상이 현재 경로에 없어 assets/에서 사용합니다: $ASSET_VIDEO_PATH"
    VIDEO_PATH="$ASSET_VIDEO_PATH"
  else
    echo "[Error] 영상 파일을 찾을 수 없습니다: $VIDEO_PATH 또는 $ASSET_VIDEO_PATH" >&2
    exit 1
  fi
fi

if [[ "$FROM_STEP_2" -eq 0 && "${VIDEO_PATH##*.}" != "mp4" ]]; then
  echo "[Error] .mp4 파일만 입력하세요: $VIDEO_PATH" >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
activate_amadeus_conda

has_colmap_model() {
  local model_dir="$1"
  [[ -d "$model_dir" \
    && -f "$model_dir/cameras.bin" \
    && -f "$model_dir/images.bin" \
    && -f "$model_dir/points3D.bin" ]]
}

count_sparse_models() {
  local sparse_dir="$1"
  local count=0

  if [[ ! -d "$sparse_dir" ]]; then
    echo 0
    return
  fi

  local recon_dir
  for recon_dir in "$sparse_dir"/*; do
    if has_colmap_model "$recon_dir"; then
      count=$((count + 1))
    fi
  done

  echo "$count"
}

single_sparse_model_dir() {
  local sparse_dir="$1"
  local recon_dir

  for recon_dir in "$sparse_dir"/*; do
    if has_colmap_model "$recon_dir"; then
      echo "$recon_dir"
      return 0
    fi
  done

  return 1
}

normalize_sparse_zero() {
  local sparse_dir="$1"
  local model_dir="$2"

  if [[ "$model_dir" == "$sparse_dir/0" ]]; then
    return
  fi

  if [[ -e "$sparse_dir/0" ]]; then
    echo "[Error] sparse/0이 이미 있어 결과 폴더를 정규화할 수 없습니다: $sparse_dir/0" >&2
    exit 1
  fi

  echo "[Info] sparse 결과 정규화: $model_dir -> $sparse_dir/0"
  mv "$model_dir" "$sparse_dir/0"
}

clear_sparse_for_retry() {
  local sparse_dir="$1"
  echo "[Info] 여러 reconstruction 감지. sparse 폴더 삭제 후 재시도: $sparse_dir"
  rm -rf "$sparse_dir"
}

run_colmap_until_single_model() {
  local attempts=()
  if [[ "$COLMAP_EXHAUSTIVE" -eq 1 ]]; then
    attempts=("--exhaustive" "--strong --exhaustive")
  else
    attempts=("" "--strong" "--strong --exhaustive")
  fi

  local attempt
  local model_count
  local model_dir
  local attempt_index=0

  for attempt in "${attempts[@]}"; do
    if [[ -n "$attempt" ]]; then
      if [[ "$attempt_index" -gt 0 ]]; then
        clear_sparse_for_retry "$COLMAP_WORK/sparse"
        echo "[Step 4] COLMAP 재실행: run_colmap.py $attempt"
      else
        echo "[Step 4] COLMAP 실행: run_colmap.py $attempt"
      fi
      # shellcheck disable=SC2086
      "$PYTHON_BIN" run_colmap.py $attempt
    else
      echo "[Step 4] COLMAP 실행"
      "$PYTHON_BIN" run_colmap.py
    fi

    model_count="$(count_sparse_models "$COLMAP_WORK/sparse")"
    echo "[Info] sparse reconstruction 개수: $model_count"

    if [[ "$model_count" -eq 1 ]]; then
      model_dir="$(single_sparse_model_dir "$COLMAP_WORK/sparse")"
      normalize_sparse_zero "$COLMAP_WORK/sparse" "$model_dir"
      return
    fi

    if [[ "$model_count" -eq 0 ]]; then
      echo "[Error] COLMAP sparse reconstruction 결과가 없습니다." >&2
      exit 1
    fi

    attempt_index=$((attempt_index + 1))
  done

  echo "[Error] 최종 COLMAP 재시도 후에도 sparse reconstruction이 여러 개입니다." >&2
  find "$COLMAP_WORK/sparse" -maxdepth 1 -mindepth 1 -type d -print >&2
  exit 1
}

move_final_dataset() {
  local source_root="$1"
  local final_root="$PROJECT_DIR/dataset/$SCENE_NAME"

  local source_images="$source_root/images"
  local source_sparse_zero="$source_root/sparse/0"

  if [[ ! -d "$source_images" ]]; then
    echo "[Error] undistorted images 폴더가 없습니다: $source_images" >&2
    exit 1
  fi

  if ! has_colmap_model "$source_sparse_zero"; then
    echo "[Error] undistorted sparse/0 모델이 없습니다: $source_sparse_zero" >&2
    exit 1
  fi

  backup_existing_path "$final_root"

  echo "[Step 8] 최종 dataset 생성: $final_root"
  mkdir -p "$final_root/sparse"
  mv "$source_images" "$final_root/images"
  mv "$source_sparse_zero" "$final_root/sparse/0"
}

backup_existing_path() {
  local path="$1"

  if [[ ! -e "$path" ]]; then
    return
  fi

  local item_epoch
  local item_timestamp
  local relative_path
  local relative_dir
  local item_name
  local legacy_dir
  local backup_path
  local duplicate_index=1

  item_epoch="$(stat -c '%Y' "$path")"
  item_timestamp="$(date -d "@$item_epoch" '+%Y%m%d_%H%M%S')"
  relative_path="${path#"$PROJECT_DIR"/}"

  if [[ "$relative_path" == "$path" ]]; then
    relative_path="${path#./}"
  fi

  relative_dir="$(dirname "$relative_path")"
  item_name="$(basename "$relative_path")"
  legacy_dir="$PROJECT_DIR/legacy/$relative_dir"
  mkdir -p "$legacy_dir"

  if [[ -d "$path" ]]; then
    backup_path="$legacy_dir/${item_name}_${item_timestamp}"
  elif [[ "$item_name" == *.* ]]; then
    backup_path="$legacy_dir/${item_name%.*}_${item_timestamp}.${item_name##*.}"
  else
    backup_path="$legacy_dir/${item_name}_${item_timestamp}"
  fi

  while [[ -e "$backup_path" ]]; do
    if [[ -d "$path" ]]; then
      backup_path="$legacy_dir/${item_name}_${item_timestamp}_${duplicate_index}"
    elif [[ "$item_name" == *.* ]]; then
      backup_path="$legacy_dir/${item_name%.*}_${item_timestamp}_${duplicate_index}.${item_name##*.}"
    else
      backup_path="$legacy_dir/${item_name}_${item_timestamp}_${duplicate_index}"
    fi
    duplicate_index=$((duplicate_index + 1))
  done

  echo "[Info] 기존 경로 백업: $path -> $backup_path"
  mv "$path" "$backup_path"
}

remove_existing_video_dataset() {
  local video_dataset="$PROJECT_DIR/dataset/$VIDEO_NAME"

  if [[ -z "${VIDEO_NAME:-}" ]]; then
    echo "[Error] VIDEO_NAME이 비어 있어 dataset 정리를 할 수 없습니다." >&2
    exit 1
  fi

  if [[ ! -e "$video_dataset" ]]; then
    return
  fi

  echo "[Info] 기존 dataset/$VIDEO_NAME 삭제 후 재생성: $video_dataset"
  rm -rf "$video_dataset"
}

backup_existing_scene_output() {
  local scene_output="$PROJECT_DIR/output/$SCENE_NAME"

  if [[ -z "${SCENE_NAME:-}" ]]; then
    echo "[Error] SCENE_NAME이 비어 있어 output 정리를 할 수 없습니다." >&2
    exit 1
  fi

  backup_existing_path "$scene_output"
}

move_owned_file() {
  local source_path="$1"
  local target_path="$2"

  if mv "$source_path" "$target_path" 2>/dev/null; then
    return
  fi

  echo "[Warn] 파일 이동 실패. Docker 산출물 권한 문제일 수 있습니다: $source_path" >&2
  echo "       현재 사용자에게 소유권을 돌린 뒤 다시 시도하세요:" >&2
  echo "       sudo chown -R $(id -u):$(id -g) output 2dgs_output 2dgs_post_output" >&2
  exit 1
}

copy_owned_file() {
  local source_path="$1"
  local target_path="$2"

  if cp "$source_path" "$target_path" 2>/dev/null; then
    return
  fi

  echo "[Warn] 파일 복사 실패. Docker 산출물 권한 문제일 수 있습니다: $source_path" >&2
  echo "       현재 사용자에게 소유권을 돌린 뒤 다시 시도하세요:" >&2
  echo "       sudo chown -R $(id -u):$(id -g) output 2dgs_output 2dgs_post_output print_output" >&2
  exit 1
}

write_pipeline_state() {
  cat > "$STATE_FILE" <<EOF
VIDEO_NAME='$VIDEO_NAME'
TIMESTAMP='$TIMESTAMP'
COLMAP_WORK_TARGET='$COLMAP_WORK_TARGET'
SCENE_NAME='$SCENE_NAME'
EOF
}

load_pipeline_state() {
  if [[ ! -f "$STATE_FILE" ]]; then
    echo "[Error] Step 2 상태 파일이 없습니다: $STATE_FILE" >&2
    echo "        먼저 Step 1을 실행하거나, --from_step_2 video_name.mp4 형태로 이름을 넘겨주세요." >&2
    exit 1
  fi

  # shellcheck disable=SC1090
  source "$STATE_FILE"
}

ensure_docker_image() {
  if docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    echo "[Step 9] Docker image already exists: $DOCKER_IMAGE"
    return
  fi

  echo "[Step 9] Docker image build: $DOCKER_IMAGE"
  docker build -t "$DOCKER_IMAGE" .
}

run_2dgs_container() {
  mkdir -p "$PROJECT_DIR/output"

  echo "[Step 10] 2DGS train/mesh extraction in Docker"
  docker run --gpus all --rm \
    --user "$(id -u):$(id -g)" \
    -v "$PROJECT_DIR/dataset:/app/dataset" \
    -v "$PROJECT_DIR/output:/app/output" \
    -e SCENE="$SCENE_NAME" \
    "$DOCKER_IMAGE" \
    bash -lc 'set -euo pipefail; train_2dgs.sh --depth_ratio 0; extract_mesh_quick.sh'
}

collect_and_postprocess_mesh() {
  local scene_output="$PROJECT_DIR/output/$SCENE_NAME"
  local output_mesh=""
  local scale_source_ply="${SCALE_SOURCE_PLY:-}"
  local unprocessed_dir="$PROJECT_DIR/2dgs_output"
  local post_output_dir="$PROJECT_DIR/2dgs_post_output"
  local print_output_dir="$PROJECT_DIR/print_output/$VIDEO_NAME"
  local foot_raw_ply="$unprocessed_dir/${VIDEO_NAME}_foot_raw.ply"
  local unprocessed_ply="$unprocessed_dir/${VIDEO_NAME}_unprocessed.ply"
  local scale_raw_ply="$unprocessed_dir/${VIDEO_NAME}_scale_raw.ply"
  local scale_filtered_ply="$unprocessed_dir/${VIDEO_NAME}_scale_filtered.ply"
  local generated_stl="$post_output_dir/postprocessed/${VIDEO_NAME}_postprocessed.stl"
  local final_stl="$post_output_dir/${VIDEO_NAME}_postprocessed.stl"

  local foot_mesh_candidates=(
    "$scene_output/unbounded_default_post.ply"
    "$scene_output/mesh_quick/unbounded_default_post.ply"
    "$scene_output/train/ours_30000/fuse_unbounded_post.ply"
    "$scene_output/mesh_quick/unbounded_default.ply"
    "$scene_output/train/ours_30000/fuse_unbounded.ply"
  )

  local candidate
  for candidate in "${foot_mesh_candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      output_mesh="$candidate"
      break
    fi
  done

  if [[ -z "$scale_source_ply" ]]; then
    local scale_ply_candidates=(
      "$scene_output/point_cloud/iteration_30000/point_cloud.ply"
      "$scene_output/point_cloud/iteration_7000/point_cloud.ply"
      "$scene_output/input.ply"
      "$output_mesh"
    )

    for candidate in "${scale_ply_candidates[@]}"; do
      if [[ -n "$candidate" && -f "$candidate" ]]; then
        scale_source_ply="$candidate"
        break
      fi
    done
  fi

  if [[ -z "$output_mesh" || ! -f "$output_mesh" ]]; then
    echo "[Error] 2DGS mesh 결과를 찾을 수 없습니다:" >&2
    for candidate in "${foot_mesh_candidates[@]}"; do
      echo "  - $candidate" >&2
    done
    exit 1
  fi

  if [[ -z "$scale_source_ply" || ! -f "$scale_source_ply" ]]; then
    echo "[Error] scale 계산용 PLY를 찾을 수 없습니다." >&2
    echo "        SCALE_SOURCE_PLY 환경변수로 직접 지정할 수 있습니다." >&2
    exit 1
  fi

  mkdir -p "$unprocessed_dir" "$post_output_dir"
  backup_existing_path "$foot_raw_ply"
  backup_existing_path "$unprocessed_ply"
  backup_existing_path "$scale_raw_ply"
  backup_existing_path "$scale_filtered_ply"

  echo "[Step 11] 2DGS foot mesh 복사: $output_mesh -> $foot_raw_ply"
  copy_owned_file "$output_mesh" "$foot_raw_ply"
  echo "[Step 11] postprocessing 입력 이름 생성: $unprocessed_ply"
  copy_owned_file "$foot_raw_ply" "$unprocessed_ply"

  echo "[Step 11] 2DGS scale source 복사: $scale_source_ply -> $scale_raw_ply"
  copy_owned_file "$scale_source_ply" "$scale_raw_ply"

  echo "[Step 3-1] postprocessing_save_steps.py 실행"
  # shellcheck disable=SC2086
  "$PYTHON_BIN" postprocessing_save_steps.py --input "$unprocessed_ply" ${POSTPROCESS_ARGS:-}

  if [[ ! -f "$generated_stl" ]]; then
    echo "[Error] postprocessed STL 결과가 없습니다: $generated_stl" >&2
    exit 1
  fi

  backup_existing_path "$final_stl"
  echo "[Step 3-1] 최종 STL 이동: $generated_stl -> $final_stl"
  move_owned_file "$generated_stl" "$final_stl"

  echo "[Step 3-2] postprocessing_for_scaling.py 실행"
  "$PYTHON_BIN" postprocessing_for_scaling.py \
    --input "$scale_raw_ply" \
    --output "$scale_filtered_ply" \
    --z-min "${SCALE_Z_MIN:--0.1}" \
    --z-max "${SCALE_Z_MAX:-0.01}"

  backup_existing_path "$print_output_dir"
  mkdir -p "$print_output_dir"

  local skip_slicing_arg=()
  if [[ "${SKIP_SLICING:-0}" == "1" ]]; then
    skip_slicing_arg=(--skip-slicing)
  fi

  echo "[Step 3-3] scale 적용/최종 mesh 정리/Orca slicing 실행"
  # shellcheck disable=SC2086
  "$PYTHON_BIN" finalize_print_pipeline.py \
    --input-stl "$final_stl" \
    --scale-ply "$scale_filtered_ply" \
    --output-dir "$print_output_dir" \
    --video-name "$VIDEO_NAME" \
    --square-real-size-mm "${SQUARE_MM:-30}" \
    --scale-resolution "${SCALE_RESOLUTION:-1000}" \
    --slicer-timeout-seconds "${SLICER_TIMEOUT_SECONDS:-900}" \
    "${skip_slicing_arg[@]}" \
    ${FINALIZE_PRINT_ARGS:-}
}

run_step_2() {
  if [[ ! -d "$PROJECT_DIR/dataset/$SCENE_NAME/images" ]] \
    || ! has_colmap_model "$PROJECT_DIR/dataset/$SCENE_NAME/sparse/0"; then
    echo "[Error] Step 2 입력 dataset이 없습니다: $PROJECT_DIR/dataset/$SCENE_NAME" >&2
    exit 1
  fi

  ensure_docker_image
  backup_existing_scene_output
  run_2dgs_container
  collect_and_postprocess_mesh
}

if [[ "$FROM_STEP_2" -eq 1 ]]; then
  PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$PROJECT_DIR"
  set_python_bin

  if [[ $# -eq 1 ]]; then
    VIDEO_FILE="$(basename "$1")"
    VIDEO_NAME="${VIDEO_FILE%.*}"
    TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
    COLMAP_WORK_TARGET=""
    set_scene_name
  else
    load_pipeline_state
    if [[ -z "${SCENE_NAME:-}" || "$SCENE_NAME" == "foot_scene" ]]; then
      set_scene_name
    fi
  fi

  echo "[Info] Project       : $PROJECT_DIR"
  echo "[Info] Video name    : $VIDEO_NAME"
  echo "[Info] Scene         : $SCENE_NAME"
  echo "[Info] Start from    : Step 2"
  run_step_2

  echo "[Done] Step 2 완료"
  echo "[Done] unprocessed ply: $PROJECT_DIR/2dgs_output/${VIDEO_NAME}_unprocessed.ply"
  echo "[Done] postprocessed : $PROJECT_DIR/2dgs_post_output/${VIDEO_NAME}_postprocessed.stl"
  exit 0
fi

VIDEO_FILE="$(basename "$VIDEO_PATH")"
VIDEO_NAME="${VIDEO_FILE%.*}"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
set_scene_name

COLMAP_DIR="$PROJECT_DIR/colmap"
COLMAP_INPUT="$COLMAP_DIR/input"

SEGMENTATION_DIR="$PROJECT_DIR/dataset/$VIDEO_NAME/segmentation/both"
LEGACY_SEGMENTATION_DIR="$PROJECT_DIR/dataset/$VIDEO_NAME/segmenation/both"

COLMAP_WORK="$PROJECT_DIR/colmap_work_tmp"
COLMAP_WORK_ROOT="$PROJECT_DIR/colmap_work"
COLMAP_WORK_TARGET="$COLMAP_WORK_ROOT/$VIDEO_NAME"

set_python_bin

echo "[Info] Project       : $PROJECT_DIR"
echo "[Info] Video         : $VIDEO_PATH"
echo "[Info] Video name    : $VIDEO_NAME"
echo "[Info] Scene         : $SCENE_NAME"
echo "[Info] Timestamp     : $TIMESTAMP"

mkdir -p "$COLMAP_DIR" "$COLMAP_WORK_ROOT"
remove_existing_video_dataset

if [[ -e "$COLMAP_INPUT" ]]; then
  echo "[Step 1] 기존 colmap/input legacy 이동: $COLMAP_INPUT"
  backup_existing_path "$COLMAP_INPUT"
else
  echo "[Step 1] 기존 colmap/input 없음. 새로 생성합니다."
fi

mkdir -p "$COLMAP_INPUT"
echo "[Step 1] 빈 colmap/input 생성 완료: $COLMAP_INPUT"

echo "[Step 2] 전처리/세그멘테이션 실행"
"$PYTHON_BIN" pipeline_before_colmap.py -p "$VIDEO_PATH"

if [[ ! -d "$SEGMENTATION_DIR" && -d "$LEGACY_SEGMENTATION_DIR" ]]; then
  echo "[Warn] segmentation 폴더가 없어 기존 오타 경로를 사용합니다: $LEGACY_SEGMENTATION_DIR"
  SEGMENTATION_DIR="$LEGACY_SEGMENTATION_DIR"
fi

if [[ ! -d "$SEGMENTATION_DIR" ]]; then
  echo "[Error] segmentation 결과 폴더를 찾을 수 없습니다: $SEGMENTATION_DIR" >&2
  exit 1
fi

shopt -s nullglob
jpg_files=("$SEGMENTATION_DIR"/*.jpg "$SEGMENTATION_DIR"/*.JPG)
shopt -u nullglob

if [[ ${#jpg_files[@]} -eq 0 ]]; then
  echo "[Error] 복사할 .jpg 파일이 없습니다: $SEGMENTATION_DIR" >&2
  exit 1
fi

echo "[Step 3] segmentation/both jpg 복사: ${#jpg_files[@]}장"
cp "${jpg_files[@]}" "$COLMAP_INPUT/"

backup_existing_path "$COLMAP_WORK"
run_colmap_until_single_model

if [[ ! -d "$COLMAP_WORK" ]]; then
  echo "[Error] COLMAP 결과 폴더가 없습니다: $COLMAP_WORK" >&2
  exit 1
fi

echo "[Step 5] 결과 폴더 이름 변경: $COLMAP_WORK -> $COLMAP_WORK_TARGET"
backup_existing_path "$COLMAP_WORK_TARGET"
mv "$COLMAP_WORK" "$COLMAP_WORK_TARGET"

UNDISTORTED_DIR="$COLMAP_WORK_TARGET/undistorted"
UNDISTORTED_SPARSE_ZERO="$UNDISTORTED_DIR/sparse/0"

echo "[Step 6] COLMAP undistort 실행"
"$PYTHON_BIN" undistort_colmap.py \
  --input_path "$COLMAP_WORK_TARGET/sparse/0" \
  --image_path "$COLMAP_INPUT" \
  --output_path "$UNDISTORTED_DIR" \
  --overwrite

echo "[Step 7] undistorted sparse 좌표축 정렬"
"$PYTHON_BIN" auto_align_colmap.py --input_path "$UNDISTORTED_SPARSE_ZERO"

move_final_dataset "$UNDISTORTED_DIR"
write_pipeline_state

echo "[Step 1 Done] COLMAP dataset 준비 완료"
echo "[Done] colmap result: $COLMAP_WORK_TARGET"
echo "[Done] 2DGS source  : $PROJECT_DIR/dataset/$SCENE_NAME"

run_step_2

echo "[Done] 전체 파이프라인 완료"
echo "[Done] unprocessed ply: $PROJECT_DIR/2dgs_output/${VIDEO_NAME}_unprocessed.ply"
echo "[Done] postprocessed : $PROJECT_DIR/2dgs_post_output/${VIDEO_NAME}_postprocessed.stl"
