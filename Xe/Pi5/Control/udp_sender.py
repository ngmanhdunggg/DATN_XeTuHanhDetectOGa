import threading
import time
import socket
import struct
import cv2
import json
import random
from config import LAPTOP_IP, VIDEO_PORT, MAX_FPS_SEND

class UDPSenderThread(threading.Thread):
    def __init__(self, stop_event, shared_data):
        super().__init__()
        self.stop_event = stop_event
        self.shared = shared_data
        self.sock = None
        self.addr = (LAPTOP_IP, VIDEO_PORT)
        self.CHUNK_SIZE = 60 * 1024

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(None)
            print(f"[UDP] Đã tạo socket đến {LAPTOP_IP}:{VIDEO_PORT}")
            return True
        except Exception as e:
            print(f"[UDP] Lỗi socket: {e}")
            return False

    def send_frame(self, frame, metadata):
        if self.sock is None:
            if not self.connect():
                return False
        try:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            _, frame_encoded = cv2.imencode('.jpg', frame, encode_param)
            frame_data = frame_encoded.tobytes()
            metadata_json = json.dumps(metadata).encode('utf-8')
            meta_len = struct.pack('!I', len(metadata_json))
            frame_len = struct.pack('!I', len(frame_data))
            total_payload = meta_len + metadata_json + frame_len + frame_data
            total_len = len(total_payload)
            num_chunks = (total_len + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
            frame_id = random.randint(0, 65535)

            for i in range(num_chunks):
                start = i * self.CHUNK_SIZE
                end = min(start + self.CHUNK_SIZE, total_len)
                chunk_data = total_payload[start:end]
                header = struct.pack('!HHH', frame_id, num_chunks, i)
                packet = header + chunk_data
                self.sock.sendto(packet, self.addr)
            return True
        except Exception as e:
            print(f"[UDP] Lỗi gửi: {e}")
            return False

    def run(self):
        print("[UDP] Bắt đầu gửi BEV (15fps)...")
        send_interval = 1.0 / MAX_FPS_SEND
        last_send = 0

        while not self.stop_event.is_set():
            now = time.time()
            if now - last_send >= send_interval:
                with self.shared['lock']:
                    frame = self.shared.get('bev_frame')
                    metadata = self.shared.get('metadata')
                if frame is not None and metadata is not None:
                    self.send_frame(frame, metadata)
                last_send = now
            else:
                time.sleep(0.001)

        if self.sock:
            self.sock.close()
        print("[UDP] Đã dừng")