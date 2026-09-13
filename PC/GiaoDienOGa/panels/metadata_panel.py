import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import QGroupBox, QFormLayout, QLabel, QFrame
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from widgets.switch import Switch

class MetadataPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Thông tin hệ thống", parent)
        self.setMinimumWidth(400)
        self.setStyleSheet("color: #ecf0f1; font-weight: bold;")
        self.layout = QFormLayout(self)
        data_font = QFont("Consolas", 12, QFont.Bold)
        value_style = "color: #1abc9c;"

        self.lbl_status = QLabel("Chờ kết nối")
        self.lbl_fps = QLabel("0")
        self.lbl_timestamp = QLabel("00-00-0000 00:00:00")
        self.lbl_mode = QLabel("Thủ công")
        self.lbl_speed = QLabel("0.00 m/s")
        self.lbl_steering = QLabel("0.0°")
        self.lbl_battery = QLabel("0%")
        self.lbl_pothole = QLabel("0.0 cm")
        self.lbl_front = QLabel("--- cm")
        self.lbl_rear = QLabel("--- cm")
        self.lbl_lat = QLabel("0.000000")
        self.lbl_lon = QLabel("0.000000")
        self.lbl_gps_valid = QLabel("Mất kết nối GPS")
        self.lbl_pothole_count = QLabel("0")
        self.lbl_pothole_area = QLabel("0.0 cm²")

        for lbl in [self.lbl_status, self.lbl_fps, self.lbl_timestamp, self.lbl_mode,
                    self.lbl_speed, self.lbl_steering, self.lbl_battery, self.lbl_pothole,
                    self.lbl_front, self.lbl_rear, self.lbl_lat, self.lbl_lon, self.lbl_gps_valid,
                    self.lbl_pothole_count, self.lbl_pothole_area]:
            lbl.setFont(data_font)
            lbl.setStyleSheet(value_style)

        self.layout.addRow("Kết nối:", self.lbl_status)
        self.layout.addRow("FPS:", self.lbl_fps)
        self.layout.addRow("Thời gian:", self.lbl_timestamp)
        self.layout.addRow("Chế độ:", self.lbl_mode)
        self.layout.addRow("Tốc độ:", self.lbl_speed)
        self.layout.addRow("Góc lái:", self.lbl_steering)
        self.layout.addRow("Pin:", self.lbl_battery)
        self.layout.addRow("Độ sâu ổ gà:", self.lbl_pothole)
        self.layout.addRow("Khoảng cách trước:", self.lbl_front)
        self.layout.addRow("Khoảng cách sau:", self.lbl_rear)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #7f8c8d;")
        self.layout.addRow(line)
        self.layout.addRow("Số ổ gà:", self.lbl_pothole_count)
        self.layout.addRow("Tổng diện tích:", self.lbl_pothole_area)
        self.layout.addRow("Vĩ độ:", self.lbl_lat)
        self.layout.addRow("Kinh độ:", self.lbl_lon)
        self.layout.addRow("Trạng thái GPS:", self.lbl_gps_valid)

        self.pothole_toggle = Switch("Phát hiện ổ gà")
        self.layout.addRow(self.pothole_toggle)

    def update_metadata(self, metadata):
        pothole_detection_enabled = self.pothole_toggle.isChecked()

        raw_ts = metadata.get('timestamp_full', metadata.get('timestamp', 'N/A'))
        ts_str = self.format_timestamp(raw_ts)
        self.lbl_timestamp.setText(ts_str)

        system = metadata.get('system', {})
        auto = system.get('auto_mode', False)
        self.lbl_mode.setText("Tự động" if auto else "Thủ công")
        self.lbl_mode.setStyleSheet("color: #2ecc71;" if auto else "color: #f39c12;")

        sensors = metadata.get('sensors', {})
        speed_mps = sensors.get('speed_mps', 0.0)
        steering_angle = sensors.get('steering_angle_deg', 0.0)
        self.lbl_speed.setText(f"{speed_mps:.2f} m/s")
        self.lbl_steering.setText(f"{steering_angle:.1f}°")
        self.lbl_battery.setText(f"{sensors.get('battery_percent', 0.0):.0f}%")
        depth_cm = sensors.get('pothole_depth_cm', 0.0)
        self.lbl_pothole.setText(f"{depth_cm:.1f} cm" if pothole_detection_enabled else "--- cm")
        f = sensors.get('front_distance_cm', -1)
        r = sensors.get('rear_distance_cm', -1)
        self.lbl_front.setText(f"{f:.1f} cm" if f != -1 and not np.isinf(f) else "--- cm")
        self.lbl_rear.setText(f"{r:.1f} cm" if r != -1 and not np.isinf(r) else "--- cm")

        gps = metadata.get('gps', {})
        valid = gps.get('valid', False)
        if valid:
            lat = gps.get('latitude', 0.0)
            lon = gps.get('longitude', 0.0)
        else:
            lat = 0.0
            lon = 0.0
        self.lbl_lat.setText(f"{lat:.6f}")
        self.lbl_lon.setText(f"{lon:.6f}")
        self.lbl_gps_valid.setText("GPS hợp lệ" if valid else "Mất kết nối GPS")
        self.lbl_gps_valid.setStyleSheet("color: #2ecc71;" if valid else "color: #e74c3c;")

    def update_pothole_stats(self, count, total_area):
        self.lbl_pothole_count.setText(str(count))
        self.lbl_pothole_area.setText(f"{total_area:.1f} cm²")

    def set_status(self, text):
        # Xử lý các thông báo từ UDP thread
        if text == "Connected":
            self.lbl_status.setText("Đã kết nối")
            self.lbl_status.setStyleSheet("color: #2ecc71;")  # xanh
        elif text == "Disconnected":
            self.lbl_status.setText("Mất kết nối")
            self.lbl_status.setStyleSheet("color: #e74c3c;")  # đỏ
        elif "UDP listening on port" in text:
            self.lbl_status.setText("Chờ kết nối")
            self.lbl_status.setStyleSheet("color: #f39c12;")  # vàng
        else:
            self.lbl_status.setText(text)

    def set_fps(self, fps):
        self.lbl_fps.setText(str(fps))

    def reset_all_display(self):
        """Reset tất cả các giá trị hiển thị về trạng thái ban đầu khi mất kết nối."""
        self.lbl_fps.setText("0")
        self.lbl_timestamp.setText(datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        self.lbl_mode.setText("Thủ công")
        self.lbl_speed.setText("0.00 m/s")
        self.lbl_steering.setText("0.0°")
        self.lbl_battery.setText("0%")
        if self.pothole_toggle.isChecked():
            self.lbl_pothole.setText("0.0 cm")
        else:
            self.lbl_pothole.setText("--- cm")
        self.lbl_front.setText("--- cm")
        self.lbl_rear.setText("--- cm")
        self.lbl_lat.setText("0.000000")
        self.lbl_lon.setText("0.000000")
        self.lbl_gps_valid.setText("Mất kết nối GPS")
        self.lbl_gps_valid.setStyleSheet("color: #e74c3c;")
        self.lbl_pothole_count.setText("0")
        self.lbl_pothole_area.setText("0.0 cm²")

    @staticmethod
    def format_timestamp(ts_str):
        if not isinstance(ts_str, str) or ts_str == "N/A":
            return datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        try:
            if "_" in ts_str and len(ts_str) >= 15:
                date_part, time_part = ts_str.split("_")
                year, month, day = date_part[:4], date_part[4:6], date_part[6:8]
                hour, minute, second = time_part[:2], time_part[2:4], time_part[4:6]
                return f"{day}-{month}-{year} {hour}:{minute}:{second}"
            cleaned = ts_str.replace('T', ' ').replace('Z', '').split('.')[0]
            dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d-%m-%Y %H:%M:%S")
        except:
            return ts_str