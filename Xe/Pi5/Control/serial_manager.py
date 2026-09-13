import serial
import re
import time
from config import SERIAL_PORT, BAUD_RATE

class SerialManager:
    def __init__(self):
        self.ser = None
        self.connected = False

    def connect(self):
        """Kết nối serial và gửi lệnh dừng ban đầu"""
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
            print(f"[Serial] UART OK {SERIAL_PORT}")
            self.send_command(0.0, 0.0)
            time.sleep(0.5)
            self.connected = True
            return True
        except Exception as e:
            print(f"[Serial] Lỗi UART: {e}")
            self.connected = False
            return False

    def send_command(self, speed, steer):
        """Gửi lệnh Sxx.xxAxx.xx\r\n xuống ESP"""
        if self.ser:
            self.ser.write(f"S{speed:.2f}A{steer:.2f}\r\n".encode())

    def read_feedback(self, shared_data):
        """Đọc dữ liệu từ ESP và cập nhật shared_data (có lock)"""
        if not self.ser or not self.ser.in_waiting:
            return
        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
        if line.startswith('FB:'):
            m_match = re.search(r'M=(\d)', line)
            a_match = re.search(r'A=([+-]?\d+\.?\d*)', line)
            s_match = re.search(r'S=([+-]?\d+\.?\d*)', line)
            f_match = re.search(r'F=([+-]?(?:\d+(?:\.\d+)?|inf|INF))', line, re.IGNORECASE)
            r_match = re.search(r'R=([+-]?(?:\d+(?:\.\d+)?|inf|INF))', line, re.IGNORECASE)
            b_match = re.search(r'B=(\d+\.?\d*)', line)
            p_match = re.search(r'P=([+-]?(?:\d+(?:\.\d+)?|inf|INF))', line, re.IGNORECASE)
            with shared_data['lock']:
                if m_match:
                    shared_data['auto_mode'] = (m_match.group(1) == '1')
                if s_match:
                    shared_data['speed'] = float(s_match.group(1))
                if a_match:
                    shared_data['steer'] = float(a_match.group(1))
                if f_match:
                    val = f_match.group(1).lower()
                    shared_data['front_distance'] = float('inf') if val == 'inf' else float(val)
                if r_match:
                    val = r_match.group(1).lower()
                    shared_data['rear_distance'] = float('inf') if val == 'inf' else float(val)
                if b_match:
                    shared_data['battery'] = float(b_match.group(1))
                if p_match:
                    val = p_match.group(1).lower()
                    shared_data['pothole_depth'] = float('inf') if val == 'inf' else float(val)

    def close(self):
        if self.ser:
            self.ser.close()
            self.connected = False