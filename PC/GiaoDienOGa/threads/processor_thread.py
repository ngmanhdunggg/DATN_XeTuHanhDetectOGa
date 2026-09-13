import os
import time
import uuid
import sqlite3
import cv2
import numpy as np
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from ultralytics import YOLO

from processors.twinlite import TwinLiteProcessor
from processors.tracker import PotholeTracker

class PotholeProcessor(QObject):
    image_processed = pyqtSignal(np.ndarray, list)
    roi1_updated = pyqtSignal(list)
    pothole_saved = pyqtSignal(dict)
    data_refresh = pyqtSignal()
    map_refresh = pyqtSignal()
    metadata_updated = pyqtSignal(dict)

    def __init__(self, pixel_to_cm2, db_path, images_dir):
        super().__init__()
        self.pixel_to_cm2 = pixel_to_cm2
        self.db_path = db_path
        self.images_dir = images_dir
        self.tracker = None
        self.yolo_model = None
        self.twinlite = None
        self.pothole_detection_enabled = True
        self.conf_threshold = 0.5
        self.roi1_rect = (0, 0, 400, 600)
        self.roi2_rect = (0, 0, 400, 600)
        self.bev_w = 400
        self.bev_h = 600

    def init_models(self, yolo_path, twinlite_path):
        self.yolo_model = YOLO(yolo_path)
        self.twinlite = TwinLiteProcessor(twinlite_path)
        self.tracker = PotholeTracker(pixel_to_cm2=self.pixel_to_cm2, iou_threshold=0.3)

    def set_rois(self, roi1_rect, roi2_rect, bev_w, bev_h):
        self.roi1_rect = roi1_rect
        self.roi2_rect = roi2_rect
        self.bev_w = bev_w
        self.bev_h = bev_h

    def set_pothole_detection(self, enabled):
        self.pothole_detection_enabled = enabled
        if not enabled and self.tracker:
            self.tracker.tracks.clear()
            self.tracker.next_id = 1

    def is_center_in_roi2(self, box):
        x1, y1, x2, y2 = box
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        rx1, ry1, rx2, ry2 = self.roi2_rect
        return (rx1 <= cx <= rx2 and ry1 <= cy <= ry2)

    def is_fully_in_roi1(self, box):
        x1, y1, x2, y2 = box
        rx1, ry1, rx2, ry2 = self.roi1_rect
        return (x1 >= rx1 and x2 <= rx2 and y1 >= ry1 and y2 <= ry2)

    def detect_potholes(self, bev_img):
        results = self.yolo_model(bev_img, conf=self.conf_threshold, verbose=False)
        h, w = bev_img.shape[:2]
        detections = []
        boxes = results[0].boxes
        masks = results[0].masks
        if boxes is not None:
            for i, box in enumerate(boxes):
                conf = box.conf.item()
                if conf < self.conf_threshold:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                mask = None
                if masks is not None:
                    m = masks.data[i].cpu().numpy()
                    m = cv2.resize(m, (w, h))
                    mask = (m > 0.5).astype(np.uint8)
                area_px = mask.sum() if mask is not None else (x2 - x1) * (y2 - y1)
                detections.append({'box': (x1, y1, x2, y2), 'confidence': conf, 'mask': mask, 'area_px': area_px})
        return detections

    def filter_potholes_by_da(self, detections, da_mask, overlap_threshold=0.3):
        filtered = []
        for det in detections:
            if det['mask'] is None:
                x1, y1, x2, y2 = det['box']
                if y2 <= y1 or x2 <= x1:
                    continue
                box_region = da_mask[y1:y2, x1:x2]
                if box_region.size == 0:
                    continue
                overlap = (box_region > 0).sum() / box_region.size
            else:
                overlap = np.logical_and(det['mask'], da_mask).sum() / (det['mask'].sum() + 1e-5)
            if overlap >= overlap_threshold:
                filtered.append(det)
        return filtered

    def save_pothole_record(self, track_id, image_crop, area_cm2, depth_cm, lat, lon, timestamp_str):
        volume_cm3 = area_cm2 * depth_cm
        
        # --- Tạo thư mục con theo ngày ---
        # Chuyển timestamp_str thành đối tượng datetime để lấy ngày
        try:
            # timestamp_str có định dạng "dd-mm-yyyy HH:MM:SS" (từ format_timestamp)
            dt = datetime.strptime(timestamp_str, "%d-%m-%Y %H:%M:%S")
            date_folder = dt.strftime("%Y-%m-%d")  # ví dụ: "2025-01-15"
        except:
            # Nếu lỗi, dùng ngày hiện tại
            date_folder = datetime.now().strftime("%Y-%m-%d")
        
        # Tạo đường dẫn đầy đủ: images_dir/yyyy-mm-dd/
        save_dir = os.path.join(self.images_dir, date_folder)
        os.makedirs(save_dir, exist_ok=True)   # tự động tạo thư mục nếu chưa có
        
        # Tạo tên file an toàn (loại bỏ ký tự đặc biệt)
        safe_timestamp = timestamp_str.replace(" ", "_").replace(":", "-").replace("/", "-")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"pothole_track{track_id}_{safe_timestamp}_{unique_id}.jpg"
        filepath = os.path.join(save_dir, filename)
        # --- Kết thúc phần tạo thư mục con ---
        
        success = cv2.imwrite(filepath, image_crop)
        if not success:
            print(f"[Processor] Cannot save image: {filepath}")
            return None
            
        # Lưu vào database (đường dẫn đã bao gồm thư mục con)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pothole_records (track_id, timestamp, area_cm2, depth_cm, volume_cm3, gps_lat, gps_lon, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (track_id, timestamp_str, area_cm2, depth_cm, volume_cm3, lat, lon, filepath))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        print(f"[Processor] Saved pothole ID={record_id}, max depth={depth_cm:.1f} cm, volume={volume_cm3:.1f} cm³")
        return record_id

    def format_timestamp(self, ts_str):
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

    @pyqtSlot(np.ndarray, dict)
    def process_frame(self, cv_img, metadata):
        self.metadata_updated.emit(metadata)

        if not self.pothole_detection_enabled:
            self.image_processed.emit(cv_img, [])
            return

        da_mask = self.twinlite.predict(cv_img)
        all_potholes = self.detect_potholes(cv_img)
        potholes_in_da = self.filter_potholes_by_da(all_potholes, da_mask)
        self.tracker.update(potholes_in_da, cv_img)
        active_tracks = self.tracker.get_active_tracks()

        gps = metadata.get('gps', {})
        valid = gps.get('valid', False)
        if valid:
            lat = gps.get('latitude', 0.0)
            lon = gps.get('longitude', 0.0)
        else:
            lat = 0.0
            lon = 0.0
        depth_cm = metadata.get('sensors', {}).get('pothole_depth_cm', 0.0)
        raw_ts = metadata.get('timestamp_full', metadata.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        ts_str = self.format_timestamp(raw_ts)

        roi1_tracks_data = []
        for track in active_tracks:
            if self.is_fully_in_roi1(track.box):
                track.update_max_area()
                if not track.has_captured:
                    track.capture_image_from_roi1(cv_img, expand=30)
                roi1_tracks_data.append({
                    'id': track.id,
                    'area_cm2': track.area_cm2,
                    'max_area_cm2': track.max_area_cm2,
                    'box': track.box,
                    'has_captured': track.has_captured,
                    'captured_image': track.captured_image
                })

            currently_in_roi2 = self.is_center_in_roi2(track.box)
            if currently_in_roi2:
                track.update_max_depth(depth_cm)
                if not track.has_entered_roi2:
                    track.has_entered_roi2 = True

            if track.has_entered_roi2 and not currently_in_roi2 and not track.saved and track.has_captured:
                area_cm2 = track.max_area_cm2
                crop = track.captured_image
                if crop is not None:
                    max_depth = track.max_depth_cm
                    if max_depth > 0.5:
                        self.save_pothole_record(track.id, crop, area_cm2, max_depth, lat, lon, ts_str)
                        track.saved = True
                        saved_info = {
                            'track_id': track.id,
                            'area': area_cm2,
                            'depth': max_depth,
                            'volume': area_cm2 * max_depth,
                            'lat': lat,
                            'lon': lon,
                            'timestamp': ts_str,
                            'image': crop
                        }
                        self.pothole_saved.emit(saved_info)
                        self.data_refresh.emit()
                        self.map_refresh.emit()

        display_img = cv_img.copy()
        for track in active_tracks:
            x1, y1, x2, y2 = track.box
            cv2.rectangle(display_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(display_img, f"ID:{track.id}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,255,0), 1)
        display_img = self.twinlite.overlay_masks(display_img, da_mask, alpha=0.3)

        self.image_processed.emit(display_img, active_tracks)
        self.roi1_updated.emit(roi1_tracks_data)