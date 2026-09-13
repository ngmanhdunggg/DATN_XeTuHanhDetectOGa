from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRect

class Switch(QCheckBox):
    """Công tắc bật/tắt giống iOS, có hiển thị text bên cạnh"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        switch_width = 50
        switch_height = 28
        spacing = 8

        if self.isChecked():
            bg_color = QColor(52, 199, 89)
        else:
            bg_color = QColor(224, 224, 224)
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, switch_width, switch_height, switch_height/2, switch_height/2)

        handle_radius = switch_height - 4
        if self.isChecked():
            handle_x = switch_width - handle_radius - 2
        else:
            handle_x = 2
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(handle_x, 2, handle_radius, handle_radius)

        text = self.text()
        if text:
            painter.setPen(QPen(QColor(236, 240, 241)))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            text_rect = QRect(switch_width + spacing, 0, self.width() - switch_width - spacing, self.height())
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)

        self.setFixedSize(switch_width + spacing + painter.fontMetrics().width(text) + 10, switch_height)

    def mousePressEvent(self, event):
        self.setChecked(not self.isChecked())
        self.update()

    def mouseReleaseEvent(self, event):
        self.toggled.emit(self.isChecked())