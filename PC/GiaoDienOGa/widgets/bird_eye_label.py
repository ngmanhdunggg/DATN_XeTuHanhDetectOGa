from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt

class BirdEyeLabel(QLabel):
    def __init__(self, roi_rects=None, parent=None):
        super().__init__(parent)
        self.roi_rects = roi_rects if roi_rects is not None else []
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black; border: 2px solid #34495e;")
        self.setScaledContents(False)
        self.pixmap = None

    def setPixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self.pixmap and not self.pixmap.isNull():
            painter = QPainter(self)
            scaled_pix = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled_pix.width()) // 2
            y = (self.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)

            img_w = self.pixmap.width()
            img_h = self.pixmap.height()
            scale = min(self.width() / img_w, self.height() / img_h)
            offset_x = (self.width() - img_w * scale) / 2
            offset_y = (self.height() - img_h * scale) / 2

            for (rect, color) in self.roi_rects:
                x1, y1, x2, y2 = rect
                rx1 = offset_x + x1 * scale
                ry1 = offset_y + y1 * scale
                rx2 = offset_x + x2 * scale
                ry2 = offset_y + y2 * scale
                painter.setPen(QPen(color, 2))
                painter.drawRect(int(rx1), int(ry1), int(rx2 - rx1), int(ry2 - ry1))
        else:
            super().paintEvent(event)