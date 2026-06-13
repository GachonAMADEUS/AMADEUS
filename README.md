# AMADEUS

AI 기반 족적 형태 분석 및 수제화 제작 보조 시스템입니다.

AMADEUS는 스마트폰으로 촬영한 발 영상과 체커보드를 입력으로 받아 발 형상을 3D로 재구성하고, 실제 크기 스케일 보정, 메쉬 후처리, STL/JSON 산출, Bambu Studio 기반 3D 프린팅 검증까지 이어지는 end-to-end 워크플로우를 목표로 합니다.

> 현재 저장소는 공개용 워크플로우와 실행 문서를 먼저 정리한 상태입니다. 최신 구현 소스코드는 이후 이 구조에 맞춰 반영할 예정입니다.

## Pipeline

```text
Smartphone foot video
-> Frame extraction and quality filtering
-> YOLOv11n-seg foot/checkerboard segmentation
-> SAM mask refinement
-> COLMAP SfM camera pose estimation and sparse point cloud
-> 2D Gaussian Splatting reconstruction
-> 2DGS PLY postprocessing
-> A4 checkerboard based scale factor estimation
-> Real-size mesh scaling and measurements
-> Watertight STL/JSON export
-> Bambu Studio slicing and print validation
```

## Repository Layout

```text
AMADEUS/
  README.md
  docs/
    WORKFLOW.md              # 전체 기술 워크플로우
    CAPTURE_GUIDE.md         # 발/체커보드 촬영 가이드
    REPRODUCIBILITY.md       # Docker, 모델, 실행 재현 계획
    OUTPUT_SPEC.md           # 중간/최종 산출물 정의
  src/
    .gitkeep                 # 최종 파이프라인 코드 반영 예정
  docker/
    .gitkeep                 # 2DGS/COLMAP 실행 환경 반영 예정
  data/
    samples/.gitkeep         # 공개 가능한 샘플 입력만 배치
  models/
    .gitkeep                 # 모델 파일은 직접 커밋하지 않음
  outputs/
    .gitkeep                 # 실행 결과는 Git 추적 제외
```

## Main Documents

- [전체 워크플로우](docs/WORKFLOW.md)
- [촬영 및 데이터 가이드](docs/CAPTURE_GUIDE.md)
- [재현 환경 및 배포 계획](docs/REPRODUCIBILITY.md)
- [산출물 명세](docs/OUTPUT_SPEC.md)

## Core Technologies

- COLMAP: SfM, camera pose estimation, sparse point cloud generation
- 2D Gaussian Splatting: disk-based Gaussian representation and mesh reconstruction
- YOLOv11n-seg + SAM: foot/checkerboard segmentation and pixel-level mask refinement
- Open3D / Trimesh: mesh scaling, cleanup, hole filling, watertight postprocessing
- Bambu Studio: slicing and 3D printing validation

## Open Source Release Plan

1. Publish workflow and execution documents.
2. Add final pipeline source code after team integration.
3. Provide Docker-based reproducible environment.
4. Link trained YOLO segmentation weights through Hugging Face or release artifacts.
5. Add sample input/output demo where privacy and file-size constraints allow.

## Privacy Note

This repository intentionally avoids committing private raw foot videos, personal data, large model weights, and generated print files. Use `data/samples/` only for public demo data.
