import cv2
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap, QImage

class SavedPotholeWidget(QGroupBox):
    image_clicked = pyqtSignal(float, float, int)   # lat, lon, track_id

    def __init__(self, parent=None):
        super().__init__("Ổ gà vừa được lưu", parent)
        self.setStyleSheet("color: #1abc9c; font-weight: bold;")
        layout = QVBoxLayout(self)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedHeight(200)
        self.image_label.setStyleSheet("background-color: black; border: 1px solid #1abc9c;")
        self.image_label.setText("Chưa có ổ gà nào được lưu")
        self.image_label.mousePressEvent = self.on_image_click

        self.info_label = QTextEdit()
        self.info_label.setReadOnly(True)
        self.info_label.setMaximumHeight(150)
        self.info_label.setStyleSheet("background-color: #34495e; color: #ecf0f1;")

        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)

        self.last_pothole = None  # (lat, lon, track_id)

    def update_saved_pothole(self, info):
        if info['image'] is not None:
            crop_rgb = cv2.cvtColor(info['image'], cv2.COLOR_BGR2RGB)
            h, w, ch = crop_rgb.shape
            qimg = QImage(crop_rgb.data, w, h, ch*w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.image_label.setPixmap(pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        text = f"""Track ID: {info['track_id']}
GPS: ({info['lat']:.6f}, {info['lon']:.6f})
Diện tích max: {info['area']:.1f} cm²
Độ sâu: {info['depth']:.1f} cm
Thể tích: {info['volume']:.1f} cm³
Thời gian phát hiện: {info['timestamp']}"""
        self.info_label.setPlainText(text)
        self.last_pothole = (info['lat'], info['lon'], info['track_id'])

    def on_image_click(self, event):
        if self.last_pothole:
            lat, lon, track_id = self.last_pothole
            self.image_clicked.emit(lat, lon, track_id)