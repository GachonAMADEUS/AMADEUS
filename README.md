# AMADEUS

AMADEUS is an AI-assisted foot morphology analysis and custom shoe-making support system.

The project aims to reconstruct a user's foot in 3D from a smartphone RGB video, recover real-world scale using a checkerboard reference, postprocess the mesh, export STL/JSON outputs, and validate the result through Bambu Studio slicing and 3D printing.

> This repository currently contains the public workflow documentation and repository scaffold. The latest implementation source code will be added to this structure after final team integration.

## Pipeline

```text
Smartphone foot video
-> Frame extraction and quality filtering
-> YOLOv11n-seg foot/checkerboard segmentation
-> SAM mask refinement
-> COLMAP SfM camera pose estimation and sparse point cloud generation
-> 2D Gaussian Splatting reconstruction
-> 2DGS PLY postprocessing
-> A4 checkerboard based scale factor estimation
-> Real-size mesh scaling and measurement
-> Watertight STL/JSON export
-> Bambu Studio slicing and print validation
```

## Repository Layout

```text
AMADEUS/
  README.md
  docs/
    WORKFLOW.md              # Full technical workflow
    CAPTURE_GUIDE.md         # Foot/checkerboard capture guide
    REPRODUCIBILITY.md       # Docker, model, and execution plan
    OUTPUT_SPEC.md           # Intermediate and final output definitions
    assets/
      capture-orbit-guide.png
  src/
    .gitkeep                 # Final pipeline code will be added here
  docker/
    .gitkeep                 # COLMAP/2DGS Docker environment will be added here
  data/
    samples/.gitkeep         # Public demo samples only
  models/
    .gitkeep                 # Model weights are not committed directly
  outputs/
    .gitkeep                 # Local generated outputs are ignored
```

## Main Documents

- [Workflow](docs/WORKFLOW.md)
- [Capture Guide](docs/CAPTURE_GUIDE.md)
- [Reproducibility Plan](docs/REPRODUCIBILITY.md)
- [Output Specification](docs/OUTPUT_SPEC.md)

## Core Technologies

- COLMAP: SfM, camera pose estimation, and sparse point cloud generation
- 2D Gaussian Splatting: disk-based Gaussian representation and mesh reconstruction
- YOLOv11n-seg + SAM: foot/checkerboard segmentation and pixel-level mask refinement
- Open3D / Trimesh: mesh scaling, cleanup, hole filling, and watertight postprocessing
- Bambu Studio: slicing and 3D printing validation

## Open Source Release Plan

1. Publish workflow and execution documentation.
2. Add the final pipeline source code after team integration.
3. Provide a Docker-based reproducible runtime.
4. Link trained YOLO segmentation weights through Hugging Face or release assets.
5. Add public demo input/output samples where privacy and file-size constraints allow.

## Privacy Note

This repository intentionally avoids committing private raw foot videos, personal data, large model weights, and generated print files. Use `data/samples/` only for public demo data.
