import torch
import cv2
import torch.utils.data
import torchvision.transforms as transforms
import numpy as np
import os
import random
import math
import json

def augment_hsv(img, hgain=0.015, sgain=0.7, vgain=0.4):
    """change color hue, saturation, value"""
    r = np.random.uniform(-1, 1, 3) * [hgain, sgain, vgain] + 1
    hue, sat, val = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    dtype = img.dtype
    x = np.arange(0, 256, dtype=np.int16)
    lut_hue = ((x * r[0]) % 180).astype(dtype)
    lut_sat = np.clip(x * r[1], 0, 255).astype(dtype)
    lut_val = np.clip(x * r[2], 0, 255).astype(dtype)
    img_hsv = cv2.merge((cv2.LUT(hue, lut_hue), cv2.LUT(sat, lut_sat), cv2.LUT(val, lut_val))).astype(dtype)
    cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR, dst=img)

def random_perspective(combination, degrees=10, translate=.1, scale=.1, shear=10, perspective=0.0, border=(0, 0)):
    """combination of img transform"""
    img, da_mask, ll_mask = combination
    height = img.shape[0] + border[0] * 2
    width = img.shape[1] + border[1] * 2

    C = np.eye(3)
    C[0, 2] = -img.shape[1] / 2
    C[1, 2] = -img.shape[0] / 2

    P = np.eye(3)
    P[2, 0] = random.uniform(-perspective, perspective)
    P[2, 1] = random.uniform(-perspective, perspective)

    R = np.eye(3)
    a = random.uniform(-degrees, degrees)
    s = random.uniform(1 - scale, 1 + scale)
    R[:2] = cv2.getRotationMatrix2D(angle=a, center=(0, 0), scale=s)

    S = np.eye(3)
    S[0, 1] = math.tan(random.uniform(-shear, shear) * math.pi / 180)
    S[1, 0] = math.tan(random.uniform(-shear, shear) * math.pi / 180)

    T = np.eye(3)
    T[0, 2] = random.uniform(0.5 - translate, 0.5 + translate) * width
    T[1, 2] = random.uniform(0.5 - translate, 0.5 + translate) * height

    M = T @ S @ R @ P @ C
    if (border[0] != 0) or (border[1] != 0) or (M != np.eye(3)).any():
        if perspective:
            img = cv2.warpPerspective(img, M, dsize=(width, height), borderValue=(114, 114, 114))
            da_mask = cv2.warpPerspective(da_mask, M, dsize=(width, height), borderValue=0)
            ll_mask = cv2.warpPerspective(ll_mask, M, dsize=(width, height), borderValue=0)
        else:
            img = cv2.warpAffine(img, M[:2], dsize=(width, height), borderValue=(114, 114, 114))
            da_mask = cv2.warpAffine(da_mask, M[:2], dsize=(width, height), borderValue=0)
            ll_mask = cv2.warpAffine(ll_mask, M[:2], dsize=(width, height), borderValue=0)

    return img, da_mask, ll_mask

class MyDataset(torch.utils.data.Dataset):
    def __init__(self, root_dir, valid=False, train_ratio=0.8, seed=42, transform=None):
        """
        root_dir: thư mục chứa ảnh .jpg và file .json cùng tên (cấu trúc LabelMe)
        valid: False -> trả về tập train, True -> trả về tập val
        train_ratio: tỷ lệ train (mặc định 0.8)
        seed: random seed để chia ổn định
        """
        self.transform = transform
        self.Tensor = transforms.ToTensor()
        self.valid = valid
        self.root_dir = root_dir

        # Lấy danh sách các file ảnh (chỉ .jpg, .png)
        all_images = [f for f in os.listdir(root_dir) if f.lower().endswith(('.jpg', '.png'))]
        # Lọc ra những file có json tương ứng
        all_images = [f for f in all_images if os.path.exists(os.path.join(root_dir, f.replace('.jpg', '.json').replace('.png', '.json')))]

        # Chia train/val
        random.seed(seed)
        indices = list(range(len(all_images)))
        random.shuffle(indices)
        split_idx = int(len(all_images) * train_ratio)
        train_indices = indices[:split_idx]
        val_indices = indices[split_idx:]

        if not valid:
            self.names = [all_images[i] for i in train_indices]
        else:
            self.names = [all_images[i] for i in val_indices]

        print(f"Dataset root: {root_dir}")
        print(f"  Total images: {len(all_images)}")
        print(f"  Train images: {len(train_indices)}")
        print(f"  Val images: {len(val_indices)}")

    def __len__(self):
        return len(self.names)

    def _load_mask_from_json(self, json_path, img_shape):
        """Tạo hai mask (da, ll) từ file JSON LabelMe"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        h, w = img_shape[:2]
        da_mask = np.zeros((h, w), dtype=np.uint8)   # drivable area
        ll_mask = np.zeros((h, w), dtype=np.uint8)   # lane line

        for shape in data.get('shapes', []):
            label = shape['label'].lower()
            points = np.array(shape['points'], dtype=np.int32)
            if len(points) < 3:
                continue

            if 'area' in label:
                cv2.fillPoly(da_mask, [points], 1)
            elif 'lane' in label:
                cv2.fillPoly(ll_mask, [points], 1)
            # Bỏ qua các label khác

        return da_mask, ll_mask

    def __getitem__(self, idx):
        W_, H_ = 640, 360
        img_name = self.names[idx]
        image_path = os.path.join(self.root_dir, img_name)
        json_path = os.path.join(self.root_dir, img_name.replace('.jpg', '.json').replace('.png', '.json'))

        # Đọc ảnh
        image = cv2.imread(image_path)   # BGR
        if image is None:
            raise FileNotFoundError(f"Không đọc được ảnh: {image_path}")

        # Tạo mask từ JSON
        da_mask, ll_mask = self._load_mask_from_json(json_path, image.shape)

        # Augmentation (chỉ khi train)
        if not self.valid:
            if random.random() < 0.5:
                image, da_mask, ll_mask = random_perspective(
                    combination=(image, da_mask, ll_mask),
                    degrees=10,
                    translate=0.1,
                    scale=0.25,
                    shear=0.0
                )
            if random.random() < 0.5:
                augment_hsv(image)
            if random.random() < 0.5:
                image = np.fliplr(image)
                da_mask = np.fliplr(da_mask)
                ll_mask = np.fliplr(ll_mask)

        # Resize
        image = cv2.resize(image, (W_, H_))
        da_mask = cv2.resize(da_mask, (W_, H_), interpolation=cv2.INTER_NEAREST)
        ll_mask = cv2.resize(ll_mask, (W_, H_), interpolation=cv2.INTER_NEAREST)

        # Tạo binary masks 2 kênh giống code cũ (background, foreground)
        # seg_da: kênh 0 = background, kênh 1 = drivable area
        da_bg = (da_mask == 0).astype(np.uint8) * 255
        da_fg = (da_mask == 1).astype(np.uint8) * 255
        seg_da = torch.stack((self.Tensor(da_bg)[0], self.Tensor(da_fg)[0]), 0)

        # seg_ll: kênh 0 = background, kênh 1 = lane line
        ll_bg = (ll_mask == 0).astype(np.uint8) * 255
        ll_fg = (ll_mask == 1).astype(np.uint8) * 255
        seg_ll = torch.stack((self.Tensor(ll_bg)[0], self.Tensor(ll_fg)[0]), 0)

        # Chuyển ảnh: BGR -> RGB, HWC -> CHW, và chuẩn hóa về [0,1]
        image = image[:, :, ::-1].transpose(2, 0, 1)   # RGB, shape (3, H, W)
        image = np.ascontiguousarray(image)
        image_tensor = torch.from_numpy(image).float() / 255.0

        return image_path, image_tensor, (seg_da, seg_ll)