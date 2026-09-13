import threading
import time
import cv2
import numpy as np
import onnxruntime as ort
from config import (
    MODEL_PATH, FRAME_SIZE, INPUT_SIZE, MIN_AREA,
    NUM_SCAN_LINES, Y_START_RATIO, Y_END_RATIO, MAX_CENTER_SHIFT,
    FRONT_SAFE_DISTANCE
)
from utils import get_bird_eye_matrix, filter_noise, compute_center_per_row, filter_outlier_centers
from serial_manager import SerialManager
from motion_control import MotionController
from ui_manager import UIManager

class AIThread(threading.Thread):
    def __init__(self, stop_event, shared_data):
        super().__init__()
        self.stop_event = stop_event
        self.shared = shared_data
        self.serial = SerialManager()
        self.motion = MotionController()
        self.ui = UIManager()

    def run(self):
        print("[AI] Khởi tạo AI model...")
        session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        M, M_inv = get_bird_eye_matrix()
        h, w = FRAME_SIZE[1], FRAME_SIZE[0]
        y_positions = np.linspace(int(h * Y_START_RATIO), int(h * Y_END_RATIO), NUM_SCAN_LINES, dtype=int)
        weights = np.linspace(1.0, 0.3, NUM_SCAN_LINES)
        if not self.serial.connect():
            return
        self.ui.initialize()
        last_ai_time = 0
        min_interval = 1.0 / 30.0
        while not self.stop_event.is_set():
            # Đọc phản hồi từ ESP
            self.serial.read_feedback(self.shared)
            now = time.time()
            if now - last_ai_time < min_interval:
                time.sleep(0.001)
                continue
            last_ai_time = now
            # Lấy dữ liệu từ shared_data
            with self.shared['lock']:
                frame = self.shared['frame_orig']
                if frame is None:
                    continue
                speed = self.shared['speed']
                steer = self.shared['steer']
                front = self.shared['front_distance']
                auto_mode = self.shared['auto_mode']
            # Kiểm tra vật cản phía trước
            front_obstacle = False
            if not np.isinf(front) and not np.isnan(front):
                if 0.01 < front < FRONT_SAFE_DISTANCE:
                    front_obstacle = True
            center_points = []
            final_speed = 0.0
            final_steer = 0.0

            if auto_mode and not front_obstacle:
                # Xử lý ảnh và AI
                img = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), INPUT_SIZE)
                img = (img.astype(np.float32) / 255.0).transpose(2, 0, 1)
                img = np.expand_dims(img, axis=0)
                outputs = session.run(None, {session.get_inputs()[0].name: img})
                da_pred = np.argmax(outputs[0], axis=1).squeeze().astype(np.uint8) * 255
                ll_pred = np.argmax(outputs[1], axis=1).squeeze().astype(np.uint8) * 255

                da_mask = cv2.resize(da_pred, FRAME_SIZE, interpolation=cv2.INTER_NEAREST)
                ll_mask = cv2.resize(ll_pred, FRAME_SIZE, interpolation=cv2.INTER_NEAREST)

                clean_da = filter_noise(da_mask, MIN_AREA)
                clean_ll = filter_noise(ll_mask, MIN_AREA)

                has_da = np.sum(clean_da > 0) > 1000
                if not has_da:
                    final_speed = 0.0
                    final_steer = 0.0
                    self.motion.boost_state = 0
                    self.motion.stall_start_time = None
                else:
                    warped_da = cv2.warpPerspective(clean_da, M, FRAME_SIZE)
                    warped_ll = cv2.warpPerspective(clean_ll, M, FRAME_SIZE)

                    centers = []
                    valid_weights = []
                    mid_w = warped_ll.shape[1] // 2
                    center_points = []
                    for idx, y in enumerate(y_positions):
                        c, valid = compute_center_per_row(y, warped_ll, warped_da, mid_w)
                        if valid:
                            centers.append(c)
                            center_points.append((int(c), int(y)))
                            valid_weights.append(weights[idx])

                    if len(center_points) >= 2:
                        center_points = filter_outlier_centers(center_points, MAX_CENTER_SHIFT)

                    if len(center_points) == 0:
                        final_speed = 0.0
                        final_steer = 0.0
                        self.motion.boost_state = 0
                        self.motion.stall_start_time = None
                    else:
                        total_error = 0.0
                        total_weight = 0.0
                        for c, wgt in zip(centers, valid_weights):
                            error = c - mid_w
                            total_error += error * wgt
                            total_weight += wgt
                        current_error = total_error / total_weight

                        cmd_steer = self.motion.compute_pid(current_error)
                        cmd_speed = self.motion.compute_speed_from_steer(cmd_steer)
                        final_speed = self.motion.update_boost(speed, cmd_speed, cmd_steer, time.time())
                        final_steer = cmd_steer

                # Ghi lại lệnh và trạng thái boost vào shared_data
                with self.shared['lock']:
                    self.shared['cmd_speed'] = final_speed
                    self.shared['cmd_steer'] = final_steer
                    self.shared['boost_state'] = self.motion.get_boost_state()

                self.serial.send_command(final_speed, final_steer)
            else:
                # Chế độ manual hoặc có vật cản
                self.serial.send_command(0.0, 0.0)
                with self.shared['lock']:
                    self.shared['cmd_speed'] = 0.0
                    self.shared['cmd_steer'] = 0.0
                    self.shared['boost_state'] = 0
                self.motion.boost_state = 0
                self.motion.stall_start_time = None
                final_speed = 0.0
                final_steer = 0.0

            # Hiển thị
            battery = self.shared.get('battery', 0.0)
            boost_state = self.motion.get_boost_state()
            display_frame = self.ui.draw_info(frame, auto_mode, center_points, M_inv,
                                              speed, steer, final_speed, final_steer,
                                              front, battery, boost_state)
            self.ui.show(display_frame)

            key = self.ui.get_key()
            if key == ord('q') or key == 27:
                self.stop_event.set()

            # Đọc lại feedback một lần nữa để cập nhật nhanh
            self.serial.read_feedback(self.shared)

        self.serial.close()
        self.ui.destroy()
        print("[AI] Đã dừng")