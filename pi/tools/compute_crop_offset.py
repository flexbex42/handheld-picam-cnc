#!/usr/bin/env python3
"""
Compute optimal crop offset to center original image content after perspective warp
"""
import json
import os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
SETTINGS = os.path.join(ROOT, 'res', 'camera_settings.json')

with open(SETTINGS, 'r') as f:
    data = json.load(f)

selected = data.get('selected_camera')
cam = data.get(selected, {})
pers = cam.get('calibration', {}).get('perspective', {})
geom = cam.get('calibration', {}).get('geometric', {})

stored_tilt = pers.get('tilt_deg')
stored_yaw = pers.get('yaw_deg')
translate_x = pers.get('translate_x', 0)
translate_y = pers.get('translate_y', 0)

cam_mat = np.array(geom.get('camera_matrix'), dtype=np.float64)

res_str = cam.get('resolution')
if res_str and 'x' in res_str:
    w_img, h_img = map(int, res_str.split('x'))
else:
    screen = data.get('calibration_settings', {}).get('screen_size', {})
    w_img = int(screen.get('width', 640))
    h_img = int(screen.get('height', 480))

print(f"Image size: {w_img}x{h_img}")
print(f"Stored tilt={stored_tilt:.2f}°, yaw={stored_yaw:.2f}°")
print(f"Stored translate: ({translate_x}, {translate_y})")

# Build rotation matrix
def build_rotation(tilt_d, yaw_d):
    tr = np.deg2rad(tilt_d)
    yr = np.deg2rad(yaw_d)
    ct = np.cos(tr)
    st = np.sin(tr)
    cy = np.cos(yr)
    sy = np.sin(yr)
    col0 = np.array([ct * cy, ct * sy, -st], dtype=np.float64)
    cand_col1_a = np.array([-sy, cy, 0.0], dtype=np.float64)
    cand_col1_b = np.array([sy, -cy, 0.0], dtype=np.float64)

    def build_R(col1):
        col1n = col1 / (np.linalg.norm(col1) + 1e-12)
        col2 = np.cross(col0, col1n)
        R = np.column_stack((col0, col1n, col2))
        U, _, Vt = np.linalg.svd(R)
        return U @ Vt

    R_a = build_R(cand_col1_a)
    R_b = build_R(cand_col1_b)
    z_a = np.arctan2(R_a[1, 0], R_a[0, 0])
    z_b = np.arctan2(R_b[1, 0], R_b[0, 0])
    return R_a if abs(z_a) <= abs(z_b) else R_b

R_recon = build_rotation(stored_tilt, stored_yaw)

fx = cam_mat[0, 0]
fy = cam_mat[1, 1]
cx = cam_mat[0, 2]
cy = cam_mat[1, 2]

# Project original image corners through inverse rotation
src_corners = np.array([[0.0, 0.0], [w_img - 1.0, 0.0], [w_img - 1.0, h_img - 1.0], [0.0, h_img - 1.0]], dtype=np.float64)
dst_corners = []
R_inv = R_recon.T

print("\nOriginal corners → Projected corners:")
for i, (u, v) in enumerate(src_corners):
    x = (u - cx) / fx
    y = (v - cy) / fy
    vec = np.array([x, y, 1.0], dtype=np.float64)
    vec_rot = R_inv @ vec
    if abs(vec_rot[2]) < 1e-9:
        u2 = cx
        v2 = cy
    else:
        u2 = fx * (vec_rot[0] / vec_rot[2]) + cx
        v2 = fy * (vec_rot[1] / vec_rot[2]) + cy
    dst_corners.append([u2, v2])
    print(f"  ({u:.0f}, {v:.0f}) → ({u2:.2f}, {v2:.2f})")

dst_corners = np.array(dst_corners, dtype=np.float64)

# After applying translation T, the projected corners will be at:
print(f"\nAfter translation by ({translate_x}, {translate_y}):")
dst_corners_translated = dst_corners + np.array([translate_x, translate_y])
for i, (orig_corner, trans_corner) in enumerate(zip(dst_corners, dst_corners_translated)):
    print(f"  Corner {i}: ({orig_corner[0]:.2f}, {orig_corner[1]:.2f}) → ({trans_corner[0]:.2f}, {trans_corner[1]:.2f})")

# The optimal crop should start where the original (0,0) ended up after translation
crop_start_x = int(np.round(dst_corners_translated[0][0]))
crop_start_y = int(np.round(dst_corners_translated[0][1]))

print(f"\n✓ Optimal crop offset: ({crop_start_x}, {crop_start_y})")
print(f"  This centers the original image content in the 640x480 crop window")

# Compare to current hardcoded value
current_hardcoded = 200
print(f"\n⚠ Currently hardcoded extra_shift_x = {current_hardcoded}")
print(f"  Actual needed: {crop_start_x - translate_x}")
print(f"  Difference: {(crop_start_x - translate_x) - current_hardcoded} pixels")
