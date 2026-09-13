import torch
import os
from model import TwinLite as net

# Kích thước đầu vào cho RPi5 (nhỏ hơn để nhanh hơn)
INPUT_H, INPUT_W = 240, 426   # Có thể thử 160x284 nếu cần nhanh hơn

model = net.TwinLiteNet()
# Load weight, bỏ qua prefix 'module.' nếu có
state_dict = torch.load('pretrained3/model_249.pth', map_location='cpu')
new_state_dict = {k[7:] if k.startswith('module.') else k: v for k, v in state_dict.items()}
model.load_state_dict(new_state_dict, strict=False)
model.eval()

dummy = torch.randn(1, 3, INPUT_H, INPUT_W)
# Đường dẫn file onnx bạn muốn lưu
output_onnx_path = 'pretrained_pi/model_249p.onnx'

# Kiểm tra nếu thư mục chưa có thì tự động tạo
output_dir = os.path.dirname(output_onnx_path)
if output_dir and not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Đã tạo thư mục: {output_dir}")
torch.onnx.export(
    model, dummy, f"pretrained_pi/model_249p.onnx",
    input_names=['input'], output_names=['da', 'll'],
    dynamic_axes={'input': {0: 'batch'}},
    opset_version=11
)
print(f"Export thành công: pretrained_pi/model_249p.onnx")