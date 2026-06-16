# =========================================================
# 2D Gaussian Splatting Dockerfile
# - CUDA 11.8 고정
# - PyTorch CUDA 11.8 고정
# - 2DGS submodule 직접 빌드
# - dataset/<scene>/images, sparse/0/*.bin 구조 사용
# - bounded / unbounded mesh 추출 스크립트 추가
# - mesh sweep 스크립트 추가
# =========================================================

FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/cuda/bin:/opt/conda/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/cuda/lib64:${LD_LIBRARY_PATH}"
ENV CUDA_HOME="/usr/local/cuda"
ENV TORCH_CUDA_ARCH_LIST="8.6"

# 시스템 패키지
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    unzip \
    ffmpeg \
    build-essential \
    cmake \
    ninja-build \
    pkg-config \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libssl-dev \
    ca-certificates \
    nano \
    bash \
    coreutils \
    findutils \
    && rm -rf /var/lib/apt/lists/*

# miniconda 설치
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

# conda 채널 정리
RUN echo "channels:\n  - pytorch\n  - nvidia\n  - conda-forge\nchannel_priority: strict" > /root/.condarc

# 0. 아나콘다 이용약관 동의 (추가)
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# 1. 가상환경 생성 (이전 레이어 유지)
RUN conda create -n surfel_splatting python=3.8 pip -c conda-forge -y

# 2. 줄바꿈 없이 한 줄로 이어서 실행
RUN conda run --no-capture-output -n surfel_splatting pip install --no-cache-dir torch==2.1.2+cu118 torchvision==0.16.2+cu118 torchaudio==2.1.2 --extra-index-url https://download.pytorch.org/whl/cu118

# 이후 모든 RUN은 해당 env 안에서 실행
SHELL ["conda", "run", "-n", "surfel_splatting", "/bin/bash", "-c"]

# PyTorch + CUDA 11.8 고정
# RUN pip install --no-cache-dir \
#    torch==2.1.2+cu118 \
#    torchvision==0.16.2+cu118 \
#    torchaudio==2.1.2 \
#    --extra-index-url https://download.pytorch.org/whl/cu118

# 6번 레이어: pip 대신 conda run을 이용해 정확히 가상환경 내에 CUDA 11.8용 torch 2.1.2 설치
# RUN conda run -n surfel_splatting conda install pytorch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 pytorch-cuda=11.8 -c pytorch -c nvidia -y


RUN python -c "import torch; print(torch.__version__, torch.version.cuda)"

ENV CONDA_OVERRIDE_CUDA=11.8

# env 안에도 11.8 toolkit 설치
RUN conda install -y -c "nvidia/label/cuda-11.8.0" cuda-toolkit -c conda-forge \
    --override-channels

# env 활성화 시 env 내부 CUDA 우선 사용
RUN mkdir -p $CONDA_PREFIX/etc/conda/activate.d && \
    printf '%s\n' \
    'export CUDA_HOME=$CONDA_PREFIX' \
    'export PATH=$CUDA_HOME/bin:$PATH' \
    'export LD_LIBRARY_PATH=$CUDA_HOME/lib:$CUDA_HOME/lib64:$LD_LIBRARY_PATH' \
    > $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh

WORKDIR /app

# 2DGS clone
RUN git clone --recursive https://github.com/hbb1/2d-gaussian-splatting.git /app/2d-gaussian-splatting
WORKDIR /app/2d-gaussian-splatting

# submodule 최신화
RUN git submodule update --init --recursive

# Open3D expects mesh vertex colors in [0, 1] before writing PLY.
RUN python - <<'PY'
from pathlib import Path

path = Path("/app/2d-gaussian-splatting/utils/mesh_utils.py")
text = path.read_text()
old = """        _, rgbs = compute_unbounded_tsdf(torch.tensor(np.asarray(mesh.vertices)).float().cuda(), inv_contraction=None, voxel_size=voxel_size, return_rgb=True)
        mesh.vertex_colors = o3d.utility.Vector3dVector(rgbs.cpu().numpy())
        return mesh
"""
new = """        _, rgbs = compute_unbounded_tsdf(torch.tensor(np.asarray(mesh.vertices)).float().cuda(), inv_contraction=None, voxel_size=voxel_size, return_rgb=True)
        rgb_min = rgbs.min().item()
        rgb_max = rgbs.max().item()
        invalid_ratio = ((rgbs < 0.0) | (rgbs > 1.0)).float().mean().item()
        print(f"mesh vertex rgb min/max: {rgb_min:.6f}/{rgb_max:.6f}, out-of-range ratio: {invalid_ratio:.6%}")
        rgbs = rgbs.clamp(0.0, 1.0)
        mesh.vertex_colors = o3d.utility.Vector3dVector(rgbs.cpu().numpy())
        return mesh
"""
if old not in text:
    raise SystemExit("mesh_utils.py patch target not found")
path.write_text(text.replace(old, new))
PY

# python 패키지 설치
RUN pip install --upgrade pip setuptools wheel
RUN pip install \
    open3d==0.18.0 \
    mediapy==1.1.2 \
    lpips==0.1.4 \
    scikit-image==0.21.0 \
    tqdm==4.66.2 \
    trimesh==4.3.2 \
    plyfile \
    opencv-python

RUN python -c "import torch; print(torch.__version__, torch.version.cuda)"

# CUDA extension 빌드
RUN pip install ./submodules/simple-knn --no-build-isolation
RUN pip install ./submodules/diff-surfel-rasterization --no-build-isolation

# 설치 검증
RUN python -c "import torch; print('torch:', torch.__version__, 'cuda:', torch.version.cuda)"
RUN python -c "import diff_surfel_rasterization, simple_knn; print('2DGS extensions OK')"

# 작업 폴더
WORKDIR /app

# 데이터/출력 디렉토리
RUN mkdir -p /app/dataset /app/output /app/scripts

# =========================================================
# 편의용 실행 스크립트
# =========================================================

# train
RUN cat > /usr/local/bin/train_2dgs.sh <<'EOF' && chmod +x /usr/local/bin/train_2dgs.sh
#!/bin/bash
set -euo pipefail

_START_TIME=$SECONDS
trap 'ec=$?; elapsed=$((SECONDS - _START_TIME)); echo "[TIME] train_2dgs.sh elapsed: ${elapsed}s"; exit $ec' EXIT

: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting

check_2dgs_dataset.sh

cd /app/2d-gaussian-splatting

python train.py \
  -s /app/dataset/${SCENE} \
  -m /app/output/${SCENE} \
  "${@}"
EOF

# view
RUN cat > /usr/local/bin/view_2dgs.sh <<'EOF' && chmod +x /usr/local/bin/view_2dgs.sh
#!/bin/bash
set -euo pipefail
: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting
cd /app/2d-gaussian-splatting

python view.py \
  -s /app/dataset/${SCENE} \
  -m /app/output/${SCENE} \
  "${@}"
EOF

# 기본 render (bounded 기본)
RUN cat > /usr/local/bin/render_2dgs.sh <<'EOF' && chmod +x /usr/local/bin/render_2dgs.sh
#!/bin/bash
set -euo pipefail
: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting
cd /app/2d-gaussian-splatting

python render.py \
  -s /app/dataset/${SCENE} \
  -m /app/output/${SCENE} \
  --skip_train \
  --skip_test \
  "${@}"
EOF

# bounded mesh 단일 추출
RUN cat > /usr/local/bin/render_2dgs_bounded.sh <<'EOF' && chmod +x /usr/local/bin/render_2dgs_bounded.sh
#!/bin/bash
set -euo pipefail
: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting
cd /app/2d-gaussian-splatting

python render.py \
  -s /app/dataset/${SCENE} \
  -m /app/output/${SCENE} \
  --skip_train \
  --skip_test \
  "${@}"
EOF

# unbounded mesh 단일 추출
RUN cat > /usr/local/bin/render_2dgs_unbounded.sh <<'EOF' && chmod +x /usr/local/bin/render_2dgs_unbounded.sh
#!/bin/bash
set -euo pipefail
: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting
cd /app/2d-gaussian-splatting

python render.py \
  -s /app/dataset/${SCENE} \
  -m /app/output/${SCENE} \
  --skip_train \
  --skip_test \
  --unbounded \
  "${@}"
EOF

# 여러 파라미터 sweep으로 ply 저장
RUN cat > /usr/local/bin/extract_mesh_variants.sh <<'EOF' && chmod +x /usr/local/bin/extract_mesh_variants.sh
#!/bin/bash
set -euo pipefail
: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting
cd /app/2d-gaussian-splatting

DATASET_PATH="/app/dataset/${SCENE}"
MODEL_PATH="/app/output/${SCENE}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SAVE_ROOT="${MODEL_PATH}/mesh_sweeps/${TIMESTAMP}"

mkdir -p "${SAVE_ROOT}"

echo "[INFO] SCENE=${SCENE}"
echo "[INFO] DATASET_PATH=${DATASET_PATH}"
echo "[INFO] MODEL_PATH=${MODEL_PATH}"
echo "[INFO] SAVE_ROOT=${SAVE_ROOT}"

COMMON_ARGS=(
  -s "${DATASET_PATH}"
  -m "${MODEL_PATH}"
  --skip_train
  --skip_test
)

# 최신 ours_* 폴더 찾기
get_latest_train_dir() {
  find "${MODEL_PATH}/train" -maxdepth 1 -type d -name 'ours_*' | sort | tail -n 1
}

# -----------------------------
# bounded mesh sweep
# -----------------------------
BOUNDED_DEPTH_RATIO_LIST=(0 1)
BOUNDED_MESH_RES_LIST=(512 1024)
BOUNDED_DEPTH_TRUNC_LIST=(2.0 3.0 4.0)
BOUNDED_VOXEL_SIZE_LIST=(0.002 0.004 0.008)
BOUNDED_NUM_CLUSTER_LIST=(10 30 50)

for depth_ratio in "${BOUNDED_DEPTH_RATIO_LIST[@]}"; do
  for mesh_res in "${BOUNDED_MESH_RES_LIST[@]}"; do
    for depth_trunc in "${BOUNDED_DEPTH_TRUNC_LIST[@]}"; do
      for voxel_size in "${BOUNDED_VOXEL_SIZE_LIST[@]}"; do
        for num_cluster in "${BOUNDED_NUM_CLUSTER_LIST[@]}"; do
          tag="bounded_dr${depth_ratio}_res${mesh_res}_dt${depth_trunc}_vs${voxel_size}_nc${num_cluster}"
          echo "[RUN] ${tag}"

          python render.py \
            "${COMMON_ARGS[@]}" \
            --depth_ratio "${depth_ratio}" \
            --mesh_res "${mesh_res}" \
            --depth_trunc "${depth_trunc}" \
            --voxel_size "${voxel_size}" \
            --num_cluster "${num_cluster}"

          SRC_DIR="$(get_latest_train_dir || true)"
          if [ -z "${SRC_DIR}" ]; then
            echo "[WARN] train/ours_* not found, skip copy for ${tag}"
            continue
          fi

          [ -f "${SRC_DIR}/fuse.ply" ] && cp "${SRC_DIR}/fuse.ply" "${SAVE_ROOT}/${tag}.ply" || true
          [ -f "${SRC_DIR}/fuse_post.ply" ] && cp "${SRC_DIR}/fuse_post.ply" "${SAVE_ROOT}/${tag}_post.ply" || true

          cat > "${SAVE_ROOT}/${tag}.txt" <<META
mode=bounded
scene=${SCENE}
depth_ratio=${depth_ratio}
mesh_res=${mesh_res}
depth_trunc=${depth_trunc}
voxel_size=${voxel_size}
num_cluster=${num_cluster}
dataset_path=${DATASET_PATH}
model_path=${MODEL_PATH}
src_dir=${SRC_DIR}
META
        done
      done
    done
  done
done

# -----------------------------
# unbounded mesh sweep
# -----------------------------
UNBOUNDED_DEPTH_RATIO_LIST=(0 1)
UNBOUNDED_MESH_RES_LIST=(512 1024 1536)
UNBOUNDED_NUM_CLUSTER_LIST=(10 30 50)

for depth_ratio in "${UNBOUNDED_DEPTH_RATIO_LIST[@]}"; do
  for mesh_res in "${UNBOUNDED_MESH_RES_LIST[@]}"; do
    for num_cluster in "${UNBOUNDED_NUM_CLUSTER_LIST[@]}"; do
      tag="unbounded_dr${depth_ratio}_res${mesh_res}_nc${num_cluster}"
      echo "[RUN] ${tag}"

      python render.py \
        "${COMMON_ARGS[@]}" \
        --unbounded \
        --depth_ratio "${depth_ratio}" \
        --mesh_res "${mesh_res}" \
        --num_cluster "${num_cluster}"

      SRC_DIR="$(get_latest_train_dir || true)"
      if [ -z "${SRC_DIR}" ]; then
        echo "[WARN] train/ours_* not found, skip copy for ${tag}"
        continue
      fi

      [ -f "${SRC_DIR}/fuse_unbounded.ply" ] && cp "${SRC_DIR}/fuse_unbounded.ply" "${SAVE_ROOT}/${tag}.ply" || true
      [ -f "${SRC_DIR}/fuse_unbounded_post.ply" ] && cp "${SRC_DIR}/fuse_unbounded_post.ply" "${SAVE_ROOT}/${tag}_post.ply" || true

      cat > "${SAVE_ROOT}/${tag}.txt" <<META
mode=unbounded
scene=${SCENE}
depth_ratio=${depth_ratio}
mesh_res=${mesh_res}
num_cluster=${num_cluster}
dataset_path=${DATASET_PATH}
model_path=${MODEL_PATH}
src_dir=${SRC_DIR}
META
    done
  done
done

echo "[DONE] mesh sweep completed"
echo "[DONE] results saved under: ${SAVE_ROOT}"
EOF

# 선택: 빠른 대표 조합만 추출
RUN cat > /usr/local/bin/extract_mesh_quick.sh <<'EOF' && chmod +x /usr/local/bin/extract_mesh_quick.sh
#!/bin/bash
set -euo pipefail

_START_TIME=$SECONDS
trap 'ec=$?; elapsed=$((SECONDS - _START_TIME)); echo "[TIME] extract_mesh_quick.sh elapsed: ${elapsed}s"; exit $ec' EXIT

: "${SCENE:?SCENE environment variable is required}"

source /opt/conda/etc/profile.d/conda.sh
conda activate surfel_splatting
cd /app/2d-gaussian-splatting

MODEL_PATH="/app/output/${SCENE}"
SAVE_ROOT="${MODEL_PATH}/mesh_quick"
mkdir -p "${SAVE_ROOT}"
rm -f "${SAVE_ROOT}/unbounded_default.ply" "${SAVE_ROOT}/unbounded_default_post.ply" "${SAVE_ROOT}/used_mesh_settings.txt"

MESH_RES_LIST="${TWO_DGS_MESH_RES_LIST:-512 1024}"
DEPTH_RATIO="${TWO_DGS_DEPTH_RATIO:-0}"
NUM_CLUSTER="${TWO_DGS_NUM_CLUSTER:-30}"

echo "[INFO] mesh extraction candidates: ${MESH_RES_LIST}"
echo "[INFO] depth_ratio=${DEPTH_RATIO}, num_cluster=${NUM_CLUSTER}"

SUCCESS=0
for MESH_RES in ${MESH_RES_LIST}; do
  echo "[RUN] unbounded mesh extraction mesh_res=${MESH_RES}"
  if python render.py \
    -s /app/dataset/${SCENE} \
    -m ${MODEL_PATH} \
    --skip_train \
    --skip_test \
    --unbounded \
    --mesh_res "${MESH_RES}" \
    --depth_ratio "${DEPTH_RATIO}" \
    --num_cluster "${NUM_CLUSTER}"; then

    LATEST_DIR=$(find "${MODEL_PATH}/train" -maxdepth 1 -type d -name 'ours_*' | sort | tail -n 1)
    [ -f "${LATEST_DIR}/fuse_unbounded.ply" ] && cp "${LATEST_DIR}/fuse_unbounded.ply" "${SAVE_ROOT}/unbounded_default.ply" || true
    if [ -f "${LATEST_DIR}/fuse_unbounded_post.ply" ]; then
      cp "${LATEST_DIR}/fuse_unbounded_post.ply" "${SAVE_ROOT}/unbounded_default_post.ply"
    elif [ -f "${LATEST_DIR}/fuse_unbounded.ply" ]; then
      cp "${LATEST_DIR}/fuse_unbounded.ply" "${SAVE_ROOT}/unbounded_default_post.ply"
    fi

    if [ -f "${SAVE_ROOT}/unbounded_default_post.ply" ]; then
      echo "mesh_res=${MESH_RES}" > "${SAVE_ROOT}/used_mesh_settings.txt"
      echo "depth_ratio=${DEPTH_RATIO}" >> "${SAVE_ROOT}/used_mesh_settings.txt"
      echo "num_cluster=${NUM_CLUSTER}" >> "${SAVE_ROOT}/used_mesh_settings.txt"
      SUCCESS=1
      break
    fi
  fi
  echo "[WARN] mesh_res=${MESH_RES} failed, trying next candidate..."
done

if [ "${SUCCESS}" -ne 1 ]; then
  echo "[ERROR] all mesh extraction candidates failed: ${MESH_RES_LIST}"
  exit 1
fi

echo "[DONE] quick mesh extraction saved under ${SAVE_ROOT}"
EOF

RUN cat > /usr/local/bin/check_2dgs_dataset.sh <<'EOF' && chmod +x /usr/local/bin/check_2dgs_dataset.sh
#!/bin/bash
set -euo pipefail

_START_TIME=$SECONDS
trap 'ec=$?; elapsed=$((SECONDS - _START_TIME)); echo "[TIME] check_2dgs_dataset.sh elapsed: ${elapsed}s"; exit $ec' EXIT

: "${SCENE:?SCENE environment variable is required}"

DATASET_DIR="/app/dataset/${SCENE}"

echo "[INFO] checking dataset: ${DATASET_DIR}"

[ -d "${DATASET_DIR}" ] || { echo "[ERROR] dataset dir not found: ${DATASET_DIR}"; exit 1; }
[ -d "${DATASET_DIR}/images" ] || { echo "[ERROR] images dir not found: ${DATASET_DIR}/images"; exit 1; }
[ -d "${DATASET_DIR}/sparse/0" ] || { echo "[ERROR] sparse/0 dir not found: ${DATASET_DIR}/sparse/0"; exit 1; }

[ -f "${DATASET_DIR}/sparse/0/cameras.bin" ] || { echo "[ERROR] cameras.bin missing"; exit 1; }
[ -f "${DATASET_DIR}/sparse/0/images.bin" ] || { echo "[ERROR] images.bin missing"; exit 1; }
[ -f "${DATASET_DIR}/sparse/0/points3D.bin" ] || { echo "[ERROR] points3D.bin missing"; exit 1; }

IMG_COUNT=$(find "${DATASET_DIR}/images" -maxdepth 1 \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | wc -l)

if [ "${IMG_COUNT}" -eq 0 ]; then
  echo "[ERROR] no images found in ${DATASET_DIR}/images"
  exit 1
fi

echo "[OK] dataset structure looks valid"
echo "[OK] image count: ${IMG_COUNT}"
EOF

RUN echo "source /opt/conda/etc/profile.d/conda.sh" >> /root/.bashrc && \
    echo "conda activate surfel_splatting" >> /root/.bashrc

CMD ["/bin/bash"]
