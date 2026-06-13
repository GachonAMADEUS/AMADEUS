# Reproducibility Plan

AMADEUS aims to provide a Docker-based runtime so the same pipeline can be reproduced on another workstation.

## Target Environment

Recommended environment:

- Windows or Linux workstation
- NVIDIA CUDA GPU
- Docker
- NVIDIA Container Toolkit
- Python 3.10+
- Bambu Studio or OrcaSlicer

macOS is not recommended for CUDA-based 2DGS execution. On macOS, use the repository mainly for documentation, lightweight preprocessing, or STL inspection.

## Planned Execution

After final source integration, the target execution flow is:

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

Expected output layout:

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

Large model files should not be committed to Git.

Expected model files:

- Fine-tuned YOLOv11n-seg weights
- SAM checkpoint
- Optional COLMAP vocabulary tree

Possible distribution channels:

- Hugging Face repository
- GitHub Release assets
- Private shared drive for internal test data

The `models/` directory is reserved as the local download location.

## Docker Scope

The Docker runtime is expected to include:

- CUDA runtime/development image
- COLMAP or COLMAP-compatible runtime
- 2D Gaussian Splatting dependencies
- Open3D/Trimesh mesh postprocessing dependencies
- Conda/Anaconda terms acceptance where required by the build environment

## What Should Not Be Committed

- Raw foot videos
- Private dataset images
- Large trained weights
- Generated STL/PLY/3MF outputs
- Python virtual environments
- Docker build cache

## Current Status

This repository currently contains public workflow documentation and a clean scaffold. The latest OOM/COLMAP fixes and final implementation source will be added under the `src/` and `docker/` structure later.
