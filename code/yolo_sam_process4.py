# 추가할 것: 객체검출못한 이미지: 오리지날 이미지도 삭제
# Finetuning 다시할지, 기존 best.pt 에 추가로 finetuning할지
import cv2
import torch
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from segment_anything import sam_model_registry, SamPredictor

CLASS_COLORS = {
    "foot": (0, 255, 0),
    "checkerboard": (255, 0, 0),
}

def draw_yolo_seg_result(image_bgr, boxes_xyxy, class_names, masks_uint8):
    """YOLO 박스와 SAM segmentation 결과를 원본 이미지 위에 시각화합니다."""
    overlay = image_bgr.copy()
    result_image = image_bgr.copy()

    for box, class_name, mask in zip(boxes_xyxy, class_names, masks_uint8):
        color = CLASS_COLORS.get(class_name, (0, 255, 255))
        color_layer = np.zeros_like(image_bgr, dtype=np.uint8)
        color_layer[mask > 0] = color
        overlay = cv2.addWeighted(overlay, 1.0, color_layer, 0.45, 0)

    result_image = cv2.addWeighted(result_image, 0.55, overlay, 0.45, 0)

    for box, class_name, mask in zip(boxes_xyxy, class_names, masks_uint8):
        color = CLASS_COLORS.get(class_name, (0, 255, 255))
        x1, y1, x2, y2 = box.astype(int)
        cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 3)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(result_image, contours, -1, color, 2)

        label = class_name
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        label_y = max(y1, text_h + baseline + 4)
        cv2.rectangle(
            result_image,
            (x1, label_y - text_h - baseline - 6),
            (x1 + text_w + 8, label_y + 2),
            color,
            -1,
        )
        cv2.putText(
            result_image,
            label,
            (x1 + 4, label_y - baseline - 2),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    return result_image

def run_segmentation(
    input_dir: str | Path,
    output_dir: str | Path,
    target_mode: str = 'both',
    yolo_model_path: str = "best.pt",
    sam_checkpoint_path: str = "sam_vit_h_4b8939.pth",
    mask_expand_pixels: int = 3,
    device: str = None
):
    """
    YOLO와 SAM을 사용하여 지정된 폴더의 이미지를 세그멘테이션합니다.

    Args:
        input_dir (str | Path): 입력 이미지가 있는 폴더 경로
        output_dir (str | Path): 결과 이미지를 저장할 폴더 경로
        target_mode (str): 'foot', 'checkerboard', 'both' 중 하나
        yolo_model_path (str): YOLO 모델 파일 경로 (.pt)
        sam_checkpoint_path (str): SAM 체크포인트 파일 경로 (.pth)
        mask_expand_pixels (int): SAM 마스크를 팽창시킬 픽셀 수
        device (str, optional): 'cuda' 또는 'cpu'. None일 경우 자동 감지.
    """
    
    # 1. 경로 및 디바이스 설정
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    yolo_seg_path = output_path / "yolo_seg"
    yolo_seg_path.mkdir(parents=True, exist_ok=True)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"[Info] Device: {device}")
    print(f"[Info] Input: {input_path}")
    print(f"[Info] Output: {output_path}")
    print(f"[Info] Mode: {target_mode}")

    # 2. 모델 로드 (YOLO & SAM)
    print(">> 모델 로딩 중...")
    try:
        yolo_model = YOLO(yolo_model_path)
        sam = sam_model_registry["vit_h"](checkpoint=sam_checkpoint_path)
        sam.to(device=device)
        sam_predictor = SamPredictor(sam)
    except Exception as e:
        print(f"[Error] 모델 로드 실패: {e}")
        return

    # YOLO 클래스 이름 매핑
    reversed_names = {v: k for k, v in yolo_model.names.items()}
    
    # 검출 대상 ID 설정
    if target_mode == 'both':
        required_target_names = ["foot", "checkerboard"]
    else:
        required_target_names = [target_mode]

    target_class_ids = []
    class_id_by_name = {}
    if "foot" in required_target_names:
        fid = reversed_names.get("foot")
        if fid is not None:
            target_class_ids.append(fid)
            class_id_by_name["foot"] = fid
    
    if "checkerboard" in required_target_names:
        cid = reversed_names.get("checkerboard")
        if cid is not None:
            target_class_ids.append(cid)
            class_id_by_name["checkerboard"] = cid
    
    missing_model_classes = [
        name for name in required_target_names
        if name not in class_id_by_name
    ]
    if missing_model_classes:
        print(f"[Error] YOLO 모델에서 클래스를 찾을 수 없습니다: {', '.join(missing_model_classes)}")
        return

    # 3. 이미지 처리
    image_files = list(input_path.glob("*.jpg"))
    print(f">> 총 {len(image_files)}장의 이미지 처리를 시작합니다.")

    success_count = 0
    yolo_seg_count = 0

    for ith, img_file in enumerate(image_files):
        filename = img_file.name
        
        # 이미지 읽기
        image_bgr = cv2.imread(str(img_file))
        if image_bgr is None:
            continue
        
        img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        # YOLO 예측
        results = yolo_model.predict(str(img_file), verbose=False)
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            print(f"  [Skip] 검출된 객체 없음: {filename}")
            continue
        
        result = results[0]
        boxes_xyxy = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)

        # 타겟 클래스 필터링
        missing_classes = []
        if target_mode == 'both':
            missing_classes = [
                name for name, class_id in class_id_by_name.items()
                if not np.any(classes == class_id)
            ]

        mask_indices = np.isin(classes, target_class_ids)
        target_boxes = boxes_xyxy[mask_indices]
        target_classes = classes[mask_indices]
        class_name_by_id = {class_id: name for name, class_id in class_id_by_name.items()}
        target_class_names = [
            class_name_by_id[int(class_id)]
            for class_id in target_classes
        ]

        if len(target_boxes) == 0:
            print(f"  [Skip] 타겟({target_mode}) 없음: {filename}")
            continue

        # SAM 예측
        target_boxes_torch = torch.tensor(target_boxes, device=device)
        sam_predictor.set_image(img_rgb)
        transformed_boxes = sam_predictor.transform.apply_boxes_torch(
            target_boxes_torch, img_rgb.shape[:2]
        )

        with torch.no_grad():
            masks, scores, _ = sam_predictor.predict_torch(
                point_coords=None,
                point_labels=None,
                boxes=transformed_boxes,
                multimask_output=True,
            )

        if masks is None or masks.shape[0] != len(target_boxes):
            print(f"  [Skip] SAM 마스크 생성 실패: {filename}")
            continue

        # 최고 점수 마스크 선택 및 병합
        best_mask_per_box = []
        for i in range(masks.shape[0]):
            best_idx = torch.argmax(scores[i])
            best_mask_per_box.append(masks[i][best_idx])
        
        best_masks = torch.stack(best_mask_per_box, dim=0)
        per_box_masks = (best_masks > 0.5).cpu().numpy().astype(np.uint8) * 255
        combined_mask = torch.any(best_masks > 0.5, dim=0) # (H, W)
        
        final_mask = (combined_mask.cpu().numpy().astype(np.uint8)) * 255
        if not np.any(final_mask):
            print(f"  [Skip] SAM 유효 마스크 없음: {filename}")
            continue

        if mask_expand_pixels > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (mask_expand_pixels, mask_expand_pixels)
            )
            final_mask = cv2.dilate(final_mask, kernel, iterations=1)

        yolo_seg_image = draw_yolo_seg_result(
            image_bgr,
            target_boxes,
            target_class_names,
            per_box_masks,
        )
        yolo_seg_save_path = yolo_seg_path / filename
        cv2.imwrite(str(yolo_seg_save_path), yolo_seg_image)
        yolo_seg_count += 1

        if missing_classes:
            print(f"  [Skip] YOLO 타겟 누락({', '.join(missing_classes)}): {filename}")
            continue

        # 배경 제거 및 저장
        clean_image = cv2.bitwise_and(image_bgr, image_bgr, mask=final_mask)
        
        save_path = output_path / filename
        cv2.imwrite(str(save_path), clean_image)
        success_count += 1
        
        # 진행 상황 (옵션)
        if (ith + 1) % 10 == 0:
            print(f"  ... {ith + 1}/{len(image_files)} 완료")

    print(f">> 작업 완료. {success_count}/{len(image_files)}장 저장됨.")
    print(f">> YOLO/SAM 확인 이미지 {yolo_seg_count}/{len(image_files)}장 저장됨: {yolo_seg_path}")

# 이 파일 자체를 실행할 때 테스트용 코드
if __name__ == "__main__":
    # 테스트 실행
    run_segmentation(
        input_dir="태량_original",
        output_dir="태량_segmented",
        target_mode="both"
    )
