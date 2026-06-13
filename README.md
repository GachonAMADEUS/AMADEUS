<div align="center">

# AMADEUS

### AI-assisted real-scale foot reconstruction for custom shoe-making

From a smartphone foot video to a printable, scale-corrected 3D foot mesh.

<p>
  <img alt="Project status" src="https://img.shields.io/badge/status-documentation%20scaffold-2f80ed?style=for-the-badge">
  <img alt="Pipeline" src="https://img.shields.io/badge/pipeline-video%20to%20STL%2F3MF-111827?style=for-the-badge">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-CUDA%20runtime-2496ED?style=for-the-badge&logo=docker&logoColor=white">
</p>

<p>
  <a href="docs/WORKFLOW.md">Workflow</a>
  ·
  <a href="docs/CAPTURE_GUIDE.md">Capture Guide</a>
  ·
  <a href="docs/REPRODUCIBILITY.md">Reproducibility</a>
  ·
  <a href="docs/OUTPUT_SPEC.md">Output Spec</a>
</p>

</div>

---

## Overview

AMADEUS is an AI-assisted foot morphology analysis and custom shoe-making support system. It reconstructs a user's foot in 3D from a smartphone RGB video, recovers real-world scale using a checkerboard reference, postprocesses the mesh, exports STL/JSON outputs, and validates the result through Bambu Studio slicing and 3D printing.

This repository currently contains the public workflow documentation and project scaffold. The latest implementation source code will be added to this structure after final team integration.

## What AMADEUS Produces

| Input | Core Reconstruction | Output |
| --- | --- | --- |
| Smartphone video of a foot and checkerboard | YOLO/SAM segmentation, COLMAP SfM, 2D Gaussian Splatting, mesh repair, scale correction | Real-scale STL, measurement JSON, processing report, slicer-ready 3MF |

## Workflow At A Glance

```mermaid
flowchart LR
  A["Foot video"] --> B["Frame filtering"]
  B --> C["YOLO/SAM masks"]
  C --> D["COLMAP SfM"]
  D --> E["2DGS mesh"]
  E --> F["Scale correction"]
  F --> G["STL + JSON"]
  G --> H["Bambu validation"]
```

## Why This Matters

| Existing bottleneck | AMADEUS direction |
| --- | --- |
| Expensive 3D foot scanners and LiDAR-specific hardware | Use a broadly available smartphone RGB camera |
| Manual, time-intensive shoe-last production | Automate reconstruction, scaling, and mesh export |
| Weak public foot datasets for this domain | Build a capture and labeling workflow for custom data |
| Unscaled photogrammetry output | Recover real-world scale from an A4 checkerboard |
| Mesh artifacts from single-object reconstruction | Use 2DGS and postprocessing for cleaner foot surfaces |

## Capture Motion

The camera should move slowly around the foot while keeping both the foot and checkerboard visible. See the full [Capture Guide](docs/CAPTURE_GUIDE.md) for details.

<p align="center">
  <img src="docs/assets/capture-orbit-guide.png" alt="Recommended camera orbit around the foot" width="520">
</p>

## Repository Layout

```text
AMADEUS/
  README.md
  docs/
    WORKFLOW.md
    CAPTURE_GUIDE.md
    REPRODUCIBILITY.md
    OUTPUT_SPEC.md
    assets/
      capture-orbit-guide.png
  src/
    .gitkeep
  docker/
    .gitkeep
  data/
    samples/.gitkeep
  models/
    .gitkeep
  outputs/
    .gitkeep
```

## Documentation

| Document | Purpose |
| --- | --- |
| [Workflow](docs/WORKFLOW.md) | Full technical pipeline from video capture to print validation |
| [Capture Guide](docs/CAPTURE_GUIDE.md) | How to record foot/checkerboard videos that work well with COLMAP and 2DGS |
| [Reproducibility Plan](docs/REPRODUCIBILITY.md) | Target runtime, Docker plan, model-weight handling, and execution assumptions |
| [Output Specification](docs/OUTPUT_SPEC.md) | Expected intermediate and final files |

## Core Technologies

| Layer | Technology |
| --- | --- |
| Frame processing | FFmpeg, OpenCV |
| Segmentation | YOLOv11n-seg, SAM |
| Camera pose estimation | COLMAP SfM |
| 3D reconstruction | 2D Gaussian Splatting |
| Mesh postprocessing | Open3D, Trimesh |
| Print validation | Bambu Studio, OrcaSlicer |

## Current Status

```text
Documentation scaffold        done
Repository structure          done
Final pipeline source         pending integration
Docker runtime                pending integration
Model weights                 external release planned
Public demo data              pending privacy review
```

## Open Source Release Plan

1. Publish workflow and execution documentation.
2. Add the final pipeline source code after team integration.
3. Provide a Docker-based reproducible runtime.
4. Link trained YOLO segmentation weights through Hugging Face or release assets.
5. Add public demo input/output samples where privacy and file-size constraints allow.

## Privacy Note

This repository intentionally avoids committing private raw foot videos, personal data, large model weights, and generated print files. Use `data/samples/` only for public demo data.
