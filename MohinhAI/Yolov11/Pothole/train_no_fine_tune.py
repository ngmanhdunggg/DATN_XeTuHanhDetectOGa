from ultralytics import YOLO
import torch
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import shutil

def plot_training_metrics(results_dir: Path):
    csv_path = results_dir / "results.csv"
    if not csv_path.exists():
        print(f"⚠️ Không tìm thấy {csv_path}, bỏ qua vẽ đồ thị.")
        return
    
    df = pd.read_csv(csv_path)
    if 'epoch' in df.columns:
        epochs = df['epoch'].values
    else:
        epochs = range(len(df))
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))  # 2x2 = 4 subplot
    
    # 1. Train Losses (góc trên trái)
    train_loss_cols = [col for col in df.columns if 'train/' in col and 'loss' in col]
    for col in train_loss_cols:
        label = col.replace('train/', '')
        axes[0,0].plot(epochs, df[col], label=label)
    axes[0,0].set_title("Training Losses")
    axes[0,0].set_xlabel("Epoch")
    axes[0,0].set_ylabel("Loss")
    axes[0,0].legend()
    axes[0,0].grid(True)
    
    # 2. Validation Losses (góc trên phải)
    val_loss_cols = [col for col in df.columns if 'val/' in col and 'loss' in col]
    for col in val_loss_cols:
        label = col.replace('val/', '')
        axes[0,1].plot(epochs, df[col], label=label)
    axes[0,1].set_title("Validation Losses")
    axes[0,1].set_xlabel("Epoch")
    axes[0,1].set_ylabel("Loss")
    axes[0,1].legend()
    axes[0,1].grid(True)
    
    # 3. Bounding Box Metrics (góc dưới trái)
    bbox_metrics = [col for col in df.columns if 'metrics/' in col and ('(B)' in col or 'mAP50(B)' in col)]
    if not bbox_metrics:
        bbox_metrics = [col for col in df.columns if 'metrics/' in col and 'B' in str(col)]
    for col in bbox_metrics:
        label = col.replace('metrics/', '')
        axes[1,0].plot(epochs, df[col], label=label)
    axes[1,0].set_title("Bounding Box Metrics")
    axes[1,0].set_xlabel("Epoch")
    axes[1,0].set_ylabel("Score")
    axes[1,0].legend()
    axes[1,0].grid(True)
    
    # 4. Mask Metrics (góc dưới phải)
    mask_metrics = [col for col in df.columns if 'metrics/' in col and ('(M)' in col or 'mAP50(M)' in col)]
    if not mask_metrics:
        mask_metrics = [col for col in df.columns if 'metrics/' in col and 'M' in str(col)]
    for col in mask_metrics:
        label = col.replace('metrics/', '')
        axes[1,1].plot(epochs, df[col], label=label)
    axes[1,1].set_title("Mask Metrics")
    axes[1,1].set_xlabel("Epoch")
    axes[1,1].set_ylabel("Score")
    axes[1,1].legend()
    axes[1,1].grid(True)
    
    plt.tight_layout()
    plt.savefig(results_dir / "training_curves.png", dpi=150)
    plt.show()
    print(f"✅ Đã lưu biểu đồ 4-in-1 tại: {results_dir / 'training_curves.png'}")

def train_pothole_model_scratch(data_yaml_path="data.yaml", epochs=100, batch_size=8, imgsz=640):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️  Device: {device}")
    print("🔄 Bắt đầu huấn luyện từ SCRATCH (không dùng pretrained weights)")

    # Khởi tạo model từ file cấu trúc (trọng số ngẫu nhiên)
    # Ultralytics sẽ tự động tải file yaml từ thư viện hoặc từ đường dẫn
    model = YOLO('yolo11n-seg.yaml')   # <- dùng yaml, không dùng .pt

    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        patience=20,
        optimizer='auto',
        lr0=0.01,               # learning rate có thể tăng lên 0.1 nếu muốn
        device=device,
        project='runs/pothole',
        name='yolo11_seg_scratch',
        exist_ok=True,
        pretrained=False,       # đảm bảo không dùng pretrained
        augment=True,
        seed=42,
        verbose=True,
        plots=True,
        save_period=1
    )

    results_dir = Path('runs/pothole/yolo11_seg_scratch')
    plot_training_metrics(results_dir)
    
    best_path = results_dir / 'weights/best.pt'
    if best_path.exists():
        dest = Path('best_pothole_model_scratch.pt')
        shutil.copy(best_path, dest)
        print(f"\n🎉 Model tốt nhất được lưu tại: {dest.resolve()}")
        print(f"📂 Checkpoints từng epoch có trong: {results_dir / 'weights'}")
    else:
        print("❌ Training failed or best model not found.")
    
    return results

if __name__ == "__main__":
    if not Path("data.yaml").exists():
        print("⚠️  data.yaml not found. Run prepare_dataset.py first.")
        exit(1)
    train_pothole_model_scratch()