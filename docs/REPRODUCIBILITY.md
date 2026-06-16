# Reproducibility Plan

AMADEUS provides the current runnable CLI pipeline under `code/`. The heaviest 2DGS stage runs through a CUDA Docker image, while host-side preprocessing, COLMAP, postprocessing, scaling, and slicing use local runtime tools.

## Target Environment

Recommended environment:

- Windows or Linux workstation
- NVIDIA CUDA GPU
- Docker
- NVIDIA Container Toolkit
- Python 3.10+
- COLMAP CLI
- OrcaSlicer CLI, unless slicing is skipped

macOS is not recommended for CUDA-based 2DGS execution. On macOS, use the repository mainly for documentation, lightweight preprocessing, or STL inspection.

## Execution

Clone the repository and run the pipeline from `code/`:

```bash
git clone https://github.com/GachonAMADEUS/AMADEUS.git
cd AMADEUS
```

```bash
cd code
pip install -r requirements.txt
```

```bash
./run_pipeline.sh "foot_video.mp4"
```

The script builds the 2DGS Docker image from `code/Dockerfile` if the expected local image tag is missing. Use `SKIP_SLICING=1` to run without OrcaSlicer.

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

## Runtime Assets

Large model files should not be committed to Git.

Expected model files:

- `code/assets/best.pt`
- `code/assets/sam_vit_h_4b8939.pth`
- `code/vocab_tree_flickr100K_words32K.bin`
- `code/tools/orca/...` for OrcaSlicer CLI support

Possible distribution channels:

- Hugging Face repository
- GitHub Release assets
- Private shared drive for internal test data

The top-level `models/` directory remains reserved for shared release assets, but the current `run_pipeline.sh` expects its runtime files under `code/`.

## Docker Scope

The 2DGS Docker runtime includes:

- CUDA runtime/development image
- 2D Gaussian Splatting dependencies
- Conda/Anaconda terms acceptance where required by the build environment

COLMAP, host Python dependencies, and OrcaSlicer remain host-side requirements for the current CLI flow.

## What Should Not Be Committed

- Raw foot videos
- Private dataset images
- Large trained weights
- Generated STL/PLY/3MF outputs
- Python virtual environments
- Docker build cache

## Current Status

This repository currently contains public workflow documentation, the web runner scaffold, and the runnable CLI implementation under `code/`.
