import json
import os
import shutil
import random
from pathlib import Path

# ========== CẤU HÌNH (ĐÃ SỬA) ==========
BASE_DIR = Path(r"C:\Users\dung2\Desktop\Pothole")
IMG_DIR = BASE_DIR / "data"               # ← đã đổi từ img2 thành data
OUTPUT_DIR = BASE_DIR / "dataset_yolo"
TRAIN_RATIO = 0.8
RANDOM_SEED = 42

CLASS_MAPPING = {"pothole": 0}

TRAIN_IMGS = OUTPUT_DIR / "images/train"
VAL_IMGS   = OUTPUT_DIR / "images/val"
TRAIN_LBLS = OUTPUT_DIR / "labels/train"
VAL_LBLS   = OUTPUT_DIR / "labels/val"

def labelme_json_to_yolo_seg(json_path, output_txt_path, img_w, img_h):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'imageWidth' in data:
        img_w = data['imageWidth']
        img_h = data['imageHeight']

    lines = []
    for shape in data['shapes']:
        label = shape['label']
        if label not in CLASS_MAPPING:
            continue
        class_id = CLASS_MAPPING[label]
        points = shape['points']

        norm_points = []
        for x, y in points:
            nx = x / img_w
            ny = y / img_h
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))
            norm_points.extend([nx, ny])

        line = f"{class_id} " + " ".join(f"{p:.6f}" for p in norm_points)
        lines.append(line)

    if not lines:
        return False

    with open(output_txt_path, 'w') as f:
        f.write("\n".join(lines))
    return True

def prepare_dataset():
    for d in [TRAIN_IMGS, VAL_IMGS, TRAIN_LBLS, VAL_LBLS]:
        d.mkdir(parents=True, exist_ok=True)

    # Tìm tất cả cặp file ảnh/json từ 1..98
    file_pairs = []
    for i in range(1, 99):
        img_path = IMG_DIR / f"{i}.jpg"
        json_path = IMG_DIR / f"{i}.json"
        if img_path.exists() and json_path.exists():
            file_pairs.append((img_path, json_path))

    if not file_pairs:
        print("❌ Không tìm thấy cặp ảnh/JSON nào trong thư mục 'data'.")
        return False

    print(f"✅ Tìm thấy {len(file_pairs)} cặp ảnh và JSON (1..98).")

    random.seed(RANDOM_SEED)
    random.shuffle(file_pairs)

    split_idx = int(len(file_pairs) * TRAIN_RATIO)
    train_pairs = file_pairs[:split_idx]
    val_pairs   = file_pairs[split_idx:]

    def process_pair(pair_list, target_img_dir, target_lbl_dir):
        for img_path, json_path in pair_list:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            img_w = data.get('imageWidth', 640)
            img_h = data.get('imageHeight', 480)

            dest_img = target_img_dir / img_path.name
            dest_txt = target_lbl_dir / f"{img_path.stem}.txt"

            shutil.copy2(img_path, dest_img)
            ok = labelme_json_to_yolo_seg(json_path, dest_txt, img_w, img_h)
            if not ok:
                print(f"⚠️  {json_path.name} không có nhãn 'pothole' -> bỏ qua file txt")

    print("🔄 Xử lý train...")
    process_pair(train_pairs, TRAIN_IMGS, TRAIN_LBLS)
    print("🔄 Xử lý val...")
    process_pair(val_pairs, VAL_IMGS, VAL_LBLS)

    # Tạo data.yaml
    data_yaml = {
        'path': str(OUTPUT_DIR.resolve()),
        'train': 'images/train',
        'val': 'images/val',
        'nc': len(CLASS_MAPPING),
        'names': list(CLASS_MAPPING.keys())
    }
    yaml_path = BASE_DIR / 'data.yaml'
    with open(yaml_path, 'w') as f:
        import yaml
        yaml.dump(data_yaml, f, default_flow_style=False)

    print(f"\n✅ Chuẩn bị dữ liệu xong!")
    print(f"   Train: {len(train_pairs)} ảnh")
    print(f"   Val  : {len(val_pairs)} ảnh")
    print(f"   File cấu hình: {yaml_path}")
    return yaml_path

if __name__ == "__main__":
    prepare_dataset()