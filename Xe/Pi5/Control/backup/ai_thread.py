# ai_thread.py
import threading
import time
import cv2
import numpy as np
import onnxruntime as ort
import serial
import re
import subprocess  # thêm để gọi wmctrl
from config import (
    MODEL_PATH, SERIAL_PORT, BAUD_RATE, FRAME_SIZE, INPUT_SIZE,
    MIN_AREA, MAX_SPEED, MIN_SPEED, MAX_STEER, KP, KD,
    NUM_SCAN_LINES, Y_START_RATIO, Y_END_RATIO, MAX_CENTER_SHIFT,
    FRONT_SAFE_DISTANCE, STEER_SLOW_THRESHOLD, MAX_STEER_FOR_BOOST
)
from utils import (
    get_bird_eye_matrix, filter_noise, compute_center_per_row,
    filter_outlier_centers, draw_center_path_on_frame
)

class AIThread(threading.Thread):
    def __init__(self, stop_event, shared_data):
        super().__init__()
        self.stop_event = stop_event
        self.shared = shared_data
        self.last_error = 0
        self.boost_state = 0
        self.boost_start_time = 0.0
        self.stall_start_time = None
        self.BOOST_FORWARD_DURATION = 1.0
        self.BOOST_BACKWARD_DURATION = 0.1
        self.BOOST_FORWARD_SPEED = 0.70
        self.BOOST_BACKWARD_SPEED = -0.1
        self.SPEED_THRESHOLD_MOVING = 0.05
        self.STALL_DELAY = 10.0
        self.ramp_start_speed = 0.0
        self.ramp_target_speed = 0.0

    def run(self):
        print("[AI] Khởi tạo AI model...")
        session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        M, M_inv = get_bird_eye_matrix()
        h, w = FRAME_SIZE[1], FRAME_SIZE[0]
        y_positions = np.linspace(int(h * Y_START_RATIO), int(h * Y_END_RATIO), NUM_SCAN_LINES, dtype=int)
        weights = np.linspace(1.0, 0.3, NUM_SCAN_LINES)

        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
            print(f"[AI] UART OK {SERIAL_PORT}")
        except Exception as e:
            print(f"[AI] Lỗi UART: {e}")
            return

        ser.write(b"S0.00A0.00\r\n")
        time.sleep(0.5)

        def read_esp_feedback():
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith('FB:'):
                    m_match = re.search(r'M=(\d)', line)
                    a_match = re.search(r'A=([+-]?\d+\.?\d*)', line)
                    s_match = re.search(r'S=([+-]?\d+\.?\d*)', line)
                    f_match = re.search(r'F=([+-]?(?:\d+(?:\.\d+)?|inf|INF))', line, re.IGNORECASE)
                    r_match = re.search(r'R=([+-]?(?:\d+(?:\.\d+)?|inf|INF))', line, re.IGNORECASE)
                    b_match = re.search(r'B=(\d+\.?\d*)', line)
                    p_match = re.search(r'P=([+-]?(?:\d+(?:\.\d+)?|inf|INF))', line, re.IGNORECASE)
                    with self.shared['lock']:
                        if m_match:
                            self.shared['auto_mode'] = (m_match.group(1) == '1')
                        if s_match:
                            self.shared['speed'] = float(s_match.group(1))
                        if a_match:
                            self.shared['steer'] = float(a_match.group(1))
                        if f_match:
                            val = f_match.group(1).lower()
                            self.shared['front_distance'] = float('inf') if val == 'inf' else float(val)
                        if r_match:
                            val = r_match.group(1).lower()
                            self.shared['rear_distance'] = float('inf') if val == 'inf' else float(val)
                        if b_match:
                            self.shared['battery'] = float(b_match.group(1))
                        if p_match:
                            val = p_match.group(1).lower()
                            self.shared['pothole_depth'] = float('inf') if val == 'inf' else float(val)

        last_ai_time = 0
        min_interval = 1.0 / 30.0

        window_name = "Robot Control"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        first_frame = True

        while not self.stop_event.is_set():
            read_esp_feedback()
            now = time.time()
            if now - last_ai_time < min_interval:
                time.sleep(0.001)
                continue
            last_ai_time = now

            with self.shared['lock']:
                frame = self.shared['frame_orig']
                if frame is None:
                    continue
                speed = self.shared['speed']
                steer = self.shared['steer']
                front = self.shared['front_distance']
                auto_mode = self.shared['auto_mode']
                cmd_speed = self.shared.get('cmd_speed', 0.0)
                cmd_steer = self.shared.get('cmd_steer', 0.0)

            front_obstacle = False
            if not np.isinf(front) and not np.isnan(front):
                if 0.01 < front < FRONT_SAFE_DISTANCE:
                    front_obstacle = True

            center_points = []

            if auto_mode and not front_obstacle:
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
                    cmd_speed = 0.0
                    cmd_steer = 0.0
                    self.boost_state = 0
                    self.stall_start_time = None
                    final_speed = cmd_speed
                    final_steer = cmd_steer
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
                        cmd_speed = 0.0
                        cmd_steer = 0.0
                        self.boost_state = 0
                        self.stall_start_time = None
                        final_speed = cmd_speed
                        final_steer = cmd_steer
                    else:
                        total_error = 0.0
                        total_weight = 0.0
                        for c, wgt in zip(centers, valid_weights):
                            error = c - mid_w
                            total_error += error * wgt
                            total_weight += wgt
                        current_error = total_error / total_weight

                        cmd_steer = KP * current_error + KD * (current_error - self.last_error)
                        self.last_error = current_error
                        cmd_steer = np.clip(cmd_steer, -MAX_STEER, MAX_STEER)

                        if abs(cmd_steer) > STEER_SLOW_THRESHOLD:
                            speed_factor = 1 - ((abs(cmd_steer) - STEER_SLOW_THRESHOLD) / (MAX_STEER - STEER_SLOW_THRESHOLD))
                            cmd_speed = MIN_SPEED + (MAX_SPEED - MIN_SPEED) * (speed_factor ** 2)
                        else:
                            cmd_speed = MAX_SPEED

                        actual_speed = speed
                        need_move = (actual_speed < self.SPEED_THRESHOLD_MOVING and
                                     cmd_speed > 0.1 and
                                     abs(cmd_steer) <= MAX_STEER_FOR_BOOST)

                        if self.boost_state != 0 and abs(cmd_steer) > MAX_STEER_FOR_BOOST:
                            self.boost_state = 0
                            self.stall_start_time = None

                        if need_move:
                            if self.stall_start_time is None:
                                self.stall_start_time = time.time()
                            elif (time.time() - self.stall_start_time) >= self.STALL_DELAY:
                                if self.boost_state == 0:
                                    self.boost_state = 1
                                    self.boost_start_time = time.time()
                                    print("[BOOST] Start boost forward")
                        else:
                            self.stall_start_time = None
                            if self.boost_state != 0 and self.boost_state != 3:
                                if self.boost_state == 1:
                                    self.boost_state = 3
                                    self.ramp_start_speed = self.BOOST_FORWARD_SPEED
                                    self.ramp_target_speed = cmd_speed
                                    self.boost_start_time = time.time()
                                elif self.boost_state == 2:
                                    self.boost_state = 3
                                    self.ramp_start_speed = abs(self.BOOST_BACKWARD_SPEED)
                                    self.ramp_target_speed = cmd_speed
                                    self.boost_start_time = time.time()
                                else:
                                    self.boost_state = 0

                        if self.boost_state == 0:
                            final_speed = cmd_speed
                            final_steer = cmd_steer
                        elif self.boost_state == 1:
                            elapsed = time.time() - self.boost_start_time
                            if elapsed >= self.BOOST_FORWARD_DURATION:
                                self.boost_state = 2
                                self.boost_start_time = time.time()
                                final_speed = self.BOOST_BACKWARD_SPEED
                                final_steer = cmd_steer
                            else:
                                final_speed = self.BOOST_FORWARD_SPEED
                                final_steer = cmd_steer
                        elif self.boost_state == 2:
                            elapsed = time.time() - self.boost_start_time
                            if elapsed >= self.BOOST_BACKWARD_DURATION:
                                self.boost_state = 1
                                self.boost_start_time = time.time()
                                final_speed = self.BOOST_FORWARD_SPEED
                                final_steer = cmd_steer
                            else:
                                final_speed = self.BOOST_BACKWARD_SPEED
                                final_steer = cmd_steer
                        elif self.boost_state == 3:
                            elapsed = time.time() - self.boost_start_time
                            speed_decrement = (elapsed / 0.05) * 0.01
                            new_speed = self.ramp_start_speed - speed_decrement
                            if new_speed <= self.ramp_target_speed:
                                self.boost_state = 0
                                final_speed = self.ramp_target_speed
                                final_steer = cmd_steer
                            else:
                                final_speed = new_speed
                                final_steer = cmd_steer
                        else:
                            final_speed = cmd_speed
                            final_steer = cmd_steer

                ser.write(f"S{final_speed:.2f}A{final_steer:.2f}\r\n".encode())
                with self.shared['lock']:
                    self.shared['cmd_speed'] = final_speed
                    self.shared['cmd_steer'] = final_steer
                    self.shared['boost_state'] = self.boost_state
            else:
                ser.write(b"S0.00A0.00\r\n")
                with self.shared['lock']:
                    self.shared['cmd_speed'] = 0.0
                    self.shared['cmd_steer'] = 0.0
                    self.shared['boost_state'] = 0
                self.boost_state = 0
                self.stall_start_time = None
                final_speed = 0.0
                final_steer = 0.0

            # Hiển thị
            display_frame = frame.copy()
            
            if auto_mode:
                mode_text = "AUTO MODE"
            else:
                mode_text = "MANUAL MODE"
            if auto_mode and len(center_points) >= 2:
                display_frame = draw_center_path_on_frame(display_frame, center_points, M_inv)

            info_lines = [
                f"Mode: {mode_text}",
                f"Speed: {speed:.2f} m/s",
                f"Steer: {steer:.1f} deg",
                f"Cmd Speed: {final_speed:.2f} | Cmd Steer: {final_steer:.1f}",
                f"Front: {front:.1f} cm" if not np.isinf(front) else "Front: ---",
                f"Battery: {self.shared.get('battery', 0.0):.1f}%",
                f"Boost: {self.boost_state}"
            ]
            y_offset = 30
            for i, line in enumerate(info_lines):
                cv2.putText(display_frame, line, (10, y_offset + i*25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

            cv2.imshow(window_name, display_frame)

            # Sử dụng wmctrl để set fullscreen một cách chắc chắn
            if first_frame:
                cv2.waitKey(500)  # đợi cửa sổ hiện ra
                # Dùng wmctrl để force fullscreen (không cần đợi window manager)
                try:
                    subprocess.Popen(['wmctrl', '-r', window_name, '-b', 'add,fullscreen'])
                    print("[AI] Đã gửi lệnh fullscreen qua wmctrl")
                except Exception as e:
                    print(f"[AI] Không thể dùng wmctrl: {e}, thử lại cv2 fullscreen")
                    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                first_frame = False

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                self.stop_event.set()

            read_esp_feedback()

        ser.close()
        cv2.destroyAllWindows()
        print("[AI] Đã dừng")