from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QTableWidget, QTableWidgetItem, QAbstractItemView

class ROITableWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Các ổ gà trong vùng 1", parent)
        self.setStyleSheet("color: #0ff; font-weight: bold;")
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Area (cm²)", "Max Area (cm²)", "BBox"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #f5f6fa;
                color: #2f3640;
                gridline-color: #dcdde1;
                border: 1px solid #7f8c8d;
                selection-background-color: #d1d8e0;
                selection-color: black;
            }
            QHeaderView::section {
                background-color: #dcdde1;
                color: #2f3640;
                padding: 5px;
                border: 1px solid #bdc3c7;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.table)

    def update_data(self, roi1_tracks_data):
        self.table.setRowCount(0)
        total_area = 0
        for idx, t in enumerate(roi1_tracks_data):
            self.table.insertRow(idx)
            self.table.setItem(idx, 0, QTableWidgetItem(str(t['id'])))
            self.table.setItem(idx, 1, QTableWidgetItem(f"{t['area_cm2']:.1f}"))
            self.table.setItem(idx, 2, QTableWidgetItem(f"{t['max_area_cm2']:.1f}"))
            self.table.setItem(idx, 3, QTableWidgetItem(str(t['box'])))
            total_area += t['area_cm2']
        return len(roi1_tracks_data), total_area