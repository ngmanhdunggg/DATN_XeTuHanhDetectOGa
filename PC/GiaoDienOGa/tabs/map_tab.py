import os
import json

from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal, Qt, QObject, pyqtSlot
from PyQt5.QtGui import QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from shapely.geometry import Point, mapping, box

from bridge import PotholeBridge
from database.database import DatabaseManager
from location_manager import LocationManager


class MapBridge(QObject):
    markers_ready = pyqtSignal(str)
    geometry_ready = pyqtSignal(str)

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.full_geometry = None
        self.filtered_ids = None

    def set_full_geometry(self, geom):
        self.full_geometry = geom

    def set_filtered_ids(self, ids_set):
        self.filtered_ids = ids_set

    @pyqtSlot(float, float, float, float, int)
    def load_markers(self, sw_lat, sw_lng, ne_lat, ne_lng, zoom):
        if zoom < 10:
            self.markers_ready.emit(json.dumps([]))
            return
        if zoom < 12:
            limit = 500
        elif zoom < 14:
            limit = 800
        else:
            limit = None

        rows = self.db.get_records_in_bbox(sw_lat, ne_lat, sw_lng, ne_lng, limit)
        markers = [{"id": r[0], "lat": r[1], "lon": r[2]} for r in rows if r[1] != 0 and r[2] != 0]

        if self.filtered_ids is not None:
            markers = [m for m in markers if m["id"] in self.filtered_ids]

        self.markers_ready.emit(json.dumps(markers))

    @pyqtSlot(float, float, float, float, int)
    def load_geometry(self, sw_lat, sw_lng, ne_lat, ne_lng, zoom):
        if self.full_geometry is None or self.full_geometry.is_empty:
            self.geometry_ready.emit("null")
            return

        if zoom <= 9:
            tolerance = 0.01
        elif zoom <= 11:
            tolerance = 0.005
        elif zoom <= 13:
            tolerance = 0.001
        elif zoom <= 15:
            tolerance = 0.0001
        else:
            tolerance = 0.000001

        bbox = box(sw_lng, sw_lat, ne_lng, ne_lat)
        try:
            clipped = self.full_geometry.intersection(bbox)
            if clipped.is_empty:
                self.geometry_ready.emit("null")
                return

            simplified = clipped.simplify(tolerance, preserve_topology=True)

            if simplified.geom_type in ['Polygon', 'MultiPolygon']:
                geojson_feature = {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": mapping(simplified),
                        "properties": {}
                    }]
                }
            else:
                self.geometry_ready.emit("null")
                return

            geojson_str = json.dumps(geojson_feature)
            if len(geojson_str) > 1.5 * 1024 * 1024:
                simplified = clipped.simplify(tolerance * 2, preserve_topology=True)
                geojson_feature["features"][0]["geometry"] = mapping(simplified)
                geojson_str = json.dumps(geojson_feature)

            self.geometry_ready.emit(geojson_str)

        except Exception as e:
            print(f"Lỗi geometry: {e}")
            self.geometry_ready.emit("null")


class MapTab(QWidget):
    focus_pothole = pyqtSignal(float, float)

    def __init__(self, db_path, location_mgr=None, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager(db_path)
        self.location_mgr = location_mgr
        self.current_group_records = []
        self.all_records = []
        self.filtered_records = []
        self.current_highlight_geom = None
        self.setup_ui()
        self.load_all_records()
        self.refresh_map()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(5, 5, 5, 5)

        if self.location_mgr:
            filter_widget = QWidget()
            filter_widget.setMaximumHeight(50)
            filter_layout = QHBoxLayout(filter_widget)
            filter_layout.setContentsMargins(5, 2, 5, 2)

            self.cbo_province = QComboBox()
            self.cbo_province.addItem("-- Tất cả --")
            self.cbo_province.addItems(self.location_mgr.get_province_names())
            self.cbo_province.setMinimumWidth(200)
            self.cbo_province.currentIndexChanged.connect(self.on_province_changed)

            self.cbo_ward = QComboBox()
            self.cbo_ward.addItem("-- Tất cả --")
            self.cbo_ward.setMinimumWidth(200)

            self.btn_apply = QPushButton("Lọc")
            self.btn_apply.setFixedWidth(80)
            self.btn_reset = QPushButton("Reset")
            self.btn_reset.setFixedWidth(80)

            filter_layout.addWidget(QLabel("Tỉnh/Thành phố:"))
            filter_layout.addWidget(self.cbo_province)
            filter_layout.addWidget(QLabel("Xã/Phường:"))
            filter_layout.addWidget(self.cbo_ward)
            filter_layout.addWidget(self.btn_apply)
            filter_layout.addWidget(self.btn_reset)
            filter_layout.addStretch()
            layout.addWidget(filter_widget)

            self.btn_apply.clicked.connect(self.apply_filter)
            self.btn_reset.clicked.connect(self.reset_filter)

        splitter = QSplitter(Qt.Horizontal)
        self.map_view = QWebEngineView()
        self.map_view.setMinimumWidth(500)

        self.channel = QWebChannel()
        self.map_view.page().setWebChannel(self.channel)

        self.map_bridge = MapBridge(self.db, self)
        self.channel.registerObject("mapBridge", self.map_bridge)
        self.map_bridge.markers_ready.connect(self.on_markers_ready)
        self.map_bridge.geometry_ready.connect(self.on_geometry_ready)

        self.pothole_bridge = PotholeBridge(self)
        self.channel.registerObject("potholeBridge", self.pothole_bridge)

        right_widget = QWidget()
        right_widget.setMaximumWidth(305)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 5, 0)

        self.map_combo = QComboBox()
        self.map_combo.currentIndexChanged.connect(self.on_combo_changed)

        self.map_info_image = QLabel()
        self.map_info_image.setFixedSize(300, 300)
        self.map_info_image.setStyleSheet("background-color: black; border: 1px solid #1abc9c;")
        self.map_info_image.mousePressEvent = self.on_image_click

        self.map_info_text = QTextEdit()
        self.map_info_text.setReadOnly(True)
        self.map_info_text.setStyleSheet("font-size: 10pt; font-family: Consolas;")

        right_layout.addWidget(QLabel("Chọn ổ gà tại điểm này:"))
        right_layout.addWidget(self.map_combo)
        right_layout.addWidget(QLabel("Ảnh:"))
        right_layout.addWidget(self.map_info_image)
        right_layout.addWidget(QLabel("Chi tiết:"))
        right_layout.addWidget(self.map_info_text)

        splitter.addWidget(self.map_view)
        splitter.addWidget(right_widget)
        splitter.setSizes([700, 400])
        layout.addWidget(splitter)
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)

    def load_all_records(self):
        all_rows = self.db.get_all_map_records()
        self.all_records = [(r[0], r[1], r[2]) for r in all_rows if r[1] != 0 and r[2] != 0]
        self.filtered_records = self.all_records[:]

    def on_province_changed(self):
        prov = self.cbo_province.currentText()
        self.cbo_ward.blockSignals(True)
        self.cbo_ward.clear()
        self.cbo_ward.addItem("-- Tất cả --")
        if prov != "-- Tất cả --" and self.location_mgr:
            wards = self.location_mgr.get_wards_by_province(prov)
            self.cbo_ward.addItems(wards)
        self.cbo_ward.blockSignals(False)

    def apply_filter(self):
        prov = self.cbo_province.currentText()
        ward = self.cbo_ward.currentText()
        if self.location_mgr is None:
            return
        if ward != "-- Tất cả --":
            location_name = ward
            level = 'ward'
        elif prov != "-- Tất cả --":
            location_name = prov
            level = 'province'
        else:
            self.filtered_records = self.all_records[:]
            self.current_highlight_geom = None
            self.map_bridge.set_full_geometry(None)
            self.map_bridge.set_filtered_ids(None)
            self.refresh_map()
            return

        geom = self.location_mgr.get_geometry(location_name, level)
        if geom is None:
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy geometry cho {location_name}")
            self.filtered_records = []
            self.current_highlight_geom = None
            self.map_bridge.set_full_geometry(None)
            self.map_bridge.set_filtered_ids(set())
            self.refresh_map()
            return

        self.current_highlight_geom = geom
        self.map_bridge.set_full_geometry(geom)

        geom_simple = geom.simplify(0.001, preserve_topology=True)
        epsilon = 1e-5
        filtered = []
        for rec in self.all_records:
            rec_id, lat, lon = rec
            point = Point(lon, lat)
            if geom_simple.buffer(epsilon).intersects(point):
                filtered.append(rec)
        self.filtered_records = filtered

        self.map_bridge.set_filtered_ids({rec[0] for rec in filtered})
        self.refresh_map()

    def reset_filter(self):
        if self.location_mgr:
            self.cbo_province.setCurrentIndex(0)
            self.cbo_ward.clear()
            self.cbo_ward.addItem("-- Tất cả --")
            self.filtered_records = self.all_records
            self.current_highlight_geom = None
            self.map_bridge.set_full_geometry(None)
            self.map_bridge.set_filtered_ids(None)
            self.refresh_map()
        else:
            self.refresh_map()

    def refresh_map(self):
        html = self.build_map_html()
        self.map_view.setHtml(html)

    def build_map_html(self):
        vietnam_bounds = [[6.0, 102.0], [24.0, 118.0]]
        if self.current_highlight_geom:
            bounds = self.current_highlight_geom.bounds
            fit_js = f"window.map.fitBounds([[{bounds[1]}, {bounds[0]}], [{bounds[3]}, {bounds[2]}]]);"
        else:
            fit_js = f"window.map.fitBounds({vietnam_bounds});"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>#map{{height:100%;width:100%;position:absolute;}} body{{margin:0;padding:0;height:100%;}}</style>
        </head>
        <body>
            <div id="map"></div>
            <script>
            var map;
            function initMap() {{
                map = L.map('map').setView([15.0, 108.0], 6);
                window.map = map;
                map.setMaxBounds([[6.0, 102.0], [24.0, 118.0]]);
                map.setMinZoom(5);
                map.setMaxZoom(18);
                
                L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&hl=vi', {{
                    attribution: '© Google Maps'
                }}).addTo(map);

                var markerGroup = L.featureGroup().addTo(map);
                var geometryLayer = null;
                var currentGeojson = null;

                function groupMarkers(markers) {{
                    var groups = new Map();
                    markers.forEach(function(m) {{
                        var key = m.lat.toFixed(6) + ',' + m.lon.toFixed(6);
                        if (!groups.has(key)) {{
                            groups.set(key, {{ ids: [], lat: m.lat, lon: m.lon }});
                        }}
                        groups.get(key).ids.push(m.id);
                    }});
                    var result = [];
                    for (var [_, g] of groups.entries()) {{
                        result.push({{ id: g.ids[0], lat: g.lat, lon: g.lon, count: g.ids.length }});
                    }}
                    return result;
                }}

                window.updateMarkers = function(markersJson) {{
                    var markers = JSON.parse(markersJson);
                    var grouped = groupMarkers(markers);
                    markerGroup.clearLayers();
                    grouped.forEach(function(m) {{
                        var popupText = m.count === 1 ? '📍 1 ổ gà' : '📍 ' + m.count + ' ổ gà';
                        var marker = L.marker([m.lat, m.lon])
                            .bindPopup(popupText)
                            .on('click', function() {{
                                if (window.potholeBridge) window.potholeBridge.select_pothole(m.id);
                            }});
                        markerGroup.addLayer(marker);
                    }});
                }};

                function getPolygonStyle() {{
                    var zoom = map.getZoom();
                    if (zoom >= 16) {{
                        return {{
                            color: 'transparent',
                            weight: 2,
                            fillOpacity: 0,
                            fillColor: '#3388ff'
                        }};
                    }} else {{
                        return {{
                            color: '#3388ff',
                            weight: 2,
                            fillOpacity: 0.3,
                            fillColor: '#3388ff'
                        }};
                    }}
                }}

                function updateGeometryLayer(geojsonStr) {{
                    if (geometryLayer) {{
                        map.removeLayer(geometryLayer);
                        geometryLayer = null;
                    }}
                    if (geojsonStr && geojsonStr !== 'null') {{
                        try {{
                            var data = JSON.parse(geojsonStr);
                            var style = getPolygonStyle();
                            geometryLayer = L.geoJSON(data, {{ style: style }}).addTo(map);
                        }} catch(e) {{
                            console.log('Geometry error:', e);
                        }}
                    }}
                }}

                window.updateGeometry = function(geojsonStr) {{
                    currentGeojson = geojsonStr;
                    updateGeometryLayer(geojsonStr);
                }};

                function updatePolygonStyleByZoom() {{
                    if (geometryLayer && currentGeojson && currentGeojson !== 'null') {{
                        var newStyle = getPolygonStyle();
                        geometryLayer.setStyle(newStyle);
                    }}
                }}

                function loadMarkers() {{
                    if (!window.mapBridge) return;
                    var bounds = map.getBounds();
                    var sw = bounds.getSouthWest();
                    var ne = bounds.getNorthEast();
                    var zoom = map.getZoom();
                    window.mapBridge.load_markers(sw.lat, sw.lng, ne.lat, ne.lng, zoom);
                }}

                function loadGeometry() {{
                    if (!window.mapBridge) return;
                    var bounds = map.getBounds();
                    var sw = bounds.getSouthWest();
                    var ne = bounds.getNorthEast();
                    var zoom = map.getZoom();
                    window.mapBridge.load_geometry(sw.lat, sw.lng, ne.lat, ne.lng, zoom);
                }}

                window.loadMarkers = loadMarkers;
                window.loadGeometry = loadGeometry;

                map.on('moveend', function() {{
                    loadMarkers();
                    loadGeometry();
                }});
                map.on('zoomend', function() {{
                    loadMarkers();
                    loadGeometry();
                    updatePolygonStyleByZoom();
                }});

                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.mapBridge = channel.objects.mapBridge;
                    window.potholeBridge = channel.objects.potholeBridge;
                    setTimeout(function() {{
                        map.invalidateSize();
                        {fit_js}
                        loadMarkers();
                        loadGeometry();
                    }}, 200);
                }});
            }}
            document.addEventListener('DOMContentLoaded', initMap);
            </script>
        </body>
        </html>
        """
        return html

    def on_markers_ready(self, markers_json):
        js = f"window.updateMarkers({json.dumps(markers_json)});"
        self.map_view.page().runJavaScript(js)

    def on_geometry_ready(self, geojson_str):
        if geojson_str == "null":
            js = "window.updateGeometry(null);"
        else:
            js = f"window.updateGeometry({json.dumps(geojson_str)});"
        self.map_view.page().runJavaScript(js)

    def display_pothole_by_id(self, pothole_id):
        row = self.db.get_pothole_by_id(pothole_id)
        if not row:
            return
        lat, lon = row[5], row[6]
        if lat == 0 or lon == 0:
            return
        records = self.db.get_group_by_gps(lat, lon)
        if not records:
            return
        self.current_group_records = records
        self.map_combo.clear()
        for rec in records:
            self.map_combo.addItem(f"ID {rec[0]}", rec[0])
        self.map_combo.setCurrentIndex(0)

    def on_combo_changed(self, index):
        if index < 0 or not self.current_group_records:
            return
        rec_id = self.map_combo.itemData(index)
        for rec in self.current_group_records:
            if rec[0] == rec_id:
                img_path = rec[7]
                if img_path and os.path.exists(img_path):
                    pixmap = QPixmap(img_path)
                    self.map_info_image.setPixmap(pixmap.scaled(
                        self.map_info_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    self.map_info_image.clear()
                    self.map_info_image.setText("Không tìm thấy ảnh")
                
                area, depth, volume, ts, lat, lon = rec[1], rec[2], rec[3], rec[4], rec[5], rec[6]
                
                location_text = ""
                if self.location_mgr and lat != 0 and lon != 0:
                    try:
                        province = self.location_mgr.get_location_name_by_point(lat, lon, 'province')
                        ward = self.location_mgr.get_location_name_by_point(lat, lon, 'ward')
                        if province:
                            if ward:
                                location_text = f"<br><b>Địa chỉ:</b> {ward}, {province}"
                            else:
                                location_text = f"<br><b>Địa chỉ:</b> {province}"
                    except Exception as e:
                        print(f"Lỗi địa chỉ MapTab: {e}")
                
                info = f"<b>ID:</b> {rec_id}<br><b>Diện tích:</b> {area:.1f} cm²<br><b>Độ sâu:</b> {depth:.1f} cm<br><b>Thể tích:</b> {volume:.1f} cm³<br><b>Thời gian phát hiện:</b> {ts}<br><b>GPS:</b> ({lat:.6f}, {lon:.6f}){location_text}"
                self.map_info_text.setHtml(info)
                break

    def on_image_click(self, event):
        idx = self.map_combo.currentIndex()
        if idx < 0:
            return
        rec_id = self.map_combo.itemData(idx)
        if rec_id is None:
            return
        for rec in self.current_group_records:
            if rec[0] == rec_id:
                lat, lon = rec[5], rec[6]
                if lat != 0 and lon != 0:
                    js = f"""
                    if (window.map && window.map.setView) {{
                        window.map.setView([{lat}, {lon}], 19);
                        if (window.tempMarker) window.tempMarker.remove();
                        window.tempMarker = L.marker([{lat}, {lon}]).addTo(window.map)
                            .bindPopup('Ổ gà ID {rec_id}')
                            .openPopup();
                        setTimeout(function(){{
                            if(window.tempMarker) window.tempMarker.remove();
                        }}, 8000);
                    }}
                    """
                    self.map_view.page().runJavaScript(js)
                break

    def fill_panel_by_db_id(self, db_id):
        row = self.db.get_pothole_by_id(db_id)
        if not row:
            return
        lat, lon = row[5], row[6]
        if lat == 0 or lon == 0:
            return
        records = self.db.get_group_by_gps(lat, lon)
        if not records:
            records = [row]
        self.current_group_records = records
        self.map_combo.blockSignals(True)
        self.map_combo.clear()
        target_index = 0
        for i, rec in enumerate(records):
            self.map_combo.addItem(f"ID {rec[0]}", rec[0])
            if rec[0] == db_id:
                target_index = i
        self.map_combo.blockSignals(False)
        self.map_combo.setCurrentIndex(target_index)
        self.on_combo_changed(target_index)

    def focus_on_pothole(self, lat, lon):
        if lat == 0 or lon == 0:
            return
        js = f"""
        if (window.map && window.map.setView) {{
            window.map.setView([{lat}, {lon}], 18);
            if (window.tempMarker) window.tempMarker.remove();
            window.tempMarker = L.marker([{lat}, {lon}]).addTo(window.map)
                .bindPopup('Ổ gà tại đây')
                .openPopup();
            setTimeout(function(){{ 
                if(window.tempMarker) window.tempMarker.remove(); 
            }}, 8000);
        }} else {{
            console.log('Map chưa sẵn sàng');
        }}
        """
        self.map_view.page().runJavaScript(js)
        if self.location_mgr:
            province_name = self.location_mgr.get_location_name_by_point(lat, lon, 'province')
            ward_name = self.location_mgr.get_location_name_by_point(lat, lon, 'ward')
            if province_name:
                self.cbo_province.blockSignals(True)
                self.cbo_province.setCurrentText(province_name)
                self.cbo_province.blockSignals(False)
                self.on_province_changed()
                if ward_name:
                    self.cbo_ward.blockSignals(True)
                    self.cbo_ward.setCurrentText(ward_name)
                    self.cbo_ward.blockSignals(False)

    def refresh_markers_only(self):
        self.map_view.page().runJavaScript("if(window.loadMarkers) window.loadMarkers();")

    def add_new_pothole(self, pothole_id, lat, lon):
        self.all_records.append((pothole_id, lat, lon))
        if self.current_highlight_geom is not None:
            point = Point(lon, lat)
            if self.current_highlight_geom.buffer(1e-5).intersects(point):
                self.filtered_records.append((pothole_id, lat, lon))
                if self.map_bridge.filtered_ids is not None:
                    self.map_bridge.filtered_ids.add(pothole_id)
        else:
            self.filtered_records.append((pothole_id, lat, lon))
        self.refresh_markers_only()