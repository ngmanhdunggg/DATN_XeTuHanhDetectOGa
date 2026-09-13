import sys
import os
import cv2
import torch
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # thêm thư mục gốc để import model
try:
    from model.TwinLite import TwinLiteNet
except ImportError:
    print("Lỗi: Không tìm thấy model/TwinLite.py. Hãy kiểm tra lại.")
    sys.exit(1)

class TwinLiteProcessor:
    def __init__(self, weight_path, img_size=(240, 426)):
        self.img_size = img_size
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = TwinLiteNet()
        state_dict = torch.load(weight_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        self.model.to(self.device)
        print(f"[TwinLite] Loaded from {weight_path} on {self.device}")

    def predict(self, img_bgr):
        h, w = img_bgr.shape[:2]
        img_resized = cv2.resize(img_bgr, (self.img_size[1], self.img_size[0]))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        img_tensor = img_tensor.to(self.device)
        with torch.no_grad():
            da_out, ll_out = self.model(img_tensor)
            da_pred = torch.argmax(da_out, dim=1).squeeze(0).cpu().numpy().astype(np.uint8) * 255
        da_mask = cv2.resize(da_pred, (w, h), interpolation=cv2.INTER_NEAREST)
        return da_mask

    @staticmethod
    def overlay_masks(img_bgr, da_mask, da_color=(0, 255, 0), alpha=0.4):
        overlay = img_bgr.copy()
        overlay[da_mask == 255] = da_color
        return cv2.addWeighted(img_bgr, 1 - alpha, overlay, alpha, 0)