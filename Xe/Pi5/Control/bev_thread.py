import threading
import time
import cv2
import numpy as np
from datetime import datetime
from config import (
    FRAME_SIZE, BEV_W, BEV_TOP_H, BEV_H, DISPLAY_H,
    PIXEL_PER_METER, TRUC_SAU_Y_PIXEL
)
from utils import get_bev_matrix

class BEVThread(threading.Thread):
    def __init__(self, stop_event, shared_data):
        super().__init__()
        self.stop_event = stop_event
        self.shared = shared_data
        self.M_bev = get_bev_matrix()
        self.bev_w = BEV_W
        self.bev_h = BEV_H
        self.prev_bev = None
        self.prev_time = None
        self.L = 0.34
        self.accum_psi = 0.0
        self.axle_center = (BEV_W // 2, TRUC_SAU_Y_PIXEL)
        print(f"[BEV] Tâm xoay trục sau: {self.axle_center} (pixel) (trong ảnh nội bộ 800px)")

    def compute_delta_pose(self, speed_mps, steer_deg, dt):
        if dt <= 0:
            return 0.0, 0.0
        steer_rad = np.deg2rad(steer_deg)
        if abs(steer_rad) < 1e-6:
            delta_psi = 0.0
        else:
            delta_psi = speed_mps * np.tan(steer_rad) / self.L * dt
        dy = speed_mps * dt
        return delta_psi, dy

    def warp_prev_bev(self, prev_bev, delta_psi_rad, dy_meter):
        if prev_bev is None:
            return None
        h, w = prev_bev.shape[:2]
        angle_deg = -np.rad2deg(delta_psi_rad)
        M = cv2.getRotationMatrix2D(self.axle_center, angle_deg, 1.0)
        dy_pixel = dy_meter * PIXEL_PER_METER
        M[1, 2] += dy_pixel
        warped = cv2.warpAffine(prev_bev, M, (w, h),
                                borderMode=cv2.BORDER_CONSTANT,
                                borderValue=0)
        return warped

    def run(self):
        print("[BEV] Bắt đầu luồng BEV (nội bộ 800px, hiển thị 600px, tâm trục sau)...")
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_SIZE[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_SIZE[1])
        min_interval = 1.0 / 30.0  # MAX_FPS_PROCESS
        last_process_time = 0
        while not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                continue
            now = time.time()
            if now - last_process_time < min_interval:
                continue
            last_process_time = now
            with self.shared['lock']:
                speed = self.shared['speed']
                steer = self.shared['steer']
                self.shared['frame_orig'] = frame.copy()
            top_bev = cv2.warpPerspective(frame, self.M_bev, (BEV_W, BEV_TOP_H))
            if self.prev_bev is not None and self.prev_time is not None:
                dt = now - self.prev_time
                if dt > 0:
                    delta_psi, dy = self.compute_delta_pose(speed, steer, dt)
                    self.accum_psi += delta_psi
                    warped_full = self.warp_prev_bev(self.prev_bev, delta_psi, dy)
                    if warped_full is not None:
                        bev_full = warped_full
                    else:
                        bev_full = np.zeros((BEV_H, BEV_W, 3), dtype=np.uint8)
                else:
                    bev_full = self.prev_bev.copy()
            else:
                bev_full = np.zeros((BEV_H, BEV_W, 3), dtype=np.uint8)
                self.accum_psi = 0.0
            bev_full[0:BEV_TOP_H, :] = top_bev
            self.prev_bev = bev_full.copy()
            self.prev_time = now
            bev_display = bev_full[:DISPLAY_H, :]
            with self.shared['lock']:
                self.shared['bev_frame'] = bev_display
                self.shared['yaw_angle_deg'] = np.rad2deg(self.accum_psi)
                metadata = {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "gps": {
                        "latitude": self.shared.get('lat', 0.0),
                        "longitude": self.shared.get('lon', 0.0),
                        "valid": self.shared.get('gps_valid', False)
                    },
                    "sensors": {
                        "pothole_depth_cm": self.shared.get('pothole_depth', 0.0),
                        "speed_mps": speed,
                        "steering_angle_deg": steer,
                        "battery_percent": self.shared.get('battery', 0.0),
                        "front_distance_cm": self.shared.get('front_distance', -1),
                        "rear_distance_cm": self.shared.get('rear_distance', -1),
                        "yaw_angle_deg": np.rad2deg(self.accum_psi)
                    },
                    "system": {
                        "auto_mode": self.shared.get('auto_mode', False),
                        "frame_width": BEV_W,
                        "frame_height": DISPLAY_H
                    }
                }
                self.shared['metadata'] = metadata
        cap.release()
        print("[BEV] Đã dừng")