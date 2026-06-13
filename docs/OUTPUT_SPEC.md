# Output Specification

이 문서는 AMADEUS 파이프라인의 중간 산출물과 최종 산출물을 정의합니다.

## Input

```text
data/
  samples/
    foot_video.mp4
```

필수 입력:

- foot video
- checkerboard visible in the same scene

선택 입력:

- pre-extracted frames
- precomputed COLMAP sparse model
- precomputed 2DGS PLY

## Intermediate Outputs

### Frames

```text
outputs/frames/
  frame_0000.jpg
  frame_0001.jpg
```

설명:

- 영상에서 추출된 대표 프레임
- blur/overexposure/motion quality filtering 적용

### Segmentation

```text
outputs/segmentation/
  foot/
  checkerboard/
  both/
```

설명:

- YOLOv11n-seg와 SAM 후처리 결과
- foot-only, checkerboard-only, combined mask를 분리 저장

### COLMAP

```text
outputs/colmap/
  database.db
  sparse/0/
    cameras.bin
    images.bin
    points3D.bin
```

설명:

- 카메라 포즈와 sparse point cloud
- 2DGS 학습의 초기 입력

### 2DGS

```text
outputs/2dgs/
  reconstruction.ply
  mesh.ply
```

설명:

- 2D Gaussian Splatting 학습 결과
- mesh extraction 결과

### Scale Debug

```text
outputs/scale/
  projected_checkerboard.png
  debug_lines.png
  scale_factor.json
```

설명:

- checkerboard 기반 scale factor 계산 결과
- 디버깅 이미지와 계산 값 저장

## Final Outputs

```text
outputs/final/
  final_foot.stl
  final_foot_scaled.stl
  measurements.json
  report.json
  report.txt
  sliced_project.3mf
```

### `final_foot.stl`

후처리된 발 mesh입니다.

요구 조건:

- foot-only geometry
- major floating artifacts removed
- repair/simplify applied where needed

### `final_foot_scaled.stl`

실제 mm 단위로 scale factor가 적용된 STL입니다.

요구 조건:

- checkerboard 기반 scale correction 적용
- Bambu Studio/OrcaSlicer에서 로딩 가능

### `measurements.json`

발 치수와 mesh metadata를 저장합니다.

예상 필드:

```json
{
  "scale_factor": 1.0,
  "foot_length_mm": 0.0,
  "foot_width_mm": 0.0,
  "instep_height_mm": 0.0,
  "bounding_box_mm": [0.0, 0.0, 0.0],
  "triangle_count": 0,
  "watertight": false
}
```

### `sliced_project.3mf`

Bambu Studio 또는 OrcaSlicer에서 slicing한 프로젝트 파일입니다.

주의:

- 실제 Bambu Cloud upload는 별도 단계입니다.
- printer/profile setting은 실행 환경에 따라 달라질 수 있습니다.
