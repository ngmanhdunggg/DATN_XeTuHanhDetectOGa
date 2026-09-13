import os
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal, Qt, QDateTime
from PyQt5.QtGui import QPixmap
from shapely.geometry import Point
from PyQt5.QtGui import QPixmap, QPalette, QColor

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from database.database import DatabaseManager
from location_manager import LocationManager


class DataTab(QWidget):
    image_clicked = pyqtSignal(int, float, float)
    data_changed = pyqtSignal()

    def __init__(self, db_path, location_mgr=None, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager(db_path)
        self.location_mgr = location_mgr
        self.current_rows = []
        self.filtered_rows = []

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Khung lọc dữ liệu
        filter_group = QGroupBox("Bộ lọc dữ liệu")
        filter_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1abc9c; }")
        group_layout = QVBoxLayout(filter_group)
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 20, 10, 10)

        # Hàng 1: thời gian
        row_time = QHBoxLayout()
        row_time.addWidget(QLabel("Thời gian từ:"))

        def create_styled_calendar():
            cal = QCalendarWidget()
            cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
            
            # Thiết lập Palette cơ bản
            palette = cal.palette()
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Text, Qt.black)
            cal.setPalette(palette)
            
            # CSS tập trung vào độ tương phản cao cho Header
            cal.setStyleSheet("""
                /* Toàn bộ bảng ngày */
                QCalendarWidget QTableView {
                    background-color: #2c3e50;
                    color: #ecf0f1;
                    selection-background-color: #1abc9c;
                    selection-color: #ffffff;
                    font: 11pt "Segoe UI";
                    outline: 0;
                }

                /* Thanh tiêu đề chứa Thứ (T2-CN) */
                QCalendarWidget QHeaderView::section {
                    background-color: #ffffff;    /* Nền trắng */
                    color: #000000;              /* Chữ đen */
                    font: bold 10pt "Segoe UI";
                    padding: 5px;
                    border: none;
                }

                /* Thanh điều hướng phía trên (Tháng/Năm) */
                QCalendarWidget QWidget#qt_calendar_navigationbar {
                    background-color: #1e2a36;
                    min-height: 35px;
                }

                QCalendarWidget QToolButton {
                    color: #ffffff;
                    font: bold 10pt "Segoe UI";
                    background-color: transparent;
                    border: none;
                    margin: 5px;
                }
            """)

            # --- ÉP MÀU CHỮ BẰNG CODE (Giải quyết triệt để chữ mờ) ---
            from PyQt5.QtGui import QTextCharFormat, QColor
            
            # 1. Định dạng chung cho Header (T2-CN)
            header_fmt = QTextCharFormat()
            header_fmt.setForeground(QColor("black"))
            header_fmt.setFontWeight(75) # Bold
            cal.setHeaderTextFormat(header_fmt)

            # 2. Định dạng riêng cho ngày thường (T2-T6) để chắc chắn không bị mờ
            workday_fmt = QTextCharFormat()
            workday_fmt.setForeground(QColor("#f94343"))
            workday_fmt.setFontWeight(75)

            # 3. Định dạng cho cuối tuần (T7-CN) giữ màu đỏ cho dễ nhìn
            weekend_fmt = QTextCharFormat()
            weekend_fmt.setForeground(QColor("#e74c3c")) # Màu đỏ đậm
            weekend_fmt.setFontWeight(75)

            # Áp dụng định dạng cho từng thứ trong tuần
            cal.setWeekdayTextFormat(Qt.Monday, workday_fmt)
            cal.setWeekdayTextFormat(Qt.Tuesday, workday_fmt)
            cal.setWeekdayTextFormat(Qt.Wednesday, workday_fmt)
            cal.setWeekdayTextFormat(Qt.Thursday, workday_fmt)
            cal.setWeekdayTextFormat(Qt.Friday, workday_fmt)
            cal.setWeekdayTextFormat(Qt.Saturday, weekend_fmt)
            cal.setWeekdayTextFormat(Qt.Sunday, weekend_fmt)

            return cal

        self.start_date = QDateTimeEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setCalendarWidget(create_styled_calendar())
        self.start_date.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.start_date.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.start_date.setMinimumWidth(160)
        row_time.addWidget(self.start_date)

        row_time.addWidget(QLabel(" đến: "))
        self.end_date = QDateTimeEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setCalendarWidget(create_styled_calendar())
        self.end_date.setDateTime(QDateTime.currentDateTime())
        self.end_date.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.end_date.setMinimumWidth(160)
        row_time.addWidget(self.end_date)
        row_time.addStretch()
        group_layout.addLayout(row_time)

        # Hàng 2: vị trí và nút
        row_pos = QHBoxLayout()
        self.cbo_province = QComboBox()
        self.cbo_province.addItem("-- Tỉnh/Thành phố --")
        self.cbo_province.setMinimumWidth(200)
        self.cbo_ward = QComboBox()
        self.cbo_ward.addItem("-- Phường/Xã --")
        self.cbo_ward.setMinimumWidth(200)

        if self.location_mgr:
            self.cbo_province.addItems(self.location_mgr.get_province_names())
            self.cbo_province.currentIndexChanged.connect(self.on_province_changed)
            row_pos.addWidget(QLabel("Vị trí: "))
            row_pos.addWidget(self.cbo_province)
            row_pos.addWidget(self.cbo_ward)

        self.btn_filter = QPushButton("Lọc")
        self.btn_filter.setFixedWidth(70)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setFixedWidth(70)
        self.btn_export = QPushButton("Xuất Excel")
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        if not PANDAS_AVAILABLE:
            self.btn_export.setEnabled(False)

        row_pos.addWidget(self.btn_filter)
        row_pos.addWidget(self.btn_reset)
        row_pos.addWidget(self.btn_export)
        row_pos.addStretch()
        group_layout.addLayout(row_pos)
        layout.addWidget(filter_group)

        # Bảng dữ liệu
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(["Chọn", "ID", "Track ID", "Thời gian phát hiện",
                                              "Diện tích", "Độ sâu", "Thể tích", "GPS", "Đường dẫn ảnh"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #f5f6fa;
                color: #2f3640;
                gridline-color: #dcdde1;
                border: 1px solid #7f8c8d;
            }
            QHeaderView::section {
                background-color: #dcdde1;
                color: black;
                font-weight: bold;
            }
        """)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table, stretch=1)

        # Chi tiết ảnh và text
        detail_layout = QHBoxLayout()
        self.image_label = QLabel()
        self.image_label.setFixedSize(250, 250)
        self.image_label.setStyleSheet("background-color: black; border: 1px solid #1abc9c; color: white;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("Chọn bản ghi để xem ảnh")
        self.image_label.mousePressEvent = self.on_image_click

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFixedHeight(250)
        self.info_text.setStyleSheet("background-color: #34495e; color: #ecf0f1; font-family: Consolas; font-size: 10pt;")

        detail_layout.addWidget(self.image_label)
        detail_layout.addWidget(self.info_text)
        layout.addLayout(detail_layout)

        # Hàng nút chức năng (chỉ giữ nút xóa các mục đã chọn)
        btn_action_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Chọn tất cả")
        self.btn_clear_all = QPushButton("Bỏ chọn tất cả")
        self.btn_edit = QPushButton("Sửa bản ghi")
        self.btn_delete_selected = QPushButton("Xóa các mục đã chọn")
        self.btn_delete_selected.setStyleSheet("background-color: #c0392b; color: white;")

        btn_action_layout.addWidget(self.btn_select_all)
        btn_action_layout.addWidget(self.btn_clear_all)
        btn_action_layout.addWidget(self.btn_edit)
        btn_action_layout.addWidget(self.btn_delete_selected)
        layout.addLayout(btn_action_layout)

        # Kết nối sự kiện
        self.start_date.dateTimeChanged.connect(self.validate_dates)
        self.end_date.dateTimeChanged.connect(self.validate_dates)
        self.btn_edit.clicked.connect(self.edit_record)
        self.btn_delete_selected.clicked.connect(self.delete_selected_records)
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_clear_all.clicked.connect(self.clear_all)
        self.btn_filter.clicked.connect(self.apply_filter)
        self.btn_reset.clicked.connect(self.reset_filter)
        self.btn_export.clicked.connect(self.export_to_excel)

    def validate_dates(self):
        if self.start_date.dateTime() > self.end_date.dateTime():
            self.end_date.setDateTime(self.start_date.dateTime())

    def on_province_changed(self):
        prov = self.cbo_province.currentText()
        self.cbo_ward.blockSignals(True)
        self.cbo_ward.clear()
        self.cbo_ward.addItem("-- Phường/Xã --")
        if prov != "-- Tỉnh/Thành phố --" and self.location_mgr:
            wards = self.location_mgr.get_wards_by_province(prov)
            self.cbo_ward.addItems(wards)
        self.cbo_ward.blockSignals(False)

    def apply_filter(self):
        start_dt = self.start_date.dateTime().toPyDateTime()
        end_dt = self.end_date.dateTime().toPyDateTime()
        if start_dt > end_dt:
            QMessageBox.warning(self, "Lỗi thời gian", "Thời gian bắt đầu phải trước thời gian kết thúc!")
            return

        prov = self.cbo_province.currentText()
        ward = self.cbo_ward.currentText()

        location_geom = None
        if self.location_mgr:
            if ward != "-- Phường/Xã --":
                location_geom = self.location_mgr.get_geometry(ward, 'ward')
            elif prov != "-- Tỉnh/Thành phố --":
                location_geom = self.location_mgr.get_geometry(prov, 'province')
            if location_geom is not None:
                location_geom = location_geom.buffer(0)
                location_geom = location_geom.simplify(0.001, preserve_topology=True)

        filtered = []
        for row in self.current_rows:
            ts_str = row[2]
            lat = row[6]
            lon = row[7]

            try:
                ts_dt = datetime.strptime(ts_str, "%d-%m-%Y %H:%M:%S")
            except Exception:
                continue
            if not (start_dt <= ts_dt <= end_dt):
                continue

            if location_geom is not None:
                point = Point(lon, lat)
                if not location_geom.buffer(1e-5).intersects(point):
                    continue

            filtered.append(row)

        self.filtered_rows = filtered
        self.display_rows(self.filtered_rows)

    def reset_filter(self):
        self.start_date.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.end_date.setDateTime(QDateTime.currentDateTime())
        if self.location_mgr:
            self.cbo_province.setCurrentIndex(0)
            self.cbo_ward.clear()
            self.cbo_ward.addItem("-- Phường/Xã --")
        self.filtered_rows = self.current_rows[:]
        self.display_rows(self.filtered_rows)

    def load_data(self):
        self.current_rows = self.db.load_all_records()
        self.filtered_rows = self.current_rows[:]
        self.display_rows(self.filtered_rows)
        self.data_changed.emit()

    def display_rows(self, rows):
        self.table.setRowCount(0)
        for row in rows:
            record_id, track_id, ts, area, depth, volume, lat, lon, img_path = row
            idx = self.table.rowCount()
            self.table.insertRow(idx)

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            self.table.setItem(idx, 0, chk_item)

            self.table.setItem(idx, 1, QTableWidgetItem(str(record_id)))
            self.table.setItem(idx, 2, QTableWidgetItem(str(track_id)))
            self.table.setItem(idx, 3, QTableWidgetItem(ts))
            self.table.setItem(idx, 4, QTableWidgetItem(f"{area:.1f}"))
            self.table.setItem(idx, 5, QTableWidgetItem(f"{depth:.1f}"))
            self.table.setItem(idx, 6, QTableWidgetItem(f"{volume:.1f}"))
            self.table.setItem(idx, 7, QTableWidgetItem(f"{lat:.6f}, {lon:.6f}"))
            self.table.setItem(idx, 8, QTableWidgetItem(img_path))
        self.table.resizeColumnsToContents()

    def show_context_menu(self, pos):
        menu = QMenu()
        edit_action = menu.addAction("Sửa bản ghi")
        # Đã xóa mục "Xóa bản ghi"
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == edit_action:
            self.edit_record()

    def get_selected_record_ids(self):
        ids = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk is not None and chk.checkState() == Qt.Checked:
                id_item = self.table.item(row, 1)
                if id_item is not None:
                    ids.append(int(id_item.text()))
        return ids

    def select_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.Checked)

    def clear_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.Unchecked)

    def delete_selected_records(self):
        ids = self.get_selected_record_ids()
        if not ids:
            QMessageBox.warning(self, "Chọn bản ghi", "Vui lòng chọn ít nhất một bản ghi để xóa.")
            return

        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"SELECT id, image_path FROM pothole_records WHERE id IN ({placeholders})", ids)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return

        msg = f"Bạn có chắc muốn xóa {len(ids)} bản ghi?\nID: {', '.join(map(str, ids))}"
        reply = QMessageBox.question(self, "Xác nhận xóa", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for rec_id, img_path in rows:
                if img_path and os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                        print(f"Đã xóa ảnh: {img_path}")
                    except Exception as e:
                        print(f"Lỗi xóa ảnh {img_path}: {e}")
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM pothole_records WHERE id IN ({placeholders})", ids)
            conn.commit()
            conn.close()
            self.load_data()
            QMessageBox.information(self, "Thành công", f"Đã xóa {len(ids)} bản ghi")

    def edit_record(self):
        ids = self.get_selected_record_ids()
        if len(ids) != 1:
            QMessageBox.warning(self, "Chọn bản ghi", "Vui lòng chọn đúng một bản ghi để sửa.")
            return
        rec_id = ids[0]

        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, area_cm2, depth_cm, gps_lat, gps_lon FROM pothole_records WHERE id=?", (rec_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return
        ts, area, depth, lat, lon = row

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Sửa bản ghi ID {rec_id}")
        layout = QFormLayout(dialog)

        ts_edit = QDateTimeEdit()
        try:
            dt = datetime.strptime(ts, "%d-%m-%Y %H:%M:%S")
        except:
            dt = datetime.now()
        ts_edit.setDateTime(QDateTime(dt))
        ts_edit.setDisplayFormat("dd/MM/yyyy HH:mm:ss")

        area_edit = QLineEdit(str(area))
        depth_edit = QLineEdit(str(depth))
        lat_edit = QLineEdit(str(lat))
        lon_edit = QLineEdit(str(lon))

        layout.addRow("Thời gian phát hiện:", ts_edit)
        layout.addRow("Diện tích (cm²):", area_edit)
        layout.addRow("Độ sâu (cm):", depth_edit)
        layout.addRow("Vĩ độ:", lat_edit)
        layout.addRow("Kinh độ:", lon_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            try:
                new_ts = ts_edit.dateTime().toPyDateTime().strftime("%d-%m-%Y %H:%M:%S")
                new_area = float(area_edit.text())
                new_depth = float(depth_edit.text())
                new_volume = new_area * new_depth
                new_lat = float(lat_edit.text())
                new_lon = float(lon_edit.text())
            except ValueError:
                QMessageBox.warning(self, "Lỗi nhập liệu", "Vui lòng nhập số hợp lệ cho các trường.")
                return

            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pothole_records
                SET timestamp=?, area_cm2=?, depth_cm=?, volume_cm3=?, gps_lat=?, gps_lon=?
                WHERE id=?
            """, (new_ts, new_area, new_depth, new_volume, new_lat, new_lon, rec_id))
            conn.commit()
            conn.close()
            self.load_data()
            QMessageBox.information(self, "Thành công", f"Đã cập nhật bản ghi ID {rec_id}")

    def on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        record_id = self.table.item(row, 1).text()
        track_id = self.table.item(row, 2).text()
        timestamp = self.table.item(row, 3).text()
        area = self.table.item(row, 4).text()
        depth = self.table.item(row, 5).text()
        volume = self.table.item(row, 6).text()
        gps = self.table.item(row, 7).text()
        img_path = self.table.item(row, 8).text()

        try:
            lat_str, lon_str = gps.split(',')
            lat = float(lat_str.strip())
            lon = float(lon_str.strip())
        except:
            lat, lon = 0.0, 0.0

        self.view_pothole_image(img_path, record_id, track_id, timestamp, area, depth, volume, gps, lat, lon)

    def view_pothole_image(self, img_path, record_id, track_id, timestamp, area, depth, volume, gps, lat, lon):
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_label.setText("Không tìm thấy ảnh")

        location_text = "Không xác định"
        if self.location_mgr and lat != 0.0 and lon != 0.0:
            try:
                ward = self.location_mgr.get_location_name_by_point(lat, lon, 'ward')
                province = self.location_mgr.get_location_name_by_point(lat, lon, 'province')
                if province:
                    if ward:
                        location_text = f"{ward}, {province}"
                    else:
                        location_text = province
            except:
                pass

        info_text = f"""<b>ID:</b> {record_id}<br>
<b>Track ID:</b> {track_id}<br>
<b>Thời gian phát hiện:</b> {timestamp}<br>
<b>Diện tích:</b> {area} cm²<br>
<b>Độ sâu:</b> {depth} cm<br>
<b>Thể tích:</b> {volume} cm³<br>
<b>GPS:</b> {gps}<br>
<b>Địa chỉ:</b> {location_text}<br>
<b>Đường dẫn ảnh:</b> {img_path}"""
        self.info_text.setHtml(info_text)

    def on_image_click(self, event):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        try:
            db_id = int(self.table.item(row, 1).text())
            gps_text = self.table.item(row, 7).text()
            lat_str, lon_str = gps_text.split(',')
            lat = float(lat_str.strip())
            lon = float(lon_str.strip())
            if lat == 0.0 and lon == 0.0:
                QMessageBox.warning(self, "Không có tọa độ GPS",
                                    "Bản ghi này không có tọa độ GPS.")
                return
            self.image_clicked.emit(db_id, lat, lon)
        except Exception as e:
            print(f"Lỗi khi xử lý click ảnh: {e}")

    def export_to_excel(self):
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Thiếu thư viện",
                                "Cần cài đặt pandas và openpyxl.\nChạy lệnh: pip install pandas openpyxl")
            return
        if not self.filtered_rows:
            QMessageBox.information(self, "Xuất Excel", "Không có dữ liệu để xuất.")
            return

        data = []
        for row in self.filtered_rows:
            record_id, track_id, ts, area, depth, volume, lat, lon, img_path = row
            location_str = "N/A"
            if self.location_mgr and lat != 0 and lon != 0:
                ward_name = self.location_mgr.get_location_name_by_point(lat, lon, 'ward')
                province_name = self.location_mgr.get_location_name_by_point(lat, lon, 'province')
                if province_name:
                    if ward_name:
                        location_str = f"{ward_name}, {province_name}"
                    else:
                        location_str = province_name
            data.append({
                "DB ID": record_id,
                "Thời gian phát hiện": ts,
                "Diện tích (cm²)": area,
                "Độ sâu (cm)": depth,
                "Thể tích (cm³)": volume,
                "Vĩ độ": lat,
                "Kinh độ": lon,
                "Địa điểm": location_str,
                "Đường dẫn ảnh": img_path
            })

        df = pd.DataFrame(data)
        file_path, _ = QFileDialog.getSaveFileName(self, "Xuất Excel", "potholes_data.xlsx", "Excel files (*.xlsx)")
        if file_path:
            try:
                df.to_excel(file_path, index=False, engine='openpyxl')
                QMessageBox.information(self, "Thành công", f"Đã xuất {len(df)} bản ghi ra {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi xuất file", str(e))