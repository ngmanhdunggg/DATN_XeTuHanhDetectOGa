import os
import json
from shapely.geometry import shape, Point

class LocationManager:
    def __init__(self, geojson_base):
        self.geojson_base = geojson_base
        self.province_geometries = {}
        self.ward_geometries = {}
        self.wards_by_province = {}
        self._load_all()

    def _load_geojson(self, filepath, target_dict, is_ward=False):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for feature in data['features']:
            props = feature['properties']
            name = None
            province_name = None
            if is_ward:
                name = props.get('ten_xa') or props.get('name')
                province_name = props.get('ten_tinh') or props.get('province_name')
            else:
                name = props.get('name') or props.get('ten_tinh')
            if name:
                geometry = shape(feature['geometry'])
                target_dict[name] = geometry
                if is_ward and province_name:
                    self.wards_by_province.setdefault(province_name, []).append(name)

    def _load_all(self):
        for root, _, files in os.walk(self.geojson_base):
            for f in files:
                if f.endswith("-tinh-thanh-34.geojson"):
                    self._load_geojson(os.path.join(root, f), self.province_geometries, is_ward=False)
                elif f.endswith("-phuong-xa-34.geojson"):
                    self._load_geojson(os.path.join(root, f), self.ward_geometries, is_ward=True)

    def get_province_names(self):
        return sorted(self.province_geometries.keys())

    def get_wards_by_province(self, province_name):
        return sorted(self.wards_by_province.get(province_name, []))

    def get_geometry(self, name, level='province'):
        if level == 'province':
            return self.province_geometries.get(name)
        else:
            return self.ward_geometries.get(name)

    def is_point_in_location(self, lat, lon, location_name, level='province'):
        geom = self.get_geometry(location_name, level)
        if not geom:
            return False
        return geom.contains(Point(lon, lat))

    def filter_records(self, records, location_name, level='province'):
        geom = self.get_geometry(location_name, level)
        if not geom:
            return []
        result = []
        for rec in records:
            lat = rec[-2]
            lon = rec[-1]
            if geom.contains(Point(lon, lat)):
                result.append(rec)
        return result
    
    def get_location_name_by_point(self, lat, lon, level='province'):
        """
        Tra cứu tên địa danh dựa trên tọa độ GPS.
        Sửa lỗi attribute bằng cách dùng đúng tên biến: province_geometries và ward_geometries
        """
        from shapely.geometry import Point
        point = Point(lon, lat)
        
        # Kiểm tra và dùng đúng tên biến mà class LocationManager đang sở hữu
        if level == 'province':
            target_dict = self.province_geometries
        else:
            target_dict = self.ward_geometries
            
        for name, geom in target_dict.items():
            if geom.contains(point):
                return name
        return None