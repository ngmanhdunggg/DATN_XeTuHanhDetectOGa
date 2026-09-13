# main.py
import threading
import time
import cv2
from ai_thread import AIThread
from bev_thread import BEVThread
from udp_sender import UDPSenderThread
from telemetry import TelemetryThread

def main():
    stop_event = threading.Event()
    shared = {
        'lock': threading.Lock(),
        'frame_orig': None,
        'bev_frame': None,
        'metadata': None,
        'speed': 0.0,
        'steer': 0.0,
        'auto_mode': False,
        'front_distance': float('inf'),
        'rear_distance': float('inf'),
        'pothole_depth': 0.0,
        'battery': 0.0,
        'lat': 0.0,
        'lon': 0.0,
        'gps_valid': False,
        'cmd_speed': 0.0,
        'cmd_steer': 0.0,
        'boost_state': 0,
        'yaw_angle_deg': 0.0,
    }

    tele_thread = TelemetryThread(stop_event, shared)
    bev_thread = BEVThread(stop_event, shared)
    ai_thread = AIThread(stop_event, shared)
    udp_thread = UDPSenderThread(stop_event, shared)

    tele_thread.start()
    bev_thread.start()
    ai_thread.start()
    udp_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Nhận tín hiệu dừng...")
    finally:
        stop_event.set()
        tele_thread.join(timeout=2)
        bev_thread.join(timeout=2)
        ai_thread.join(timeout=2)
        udp_thread.join(timeout=2)
        cv2.destroyAllWindows()
        print("Hệ thống đã dừng hoàn toàn.")

if __name__ == "__main__":
    main()