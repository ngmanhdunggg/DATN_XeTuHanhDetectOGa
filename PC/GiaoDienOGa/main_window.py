import sys
import os
import time
import sqlite3
import cv2
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from threads.udp_thread import UDPVideoThread
from threads.processor_thread import PotholeProcessor
from widgets.bird_eye_label import BirdEyeLabel
from widgets.saved_pothole_widget import SavedPotholeWidget
from widgets.roi_table_widget import ROITableWidget
from tabs.data_tab import DataTab
from tabs.map_tab import MapTab
from panels.metadata_panel import MetadataPanel
from bridge import PotholeBridge
from location_manager import LocationManager
from database.database import DatabaseManager


class MainWindow(QMainWindow):
    def __init__(self, init_data=None):
        super().__init__()
        self.setWindowTitle("Phần mềm phát hiện ổ gà")
        self.resize(1400, 800)
        self.setStyleSheet("background-color: #2c3e50; color: white;")

        if init_data is not None:
            # ---------- DÙNG DỮ LIỆU TỪ SPLASH ----------
            self.db_path = init_data['db_path']
            self.images_dir = init_data['images_dir']
            self.location_mgr = init_data['location_mgr']
            self.processor = init_data['processor']
            self.processor_thread = init_data['processor_thread']
            self.udp_thread = init_data['udp_thread']
            self.bev_w = init_data['bev_w']
            self.bev_h = init_data['bev_h']
            self.pixel_to_cm2 = init_data['pixel_to_cm2']
            self.roi1_rect = init_data['roi1_rect']
            self.roi2_rect = init_data['roi2_rect']
            self.roi1_center_y_ratio = init_data['roi1_center_y_ratio']
            self.roi1_height_ratio = init_data['roi1_height_ratio']
            self.roi2_center_y_ratio = init_data['roi2_center_y_ratio']
            self.roi2_height_ratio = init_data['roi2_height_ratio']

            self.db = DatabaseManager(self.db_path)
            self.pothole_detection_enabled = False

            # Tạo metadata panel
            self.meta_panel = MetadataPanel()
            self.meta_panel.pothole_toggle.setChecked(self.pothole_detection_enabled)

            # Tạo giao diện
            self._setup_gui()

            # Cập nhật ROI cho bird_label
            self.update_rois()

            # Kết nối signals
            self._connect_signals()

            # Bật chế độ phát hiện (mặc định tắt)
            self.toggle_pothole_detection(False)

            # Bắt đầu UDP thread (chưa start ở splash)
            self.udp_thread.start()

            self.last_time = time.time()
            self.frame_count = 0
            self.load_data()

        else:
            # ---------- KHỞI TẠO THÔNG THƯỜNG (KHÔNG SPLASH) ----------
            # BEV config
            self.bev_w = 400
            self.bev_h = 600
            self.pixel_to_cm2 = (60.0 / 400.0) ** 2

            self.roi1_center_y_ratio = 0.42
            self.roi1_height_ratio = 0.2
            self.roi2_center_y_ratio = 0.82
            self.roi2_height_ratio = 0.3

            self.pothole_detection_enabled = False
            self.update_rois()

            # Database & folder
            self.db_path = os.path.join("database", "potholes.db")
            self.db = DatabaseManager(self.db_path)
            os.makedirs("database", exist_ok=True)
            self.images_dir = os.path.abspath("OGa")
            os.makedirs(self.images_dir, exist_ok=True)
            self.init_database()

            # LocationManager
            geojson_base = os.path.join("database", "geojson")
            if os.path.exists(geojson_base):
                self.location_mgr = LocationManager(geojson_base)
            else:
                print(f"Warning: Geojson folder not found at {geojson_base}")
                self.location_mgr = None

            # Metadata panel
            self.meta_panel = MetadataPanel()
            self.meta_panel.pothole_toggle.setChecked(self.pothole_detection_enabled)

            # Worker thread
            self.processor_thread = QThread()
            self.processor = PotholeProcessor(self.pixel_to_cm2, self.db_path, self.images_dir)
            self.processor.moveToThread(self.processor_thread)
            self.processor_thread.start()
            self.processor.init_models(
                os.path.join("model", "epoch99.pt"),
                os.path.join("model", "model_249.pth")
            )
            self.processor.set_rois(self.roi1_rect, self.roi2_rect, self.bev_w, self.bev_h)
            self.toggle_pothole_detection(False)

            # UDP thread
            self.udp_thread = UDPVideoThread(5557)

            # GUI
            self._setup_gui()
            self._connect_signals()

            self.last_time = time.time()
            self.frame_count = 0
            self.udp_thread.start()
            self.load_data()

    # ------------------ CÁC PHƯƠNG THỨC CHUNG ------------------
    def _setup_gui(self):
        """Tạo toàn bộ giao diện (được dùng chung cho cả hai trường hợp)"""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #34495e; background: #2c3e50; }
            QTabBar::tab { height: 35px; width: 140px; background-color: #34495e; color: #bdc3c7;
                           font-weight: bold; padding: 5px; margin: 2px;
                           border-top-left-radius: 5px; border-top-right-radius: 5px; }
            QTabBar::tab:selected { background-color: #1abc9c; color: white; }
            QTabBar::tab:hover { background-color: #16a085; color: white; }
        """)

        # Tab Camera (BEV)
        self.bev_tab = QWidget()
        bev_layout = QHBoxLayout(self.bev_tab)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.bev_container = QGroupBox("Camera biến đổi phối cảnh")
        self.bev_container.setStyleSheet("color: #ecf0f1; font-weight: bold;")
        self.bird_label = BirdEyeLabel(roi_rects=[], parent=self.bev_container)
        bev_inner = QVBoxLayout()
        bev_inner.addWidget(self.bird_label)
        self.bev_container.setLayout(bev_inner)
        left_layout.addWidget(self.bev_container)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.saved_widget = SavedPotholeWidget()
        self.roi_table_widget = ROITableWidget()
        right_layout.addWidget(self.saved_widget, 3)
        right_layout.addWidget(self.roi_table_widget, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 400])
        bev_layout.addWidget(splitter)
        self.tab_widget.addTab(self.bev_tab, "Camera")

        # Data Tab
        self.data_tab = DataTab(self.db_path, self.location_mgr)
        self.tab_widget.addTab(self.data_tab, "Dữ liệu")

        # Map Tab
        self.map_tab = MapTab(self.db_path, self.location_mgr)
        self.tab_widget.addTab(self.map_tab, "Bản đồ")

        self.main_layout.addWidget(self.tab_widget, stretch=3)
        self.main_layout.addWidget(self.meta_panel, stretch=1)

    def _connect_signals(self):
        """Kết nối tất cả signals (chung cho cả hai trường hợp)"""
        self.processor.metadata_updated.connect(self.meta_panel.update_metadata)
        self.processor.image_processed.connect(self.update_bev_display)
        self.processor.roi1_updated.connect(self.update_roi_table)
        self.processor.pothole_saved.connect(self.saved_widget.update_saved_pothole)
        self.processor.pothole_saved.connect(self.on_pothole_saved)
        self.processor.data_refresh.connect(self.data_tab.load_data)

        self.saved_widget.image_clicked.connect(self.on_saved_image_click)
        self.data_tab.image_clicked.connect(self.on_data_image_clicked)

        self.meta_panel.pothole_toggle.toggled.connect(self.toggle_pothole_detection)

        self.udp_thread.change_pixmap_signal.connect(self.processor.process_frame)
        self.udp_thread.connection_status_signal.connect(self.meta_panel.set_status)
        self.udp_thread.connection_status_signal.connect(self.on_connection_status)

    def update_rois(self):
        center_y1 = int(self.roi1_center_y_ratio * self.bev_h)
        half_h1 = int(self.roi1_height_ratio * self.bev_h / 2)
        self.roi1_rect = (0, max(0, center_y1 - half_h1), self.bev_w, min(self.bev_h, center_y1 + half_h1))
        center_y2 = int(self.roi2_center_y_ratio * self.bev_h)
        half_h2 = int(self.roi2_height_ratio * self.bev_h / 2)
        self.roi2_rect = (0, max(0, center_y2 - half_h2), self.bev_w, min(self.bev_h, center_y2 + half_h2))
        if hasattr(self, 'bird_label'):
            if self.pothole_detection_enabled:
                self.bird_label.roi_rects = [(self.roi1_rect, QColor(0, 255, 255)), (self.roi2_rect, QColor(255, 255, 0))]
            else:
                self.bird_label.roi_rects = []
            self.bird_label.update()
        if hasattr(self, 'processor'):
            self.processor.set_rois(self.roi1_rect, self.roi2_rect, self.bev_w, self.bev_h)

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pothole_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER,
                timestamp TEXT NOT NULL,
                area_cm2 REAL NOT NULL,
                depth_cm REAL NOT NULL,
                volume_cm3 REAL NOT NULL,
                gps_lat REAL NOT NULL,
                gps_lon REAL NOT NULL,
                image_path TEXT NOT NULL
            )
        ''')
        cursor.execute("PRAGMA table_info(pothole_records)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'volume_cm3' not in columns:
            cursor.execute("ALTER TABLE pothole_records ADD COLUMN volume_cm3 REAL DEFAULT 0")
        conn.commit()
        conn.close()

    def load_data(self):
        self.data_tab.load_data()
        self.map_tab.refresh_map()

    def toggle_pothole_detection(self, enabled):
        self.pothole_detection_enabled = enabled
        self.processor.set_pothole_detection(enabled)

        if hasattr(self, 'bird_label'):
            if not enabled:
                self.bird_label.roi_rects = []
                self.saved_widget.image_label.setText("Tắt phát hiện")
                self.saved_widget.info_label.clear()
                self.meta_panel.update_pothole_stats(0, 0.0)
                self.meta_panel.lbl_pothole.setText("0.0 cm")
            else:
                self.bird_label.roi_rects = [(self.roi1_rect, QColor(0, 255, 255)),
                                            (self.roi2_rect, QColor(255, 255, 0))]
                self.saved_widget.image_label.setText("Chưa có ổ gà nào được lưu")
            self.bird_label.update()

    def update_bev_display(self, image, active_tracks):
        self.frame_count += 1
        now = time.time()
        if now - self.last_time >= 1.0:
            self.meta_panel.set_fps(self.frame_count)
            self.frame_count, self.last_time = 0, now
        pixmap = self.convert_cv_qt(image)
        self.bird_label.setPixmap(pixmap)

    def update_roi_table(self, roi1_tracks_data):
        count, total_area = self.roi_table_widget.update_data(roi1_tracks_data)
        self.meta_panel.update_pothole_stats(count, total_area)

    def convert_cv_qt(self, cv_img):
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QPixmap.fromImage(QImage(rgb.data, w, h, ch*w, QImage.Format_RGB888))

    def on_saved_image_click(self, lat, lon, track_id):
        self.tab_widget.setCurrentIndex(2)  # Map tab
        self.map_tab.focus_on_pothole(lat, lon)

    def on_data_image_clicked(self, db_id, lat, lon):
        self.map_tab.fill_panel_by_db_id(db_id)
        self.tab_widget.setCurrentIndex(2)
        self.map_tab.focus_on_pothole(lat, lon)

    def on_pothole_saved(self, pothole_id):
        row = self.db.get_pothole_by_id(pothole_id)
        if row:
            lat = row[5]
            lon = row[6]
            self.map_tab.add_new_pothole(pothole_id, lat, lon)

    def on_connection_status(self, status):
        if status == "Disconnected":
            self.meta_panel.reset_all_display()
            self.frame_count = 0
            self.last_time = time.time()
            self.meta_panel.set_fps(0)
            if hasattr(self.roi_table_widget, 'clear'):
                self.roi_table_widget.clear()
            self.saved_widget.image_label.setText("Chưa có ổ gà nào được lưu")
            self.saved_widget.info_label.clear()

    def closeEvent(self, event):
        self.udp_thread.stop()
        self.processor_thread.quit()
        self.processor_thread.wait()
        event.accept()