import time

class PotholeTrack:
    def __init__(self, track_id, detection, pixel_to_cm2, expand=30):
        self.id = track_id
        self.box = detection['box']
        self.area_px = detection['area_px']
        self.area_cm2 = self.area_px * pixel_to_cm2
        self.max_area_cm2 = self.area_cm2
        self.confidence = detection['confidence']
        self.last_seen = time.time()
        self.saved = False
        self.captured_image = None
        self.has_captured = False
        self.max_depth_cm = 0.0
        self.has_entered_roi2 = False

    def update(self, detection, pixel_to_cm2):
        self.box = detection['box']
        self.area_px = detection['area_px']
        self.area_cm2 = self.area_px * pixel_to_cm2
        self.confidence = detection['confidence']
        self.last_seen = time.time()

    def capture_image_from_roi1(self, bev_img, expand=30):
        if self.has_captured:
            return
        x1, y1, x2, y2 = self.box
        x1e = max(0, x1 - expand)
        y1e = max(0, y1 - expand)
        x2e = min(bev_img.shape[1], x2 + expand)
        y2e = min(bev_img.shape[0], y2 + expand)
        crop = bev_img[y1e:y2e, x1e:x2e]
        if crop.size > 0:
            self.captured_image = crop.copy()
            self.has_captured = True

    def update_max_area(self):
        if self.area_cm2 > self.max_area_cm2:
            self.max_area_cm2 = self.area_cm2

    def update_max_depth(self, depth_cm):
        if depth_cm > self.max_depth_cm:
            self.max_depth_cm = depth_cm

class PotholeTracker:
    def __init__(self, pixel_to_cm2, iou_threshold=0.3, lost_timeout=1.0):
        self.next_id = 1
        self.tracks = []
        self.iou_threshold = iou_threshold
        self.lost_timeout = lost_timeout
        self.pixel_to_cm2 = pixel_to_cm2

    def compute_iou(self, box1, box2):
        x1, y1, x2, y2 = box1
        x1b, y1b, x2b, y2b = box2
        inter_x1 = max(x1, x1b)
        inter_y1 = max(y1, y1b)
        inter_x2 = min(x2, x2b)
        inter_y2 = min(y2, y2b)
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (x2b - x1b) * (y2b - y1b)
        return inter_area / (area1 + area2 - inter_area + 1e-5)

    def update(self, detections, bev_img):
        now = time.time()
        self.tracks = [t for t in self.tracks if now - t.last_seen < self.lost_timeout]

        if not detections:
            return

        unmatched_detections = list(range(len(detections)))
        unmatched_tracks = list(range(len(self.tracks)))

        for i, track in enumerate(self.tracks):
            best_iou = 0
            best_det = -1
            for j, det in enumerate(detections):
                if j in unmatched_detections:
                    iou = self.compute_iou(track.box, det['box'])
                    if iou > best_iou and iou > self.iou_threshold:
                        best_iou = iou
                        best_det = j
            if best_det != -1:
                unmatched_detections.remove(best_det)
                unmatched_tracks.remove(i)
                track.update(detections[best_det], self.pixel_to_cm2)

        for j in unmatched_detections:
            new_track = PotholeTrack(self.next_id, detections[j], self.pixel_to_cm2)
            self.tracks.append(new_track)
            self.next_id += 1

    def get_active_tracks(self):
        now = time.time()
        return [t for t in self.tracks if now - t.last_seen < 0.5]