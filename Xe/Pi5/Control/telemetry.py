import threading
import time
import serial
import pynmea2
from config import SERIAL_PORT

class TelemetryThread(threading.Thread):
    def __init__(self, stop_event, shared_data):
        super().__init__()
        self.stop_event = stop_event
        self.shared = shared_data

    def run(self):
        print("[Telemetry] Đã tắt đọc ESP (chỉ đọc GPS nếu có)...")
        try:
            ser_gps = serial.Serial("/dev/ttyACM0", baudrate=9600, timeout=1)
            print("[Telemetry] GPS OK")
        except Exception as e:
            print(f"[Telemetry] Lỗi GPS: {e}")
            ser_gps = None

        while not self.stop_event.is_set():
            if ser_gps and ser_gps.in_waiting > 0:
                line = ser_gps.readline().decode('ascii', errors='ignore')
                if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    try:
                        msg = pynmea2.parse(line)
                        if msg.latitude != 0.0 and msg.longitude != 0.0:
                            with self.shared['lock']:
                                self.shared['lat'] = msg.latitude
                                self.shared['lon'] = msg.longitude
                                self.shared['gps_valid'] = True
                        else:
                            with self.shared['lock']:
                                self.shared['gps_valid'] = False
                    except:
                        pass
            time.sleep(0.005)

        if ser_gps:
            ser_gps.close()
        print("[Telemetry] Đã dừng")