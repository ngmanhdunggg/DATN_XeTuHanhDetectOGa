import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path="database/potholes.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()

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

    def load_all_records(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, track_id, timestamp, area_cm2, depth_cm, volume_cm3, gps_lat, gps_lon, image_path
            FROM pothole_records ORDER BY id DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_pothole_by_id(self, pothole_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Ép kiểu an toàn
        try:
            pothole_id = int(pothole_id)
        except:
            return None
        cursor.execute('''
            SELECT id, area_cm2, depth_cm, volume_cm3, timestamp, gps_lat, gps_lon, image_path
            FROM pothole_records WHERE id = ?
        ''', (pothole_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    def get_group_by_gps(self, lat, lon, tolerance=0.000001):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, area_cm2, depth_cm, volume_cm3, timestamp, gps_lat, gps_lon, image_path
            FROM pothole_records
            WHERE ABS(gps_lat - ?) < ? AND ABS(gps_lon - ?) < ?
            ORDER BY id
        ''', (lat, tolerance, lon, tolerance))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_all_map_records(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, gps_lat, gps_lon
            FROM pothole_records WHERE gps_lat != 0 AND gps_lon != 0 ORDER BY id DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_records_in_bbox(self, lat_min, lat_max, lon_min, lon_max, limit=None):
        """
        Trả về danh sách các tuple (id, gps_lat, gps_lon) của ổ gà nằm trong bounding box.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT id, gps_lat, gps_lon FROM pothole_records 
            WHERE gps_lat BETWEEN ? AND ? 
            AND gps_lon BETWEEN ? AND ?
            AND gps_lat != 0 AND gps_lon != 0
        """
        params = [lat_min, lat_max, lon_min, lon_max]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows