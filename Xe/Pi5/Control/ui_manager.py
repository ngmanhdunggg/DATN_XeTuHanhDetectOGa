import cv2
import subprocess
import numpy as np
from utils import draw_center_path_on_frame

class UIManager:
    def __init__(self, window_name="Robot Control"):
        self.window_name = window_name
        self.first_frame = True

    def initialize(self):
        """Tạo cửa sổ OpenCV"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)

    def draw_info(self, frame, auto_mode, center_points, M_inv, speed, steer,
                  final_speed, final_steer, front_distance, battery, boost_state):
        """Vẽ tất cả thông tin lên frame"""
        display = frame.copy()
        if auto_mode and center_points and len(center_points) >= 2:
            display = draw_center_path_on_frame(display, center_points, M_inv)

        mode_text = "AUTO MODE" if auto_mode else "MANUAL MODE"
        front_str = f"Front: {front_distance:.1f} cm" if not np.isinf(front_distance) else "Front: ---"
        info_lines = [
            f"Mode: {mode_text}",
            f"Speed: {speed:.2f} m/s",
            f"Steer: {steer:.1f} deg",
            f"Cmd Speed: {final_speed:.2f} | Cmd Steer: {final_steer:.1f}",
            front_str,
            f"Battery: {battery:.1f}%",
            f"Boost: {boost_state}"
        ]
        y_offset = 30
        for i, line in enumerate(info_lines):
            cv2.putText(display, line, (10, y_offset + i*25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
        return display

    def show(self, frame):
        """Hiển thị frame và xử lý fullscreen lần đầu"""
        cv2.imshow(self.window_name, frame)
        if self.first_frame:
            cv2.waitKey(500)  # đợi cửa sổ hiện ra
            try:
                subprocess.Popen(['wmctrl', '-r', self.window_name, '-b', 'add,fullscreen'])
                print("[UI] Đã gửi lệnh fullscreen qua wmctrl")
            except Exception as e:
                print(f"[UI] Không thể dùng wmctrl: {e}, thử lại cv2 fullscreen")
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            self.first_frame = False

    def get_key(self):
        """Lấy phím nhấn từ bàn phím (non-blocking)"""
        return cv2.waitKey(1) & 0xFF

    def destroy(self):
        cv2.destroyAllWindows()