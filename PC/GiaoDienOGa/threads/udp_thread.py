import socket
import struct
import cv2
import numpy as np
import json
import time
from PyQt5.QtCore import QThread, pyqtSignal

class UDPVideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray, dict)
    connection_status_signal = pyqtSignal(str)

    def __init__(self, port=5557):
        super().__init__()
        self.port = port
        self._run_flag = True
        self.fragments = {}
        self.cleanup_interval = 5.0
        self.last_cleanup = time.time()
        self.connected = False
        self.last_received = time.time()
        self.last_frame_shape = None          # Lưu kích thước frame cuối
        self.sent_black_on_disconnect = False # Tránh gửi nhiều lần

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', self.port))
        sock.settimeout(1.0)
        self.connection_status_signal.emit(f"UDP listening on port {self.port} (fragmented)")

        while self._run_flag:
            try:
                data, addr = sock.recvfrom(65536)
                if len(data) < 6:
                    continue

                # --- Có dữ liệu đến ---
                self.last_received = time.time()
                if not self.connected:
                    self.connected = True
                    self.sent_black_on_disconnect = False
                    self.connection_status_signal.emit("Connected")

                # Xử lý phân mảnh (giữ nguyên)
                frame_id, num_chunks, chunk_idx = struct.unpack('!HHH', data[:6])
                chunk_data = data[6:]

                if frame_id not in self.fragments:
                    self.fragments[frame_id] = {
                        'num_chunks': num_chunks,
                        'chunks': {},
                        'last_update': time.time()
                    }
                self.fragments[frame_id]['chunks'][chunk_idx] = chunk_data
                self.fragments[frame_id]['last_update'] = time.time()

                frag = self.fragments[frame_id]
                if len(frag['chunks']) == num_chunks:
                    total_data = b''.join(frag['chunks'][i] for i in range(num_chunks))
                    del self.fragments[frame_id]

                    if len(total_data) < 8:
                        continue
                    meta_len = struct.unpack('!I', total_data[:4])[0]
                    if meta_len <= 0 or meta_len > 1000000:
                        continue
                    if len(total_data) < 4 + meta_len + 4:
                        continue
                    metadata_json = total_data[4:4+meta_len].decode('utf-8')
                    metadata = json.loads(metadata_json)
                    frame_len = struct.unpack('!I', total_data[4+meta_len:8+meta_len])[0]
                    if frame_len <= 0 or frame_len > 5000000:
                        continue
                    frame_start = 8 + meta_len
                    if len(total_data) < frame_start + frame_len:
                        continue
                    frame_data = total_data[frame_start:frame_start+frame_len]
                    frame = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        self.last_frame_shape = frame.shape  # Lưu kích thước
                        self.change_pixmap_signal.emit(frame, metadata)

                # Dọn dẹp fragment cũ
                now = time.time()
                if now - self.last_cleanup >= self.cleanup_interval:
                    expired = [fid for fid, info in self.fragments.items() if now - info['last_update'] > 5.0]
                    for fid in expired:
                        del self.fragments[fid]
                    self.last_cleanup = now

            except socket.timeout:
                # Kiểm tra mất kết nối
                if self.connected and (time.time() - self.last_received > 10.0):
                    self.connected = False
                    self.connection_status_signal.emit("Disconnected")
                    # Gửi ảnh đen nếu có kích thước frame cũ
                    if self.last_frame_shape is not None and not self.sent_black_on_disconnect:
                        black_frame = np.zeros(self.last_frame_shape, dtype=np.uint8)
                        self.change_pixmap_signal.emit(black_frame, {})
                        self.sent_black_on_disconnect = True
                continue
            except Exception as e:
                self.connection_status_signal.emit(f"Error: {e}")

        sock.close()

    def stop(self):
        self._run_flag = False
        self.wait()