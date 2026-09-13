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
    
    loss_cols = [col for col in df.columns if 'loss' in col and col not in ['epoch']]
    metric_cols = [col for col in df.columns if 'metrics/' in col]
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    for col in loss_cols:
        label = col.replace('train/', '').replace('val/', '')
        axes[0].plot(epochs, df[col], label=label)
    axes[0].set_title("Training Losses")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].legend()
    axes[0].grid(True)
    
    for col in metric_cols:
        label = col.replace('metrics/', '')
        axes[1].plot(epochs, df[col], label=label)
    axes[1].set_title("Validation Metrics (mAP)")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Score")
    axes[1].legend()
    axes[1].grid(True)
    
    plt.tight_layout()
    plt.savefig(results_dir / "training_curves.png", dpi=150)
    plt.show()
    print(f"✅ Đã lưu biểu đồ tại: {results_dir / 'training_curves.png'}")

def train_pothole_model(data_yaml_path="data.yaml", epochs=100, batch_size=8, imgsz=640):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"🖥️  Device: {device}")
    print("🔄 Fine‑tuning from pretrained yolo11n-seg.pt (có thể đổi sang scratch bằng cách dùng .yaml và pretrained=False)")

    # Fine‑tune (dùng pretrained)
    model = YOLO('yolo11n-seg.pt')   # hoặc 'yolo11n-seg.yaml' + pretrained=False cho scratch

    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        patience=20,
        optimizer='auto',
        lr0=0.01,
        device=device,
        project='runs/pothole',
        name='yolo11_seg_pothole',
        exist_ok=True,
        pretrained=True,
        augment=True,
        seed=42,
        verbose=True,
        plots=True,
        save_period=1   # <--- LƯU CHECKPOINT SAU MỖI EPOCH
    )

    results_dir = Path('runs/pothole/yolo11_seg_pothole')
    plot_training_metrics(results_dir)
    
    best_path = results_dir / 'weights/best.pt'
    if best_path.exists():
        dest = Path('best_pothole_model.pt')
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
    train_pothole_model()