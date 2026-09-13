import torch
import cv2
import numpy as np
import os
from model import TwinLite as net

def load_model(weight_path, img_size=(360, 640)):
    model = net.TwinLiteNet()
    model.load_state_dict(torch.load(weight_path, map_location='cpu', weights_only=False))
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()
    return model

def predict(model, img_path, img_size=(360, 640)):
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise FileNotFoundError(f"Không thể đọc ảnh: {img_path}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    
    img_resized = cv2.resize(img_rgb, (img_size[1], img_size[0]))
    img_tensor = torch.from_numpy(img_resized).permute(2,0,1).unsqueeze(0).float() / 255.0
    if torch.cuda.is_available():
        img_tensor = img_tensor.cuda()
    
    with torch.no_grad():
        da_out, ll_out = model(img_tensor)
        da_pred = torch.argmax(da_out, dim=1).squeeze(0).cpu().numpy()
        ll_pred = torch.argmax(ll_out, dim=1).squeeze(0).cpu().numpy()
    
    da_mask = cv2.resize(da_pred, (w, h), interpolation=cv2.INTER_NEAREST)
    ll_mask = cv2.resize(ll_pred, (w, h), interpolation=cv2.INTER_NEAREST)
    
    return da_mask, ll_mask, img_bgr

def overlay_masks(img_bgr, da_mask, ll_mask, da_color=(0, 255, 255), ll_color=(0, 0, 255)):
    """
    Tô màu trực tiếp lên ảnh, không pha trộn (màu đậm).
    da_color: BGR cho driving area (mặc định vàng)
    ll_color: BGR cho lane line (mặc định đỏ)
    """
    result = img_bgr.copy()
    # Tô driving area
    result[da_mask == 1] = da_color
    # Tô lane line (đè lên driving area nếu trùng)
    result[ll_mask == 1] = ll_color
    return result

def main():
    weight_path = './pretrained2/model_299.pth'   # hoặc model tốt nhất bạn có
    if not os.path.exists(weight_path):
        print(f"Không tìm thấy file model: {weight_path}")
        return
    
    print("Loading model...")
    model = load_model(weight_path)
    print("Model loaded.")
    
    img_path = input("Nhập đường dẫn đến ảnh (hoặc kéo thả file vào đây): ").strip().strip('"')
    if not os.path.exists(img_path):
        print(f"File không tồn tại: {img_path}")
        return
    
    print("Đang xử lý...")
    da_mask, ll_mask, img_bgr = predict(model, img_path)
    
    # Overlay màu đậm (không alpha)
    result = overlay_masks(img_bgr, da_mask, ll_mask, da_color=(0, 255, 255), ll_color=(0, 0, 255))
    
    out_name = f"output_{os.path.basename(img_path)}"
    cv2.imwrite(out_name, result)
    print(f"Đã lưu kết quả tại: {out_name}")
    
    cv2.imshow("Segmentation Result", result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()