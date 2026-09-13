import cv2
import torch
import numpy as np
from ultralytics import YOLO
from pathlib import Path

def calculate_polygon_area(mask_binary):
    return np.sum(mask_binary > 0)

def draw_results(image, results, conf_threshold=0.5):
    img_out = image.copy()
    h, w = img_out.shape[:2]

    boxes = results[0].boxes
    masks = results[0].masks
    if boxes is None:
        print("Không phát hiện ổ gà nào.")
        return img_out

    for i, box in enumerate(boxes):
        conf = box.conf.item()
        if conf < conf_threshold:
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        cv2.rectangle(img_out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"pothole {conf:.2f}"
        cv2.putText(img_out, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        if masks is not None:
            mask = masks.data[i].cpu().numpy()
            mask = cv2.resize(mask, (w, h))
            mask_binary = (mask > 0.5).astype(np.uint8)
            area_px = calculate_polygon_area(mask_binary)
            print(f"Ổ gà {i+1}: confidence={conf:.2f}, diện tích = {area_px} pixels")
            color_mask = np.zeros_like(img_out, dtype=np.uint8)
            color_mask[mask_binary == 1] = (0, 0, 255)
            img_out = cv2.addWeighted(img_out, 1.0, color_mask, 0.4, 0)

    return img_out

def test_image(model_path, image_path, conf_threshold=0.5, save_result=True):
    if not Path(model_path).exists():
        print(f"❌ Không tìm thấy model: {model_path}")
        return

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️  Device: {device}")
    model = YOLO(model_path)

    results = model(image_path, conf=conf_threshold)

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"❌ Không đọc được ảnh: {image_path}")
        return

    result_img = draw_results(img, results, conf_threshold)

    cv2.imshow("Pothole Detection", result_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    if save_result:
        out_path = f"result_{Path(image_path).stem}.jpg"
        cv2.imwrite(out_path, result_img)
        print(f"💾 Đã lưu kết quả tại: {out_path}")

def test_images_folder(model_path, folder_path, conf_threshold=0.5, result_folder="results"):
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ Thư mục không tồn tại: {folder_path}")
        return

    result_dir = Path(result_folder)
    result_dir.mkdir(exist_ok=True)

    image_exts = ['*.jpg', '*.jpeg', '*.png']
    image_paths = []
    for ext in image_exts:
        image_paths.extend(folder.glob(ext))

    if not image_paths:
        print(f"❌ Không tìm thấy ảnh trong {folder_path}")
        return

    model = YOLO(model_path)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️  Device: {device}")
    print(f"🔍 Tìm thấy {len(image_paths)} ảnh. Bắt đầu xử lý...")

    for img_path in image_paths:
        print(f"\n📷 Xử lý: {img_path.name}")
        results = model(img_path, conf=conf_threshold)
        img = cv2.imread(str(img_path))
        result_img = draw_results(img, results, conf_threshold)
        out_path = result_dir / f"result_{img_path.name}"
        cv2.imwrite(str(out_path), result_img)
        print(f"💾 Đã lưu: {out_path}")

    print(f"\n✅ Hoàn thành. Kết quả lưu trong thư mục '{result_folder}'")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test pothole detection model")
    parser.add_argument("--model", type=str, default="best_pothole_model.pt", help="Đường dẫn model .pt")
    parser.add_argument("--source", type=str, default="C:\\Users\\dung2\\Desktop\\Pothole\\test.jpg", help="Đường dẫn ảnh hoặc thư mục ảnh (mặc định: test.jpg)")
    parser.add_argument("--conf", type=float, default=0.5, help="Ngưỡng confidence")
    parser.add_argument("--save", action="store_true", default=True, help="Lưu ảnh kết quả")
    parser.add_argument("--folder", action="store_true", help="Xử lý cả thư mục (nếu source là thư mục)")

    args = parser.parse_args()

    if args.folder:
        test_images_folder(args.model, args.source, args.conf)
    else:
        test_image(args.model, args.source, args.conf, save_result=args.save)