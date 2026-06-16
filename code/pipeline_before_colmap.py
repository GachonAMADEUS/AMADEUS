# 영상 하나를 입력 받아(ex. 태량1) -> 프레임 추출 후 -> Quality Filtering 후 
#   -> dataset/태량1/original_image에 저장 
#   -> 각 이미지에 대해 3DGS에 넣을 발 segentation 이미지를 만들기 위해 
#       yolo - SAM 파이프라인 후 저장 (dataset/태량1/foot_segmentation)

# 사용법: python pipeline_before_colmap -d "태량1.mp4" 
# (동일 폴더 내에 있을 경우)

#나중에 밝기 올리는 로직 추가(사진저장할때)

from pathlib import Path
import argparse
from frame_preprocessing import extract_frames_to
import os, time
import yolo_sam_process4

def do_pipeline():
  parser = argparse.ArgumentParser(
    description=(
    '영상 하나를 입력 받아(ex. 태량1) -> 프레임 추출 후 -> Quality Filtering 후 \n'
    '-> dataset/태량1/original_image에 저장 \n'
    '-> 각 이미지에 대해 3DGS에 넣을 발 segentation 이미지를 만들기 위해 \n'
    '  yolo - SAM 파이프라인 후 저장 (dataset/태량1/foot_segmentation)\n\n'

    '사용법: python pipeline_before_colmap -d "태량1.mp4"\n'
    '(동일 폴더 내에 있을 경우)'
  ))

  parser.add_argument(
    "-p", "--path", required=True,
    help=".mp4 상대경로 혹은 절대경로(ex. 길동.mp4)"
  )
  args = parser.parse_args()
  vid_path = Path(args.path)
  if vid_path:
    print(vid_path)
  else:
    raise RuntimeError("경로에 mp4 없음")
  
  ORIGINAL_IMAGE_DIR = Path("./dataset") / vid_path.stem / "original_image"
  SEGMENTATION_IMAGE_DIR = Path("./dataset") / vid_path.stem / "segmentation"
  ASSET_DIR = Path('./assets')

  print(f"저장할 경로: {ORIGINAL_IMAGE_DIR.absolute()}, {SEGMENTATION_IMAGE_DIR.absolute()}")
  os.makedirs(ORIGINAL_IMAGE_DIR, exist_ok=True)
  os.makedirs(SEGMENTATION_IMAGE_DIR, exist_ok=True)

  do_extract = True
  if any(file.is_file() for file in ORIGINAL_IMAGE_DIR.iterdir()):
    input_does_new_extract = input(f"이미 {ORIGINAL_IMAGE_DIR}에 파일 존재. 다시 extract? (Y/n): ").strip().lower()
    do_extract = True if input_does_new_extract == "y" else False
  if do_extract:
    extract_frames_to(video_path=vid_path, output_dir=ORIGINAL_IMAGE_DIR, blur_threshold=200, sim_threshold=0.92)

  os.makedirs(SEGMENTATION_IMAGE_DIR / "foot", exist_ok=True)
  os.makedirs(SEGMENTATION_IMAGE_DIR / "checkerboard", exist_ok=True)
  os.makedirs(SEGMENTATION_IMAGE_DIR / "both", exist_ok=True)
  # yolo_sam_process4.run_segmentation(ORIGINAL_IMAGE_DIR, (SEGMENTATION_IMAGE_DIR / "foot"), "foot", ASSET_DIR / "best.pt", ASSET_DIR / "sam_vit_h_4b8939.pth", device="cuda")
  # yolo_sam_process4.run_segmentation(ORIGINAL_IMAGE_DIR, (SEGMENTATION_IMAGE_DIR / "checkerboard"), "checkerboard", ASSET_DIR / "best.pt", ASSET_DIR / "sam_vit_h_4b8939.pth", device="cuda")
  yolo_sam_process4.run_segmentation(ORIGINAL_IMAGE_DIR, (SEGMENTATION_IMAGE_DIR / "both"), "both", ASSET_DIR / "best.pt", ASSET_DIR / "sam_vit_h_4b8939.pth", device="cuda")
  






if __name__ == "__main__":
  start_time = time.perf_counter()

  do_pipeline()
  
  end_time = time.perf_counter()
  execution_time = end_time - start_time

  print(f"전체 실행 시간: {execution_time:.6f}초")
