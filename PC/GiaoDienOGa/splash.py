# splash.py
import sys
import os
import sqlite3
import traceback
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QPixmap

# Import các module của dự án
from threads.udp_thread import UDPVideoThread
from threads.processor_thread import PotholeProcessor
from database.database import DatabaseManager
from location_manager import LocationManager


class SplashScreen(QDialog):
    """Cửa sổ splash hiển thị logo với thanh tiến trình và phần trăm nằm đè bên trong ảnh"""
    def __init__(self, image_path):
        super().__init__()
        # Thiết lập cửa sổ không viền
        #self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setModal(False)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 1. Layout chính để chứa nhãn ảnh (Logo)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)

        # 2. Thiết lập Nhãn ảnh (Logo)
        self.image_label = QLabel()
        pixmap = QPixmap(image_path)
        
        # Kích thước khung Splash (Khớp với tỉ lệ ảnh đồ án của bạn)
        self.img_w, self.img_h = 800, 450 
        
        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.img_w, self.img_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        else:
            pixmap = QPixmap(self.img_w, self.img_h)
            pixmap.fill(Qt.gray)
            
        self.image_label.setPixmap(pixmap)
        main_layout.addWidget(self.image_label)

        # 3. Tạo Progress Bar LÀ CON CỦA image_label (để hiển thị đè lên)
        self.progress_bar = QProgressBar(self.image_label) 
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # Cấu hình thanh progress mỏng nằm sát đáy ảnh
        self.pb_height = 10 
        self.progress_bar.setFixedHeight(self.pb_height)
        self.progress_bar.setFixedWidth(self.img_w)
        self.progress_bar.move(0, self.img_h - self.pb_height)

        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: rgba(255, 255, 255, 30); 
                text-align: center;
                color: transparent;
            }}
            QProgressBar::chunk {{
                background-color: #1abc9c;
            }}
        """)

        # 4. Nhãn phần trăm (Hiển thị đè lên ảnh, căn giữa theo chiều ngang)
        self.percent_label = QLabel("0%", self.image_label)
        self.percent_label.setStyleSheet("""
            color: white; 
            font-weight: bold; 
            font-size: 13px; 
            background: rgba(0, 0, 0, 160); 
            padding: 2px 12px;
            border-radius: 5px;
        """)
        
        # Cập nhật vị trí ban đầu
        self.update_label_position()

        # Cố định kích thước Dialog và căn giữa màn hình
        self.setFixedSize(self.img_w, self.img_h)
        self.center_on_screen()

    def center_on_screen(self):
        """Căn giữa cửa sổ trên màn hình (Sửa lỗi AttributeError)"""
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2,
                  (screen.height() - self.height()) // 2)

    def update_label_position(self):
        """Tính toán tọa độ để đưa nhãn phần trăm ra CHÍNH GIỮA chiều ngang"""
        self.percent_label.adjustSize()
        
        # Công thức căn giữa: (Chiều rộng cha - Chiều rộng con) / 2
        x = (self.img_w - self.percent_label.width()) // 2
        
        # Tọa độ y: Nằm ngay phía trên thanh progress bar (cách 5px)
        y = self.img_h - self.pb_height - self.percent_label.height() - 5
        
        self.percent_label.move(x, y)

    def update_progress(self, value):
        """Cập nhật giá trị tiến trình từ thread khởi tạo"""
        self.progress_bar.setValue(value)
        self.percent_label.setText(f"{value}%")
        
        # Cập nhật lại vị trí vì kích thước chữ thay đổi (ví dụ từ 9% lên 10%)
        self.update_label_position()
        
        QApplication.processEvents()


class AppInitializer(QObject):
    """Chạy các tác vụ khởi tạo nặng trong thread riêng, emit tiến trình"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)

    def run(self):
        try:
            # Bước 1: Database
            self.progress.emit(5)
            db_path = os.path.join("database", "potholes.db")
            os.makedirs("database", exist_ok=True)
            self._init_database_schema(db_path)
            self.progress.emit(15)

            # Bước 2: Thư mục ảnh
            images_dir = os.path.abspath("OGa")
            os.makedirs(images_dir, exist_ok=True)
            self.progress.emit(25)

            # Bước 3: Location Manager
            geojson_base = os.path.join("database", "geojson")
            location_mgr = None
            if os.path.exists(geojson_base):
                location_mgr = LocationManager(geojson_base)
            self.progress.emit(35)

            # Bước 4: Cấu hình BEV/ROI
            bev_w, bev_h = 400, 600
            pixel_to_cm2 = (60.0 / 400.0) ** 2
            roi1_ratio, roi1_h_ratio = 0.42, 0.2
            roi2_ratio, roi2_h_ratio = 0.82, 0.3

            roi1_rect = (0, max(0, int(roi1_ratio * bev_h) - int(roi1_h_ratio * bev_h / 2)),
                         bev_w, min(bev_h, int(roi1_ratio * bev_h) + int(roi1_h_ratio * bev_h / 2)))
            roi2_rect = (0, max(0, int(roi2_ratio * bev_h) - int(roi2_h_ratio * bev_h / 2)),
                         bev_w, min(bev_h, int(roi2_ratio * bev_h) + int(roi2_h_ratio * bev_h / 2)))
            self.progress.emit(45)

            # Bước 5: Khởi tạo AI Processor (Nặng nhất)
            processor_thread = QThread()
            processor = PotholeProcessor(pixel_to_cm2, db_path, images_dir)
            processor.moveToThread(processor_thread)
            processor_thread.start()

            self.progress.emit(55)
            processor.init_models(
                os.path.join("model", "epoch62.pt"),
                os.path.join("model", "model_249.pth")
            )
            self.progress.emit(85)
            processor.set_rois(roi1_rect, roi2_rect, bev_w, bev_h)

            # Bước 6: UDP Video
            udp_thread = UDPVideoThread(5557)
            self.progress.emit(100)

            # Đóng gói dữ liệu trả về cho MainWindow
            result = {
                'db_path': db_path, 'images_dir': images_dir, 'location_mgr': location_mgr,
                'processor': processor, 'processor_thread': processor_thread, 'udp_thread': udp_thread,
                'bev_w': bev_w, 'bev_h': bev_h, 'pixel_to_cm2': pixel_to_cm2,
                'roi1_rect': roi1_rect, 'roi2_rect': roi2_rect,
                'roi1_center_y_ratio': roi1_ratio, 'roi1_height_ratio': roi1_h_ratio,
                'roi2_center_y_ratio': roi2_ratio, 'roi2_height_ratio': roi2_h_ratio,
            }
            self.finished.emit(result)
        except Exception:
            traceback.print_exc()
            self.finished.emit({})

    def _init_database_schema(self, db_path):
        conn = sqlite3.connect(db_path)
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
        cols = [col[1] for col in cursor.fetchall()]
        if 'volume_cm3' not in cols:
            cursor.execute("ALTER TABLE pothole_records ADD COLUMN volume_cm3 REAL DEFAULT 0")
        conn.commit()
        conn.close()