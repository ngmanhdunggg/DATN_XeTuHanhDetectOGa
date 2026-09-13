# utils.py
import cv2
import numpy as np
from config import (
    FRAME_SIZE, BEV_W, BEV_TOP_H, COLOR_DRIVABLE, COLOR_LANE,
    COLOR_CENTER_PATH, COLOR_CENTER_POINT, COLOR_DA_POLY,
    MAX_CENTER_SHIFT
)

def get_bird_eye_matrix():
    src = np.float32([[114, 27], [526, 27], [640, 417], [0, 417]])
    dst = np.float32([[120, 0], [520, 0], [520, 400], [120, 400]])
    M = cv2.getPerspectiveTransform(src, dst)
    M_inv = cv2.getPerspectiveTransform(dst, src)
    return M, M_inv

def get_bev_matrix():
    src = np.float32([[114, 27], [526, 27], [640, 417], [0, 417]])
    dst = np.float32([[0, 0], [BEV_W, 0], [BEV_W, BEV_TOP_H], [0, BEV_TOP_H]])
    return cv2.getPerspectiveTransform(src, dst)

def filter_noise(mask, min_area):
    clean_mask = np.zeros_like(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        if cv2.contourArea(cnt) > min_area:
            cv2.drawContours(clean_mask, [cnt], -1, 255, -1)
    return clean_mask

def draw_drivable_and_lane(frame, da_mask_warped, ll_mask, M_inv):
    overlay = frame.copy()
    h_warp, w_warp = da_mask_warped.shape
    left_pts = []
    right_pts = []
    for y in range(0, h_warp, 5):
        row = da_mask_warped[y, :]
        indices = np.where(row == 255)[0]
        if len(indices) > 0:
            left_pts.append([indices[0], y])
            right_pts.append([indices[-1], y])
    if len(left_pts) > 0 and len(right_pts) > 0:
        left_pts = np.array(left_pts, dtype=np.float32).reshape(-1,1,2)
        right_pts = np.array(right_pts, dtype=np.float32).reshape(-1,1,2)
        left_warped = cv2.perspectiveTransform(left_pts, M_inv).reshape(-1,2).astype(np.int32)
        right_warped = cv2.perspectiveTransform(right_pts, M_inv).reshape(-1,2).astype(np.int32)
        polygon = np.vstack((left_warped, right_warped[::-1]))
        cv2.fillPoly(overlay, [polygon], COLOR_DA_POLY)
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
    if ll_mask.shape != frame.shape[:2]:
        ll_mask = cv2.resize(ll_mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
    frame[ll_mask == 255] = COLOR_LANE
    return frame

def compute_center_per_row(y, warped_ll, warped_da, mid_w):
    ll_row = warped_ll[y, :]
    da_row = warped_da[y, :]
    ll_indices = np.where(ll_row == 255)[0]
    da_indices = np.where(da_row == 255)[0]
    if len(da_indices) == 0:
        return None, False
    x_da_left = da_indices[0]
    x_da_right = da_indices[-1]
    center_da = (x_da_left + x_da_right) / 2.0
    ll_left_side = ll_indices[ll_indices < center_da]
    ll_right_side = ll_indices[ll_indices > center_da]
    has_left_ll = len(ll_left_side) > 0
    has_right_ll = len(ll_right_side) > 0
    if has_left_ll and has_right_ll:
        x_tim = (np.mean(ll_left_side) + np.mean(ll_right_side)) / 2.0
    elif has_left_ll:
        x_tim = (np.mean(ll_left_side) + x_da_right) / 2.0
    elif has_right_ll:
        x_tim = (x_da_left + np.mean(ll_right_side)) / 2.0
    else:
        x_tim = center_da
    return x_tim, True

def filter_outlier_centers(center_points, max_shift):
    if len(center_points) < 2:
        return center_points
    x_vals = np.array([p[0] for p in center_points], dtype=np.float32)
    y_vals = np.array([p[1] for p in center_points], dtype=np.float32)
    valid_mask = np.ones(len(x_vals), dtype=bool)
    for i in range(1, len(x_vals)):
        if abs(x_vals[i] - x_vals[i-1]) > max_shift:
            valid_mask[i] = False
    if not np.all(valid_mask):
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) >= 2:
            x_interp = np.interp(np.arange(len(x_vals)), valid_indices, x_vals[valid_indices])
            return [(int(x_interp[i]), int(y_vals[i])) for i in range(len(x_vals))]
        elif len(valid_indices) == 1:
            return [center_points[valid_indices[0]]]
        else:
            return []
    return center_points

def draw_center_path_on_frame(frame, center_points_warped, M_inv):
    if len(center_points_warped) < 2:
        return frame
    pts_src = np.array(center_points_warped, dtype=np.float32).reshape(-1,1,2)
    pts_dst = cv2.perspectiveTransform(pts_src, M_inv).reshape(-1,2).astype(np.int32)
    cv2.polylines(frame, [pts_dst], False, COLOR_CENTER_PATH, 3)
    for pt in pts_dst:
        cv2.circle(frame, tuple(pt), 5, COLOR_CENTER_POINT, -1)
    return frame