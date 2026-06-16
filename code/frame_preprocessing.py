import cv2
import os
from skimage.metrics import structural_similarity as ssim

def variance_of_laplacian(image):
    # 흐림 정도 계산 (높을수록 선명함)
    return cv2.Laplacian(image, cv2.CV_64F).var()

def is_similar(img1, img2, threshold=0.90):
    # 두 이미지의 유사도 비교 (속도를 위해 흑백 + 리사이즈 후 비교 추천)
    # SSIM은 구조적 차이를 잘 잡아냅니다.
    
    # 연산 속도를 위해 작게 줄여서 비교
    h, w = 128, 128
    img1_s = cv2.resize(img1, (w, h))
    img2_s = cv2.resize(img2, (w, h))
    
    score, _ = ssim(img1_s, img2_s, full=True)
    return score > threshold  # 유사도가 threshold보다 높으면 True (중복)

def extract_frames_to(video_path, output_dir, gap=3, blur_threshold=100.0, sim_threshold=0.95):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        return

    frame_count = 0
    saved_count = 0
    last_saved_frame_gray = None
    skip_frames = 0  # 3프레임을 건너뛰기 위한 변수

    print(f"Processing: {video_path}...")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # 총 프레임 수

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 1. 최소 간격 (Gap) 체크: 3프레임마다 하나씩 처리
        if skip_frames > 0:
            skip_frames -= 1
            frame_count += 1
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 2. 흔들림(Blur) 체크
        fm = variance_of_laplacian(gray)
        if fm < blur_threshold and skip_frames < 7:
            print(f"Skipped Frame {frame_count}: Too blurry (Score: {fm:.2f})")
            frame_count += 1
            skip_frames = gap - 1  # 프레임을 건너뛰기 위해 skip_frames 설정
            continue

        # 3. 위치 변화(유사도) 체크
        if last_saved_frame_gray is not None and skip_frames < 7:
            if is_similar(last_saved_frame_gray, gray, threshold=sim_threshold):
                print(f"Skipped Frame {frame_count}: Too similar to previous frame")
                frame_count += 1
                skip_frames = gap - 1  # 프레임을 건너뛰기 위해 skip_frames 설정
                continue

        # 조건 만족 시 저장
        save_path = os.path.join(output_dir, f"frame_{frame_count:05d}.jpg")
        cv2.imwrite(save_path, frame)
        
        last_saved_frame_gray = gray
        saved_count += 1
        
        if saved_count % 10 == 0:
            print(f"Saved {saved_count} frames... (Last Blur Score: {fm:.2f})")

        frame_count += 1
        skip_frames = gap - 1  # 프레임을 건너뛰기 위한 설정

    cap.release()
    print(f"Done! Total extracted: {saved_count} / {total_frames}")


# 실행 예시
# blur_threshold: 이 값은 영상 조명에 따라 다릅니다. (보통 50~150 사이, 밝고 선명하면 100 이상)
# sim_threshold: 0.95 이상이면 거의 같은 위치로 간주하고 패스
#extract_frames('my_foot_video.mp4', './dataset/extracted', gap=3, blur_threshold=100.0, sim_threshold=0.92)