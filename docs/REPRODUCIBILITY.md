# Reproducibility Plan

AMADEUS는 다른 컴퓨터에서도 같은 파이프라인을 재현할 수 있도록 Docker 기반 실행 환경을 목표로 합니다.

## Target Environment

권장 환경:

- Windows or Linux workstation
- NVIDIA CUDA GPU
- Docker
- NVIDIA Container Toolkit
- Python 3.10+
- Bambu Studio or OrcaSlicer

macOS는 CUDA 기반 2DGS Docker 실행에 적합하지 않습니다. macOS에서는 문서 작업, lightweight preprocessing, STL inspection 정도만 권장합니다.

## Planned Execution

최종 코드 통합 후 목표 실행 방식:

```bash
git clone https://github.com/GachonAMADEUS/AMADEUS.git
cd AMADEUS
```

```bash
docker build -t amadeus-2dgs docker/2dgs
```

```bash
python src/pipeline.py --input data/samples/foot_video.mp4
```

예상 결과:

```text
outputs/
  frames/
  segmentation/
  colmap/
  2dgs/
  mesh/
  final_foot.stl
  measurements.json
  report.json
  sliced_project.3mf
```

## Model Weights

대용량 모델 파일은 Git에 직접 커밋하지 않습니다.

예상 파일:

- YOLOv11n-seg fine-tuned weights
- SAM checkpoint
- optional COLMAP vocab tree

배포 방식:

- Hugging Face repository
- GitHub Release assets
- private shared drive for internal test data

`models/` 폴더는 모델을 내려받는 위치로만 사용합니다.

## Docker Scope

Docker 환경에는 다음을 포함할 예정입니다.

- CUDA runtime/devel image
- COLMAP or COLMAP-compatible runtime
- 2D Gaussian Splatting dependencies
- Open3D/Trimesh mesh postprocessing dependencies
- Anaconda/conda terms acceptance where required by build environment

## What Should Not Be Committed

- raw foot videos
- private dataset images
- trained weights if too large or license-restricted
- generated STL/PLY/3MF outputs
- Python virtual environments
- Docker build cache

## Current Status

이 저장소에는 현재 PDF 기반 공개 워크플로우 문서를 먼저 정리했습니다. 최신 OOM/COLMAP 수정본은 이후 `src/`와 `docker/` 구조에 맞춰 반영합니다.
