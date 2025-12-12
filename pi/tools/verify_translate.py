#!/usr/bin/env python3
"""
Verify translate_x/translate_y calculation using stored perspective values
"""
import json
import os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
SETTINGS = os.path.join(ROOT, 'res', 'camera_settings.json')

with open(SETTINGS, 'r') as f:
    data = json.load(f)

selected = data.get('selected_camera')
print(f"Selected camera: {selected}")

cam = data.get(selected, {})
pers = cam.get('intrinsic', {}).get('perspective', {})
geom = cam.get('intrinsic', {}).get('geometric', {})

# Read stored values (already in the convention used by caliOffset)
stored_pitch = pers.get('pitch_deg')
stored_roll = pers.get('roll_deg')
print(f"\nStored in settings file:")
print(f"  pitch_deg: {stored_pitch}")
print(f"  roll_deg: {stored_roll}")
print(f"  translate_x: {pers.get('translate_x')}")
print(f"  translate_y: {pers.get('translate_y')}")

# Get camera matrix
cam_mat = None
if geom and geom.get('camera_matrix'):
    cam_mat = np.array(geom.get('camera_matrix'), dtype=np.float64)
    print(f"\nCamera matrix:")
    print(f"  fx={cam_mat[0,0]:.2f}, fy={cam_mat[1,1]:.2f}")
    print(f"  cx={cam_mat[0,2]:.2f}, cy={cam_mat[1,2]:.2f}")
else:
    print("\nERROR: No camera_matrix found!")
    exit(1)

# Get image dimensions
res_str = cam.get('resolution')
if res_str and 'x' in res_str:
    w_img, h_img = map(int, res_str.split('x'))
else:
    screen = data.get('calibration_settings', {}).get('screen_size', {})
    w_img = int(screen.get('width', 640))
    h_img = int(screen.get('height', 480))

print(f"  Image size: {w_img}x{h_img}")

# Build rotation matrix from stored pitch/roll (same as caliPerspective)
def build_rotation(pitch_d, roll_d):
    tr = np.deg2rad(pitch_d)
    yr = np.deg2rad(roll_d)
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
    chosen = R_a if abs(z_a) <= abs(z_b) else R_b
    return chosen

R_recon = build_rotation(stored_pitch, stored_roll)

fx = cam_mat[0, 0]
fy = cam_mat[1, 1]
cx = cam_mat[0, 2]
cy = cam_mat[1, 2]

# Project image corners through inverse rotation
src_corners = np.array([[0.0, 0.0], [w_img - 1.0, 0.0], [w_img - 1.0, h_img - 1.0], [0.0, h_img - 1.0]], dtype=np.float64)
dst = []
R_inv = R_recon.T

print(f"\nProjected corners:")
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
    dst.append([u2, v2])
    print(f"  Corner {i}: ({u:.1f}, {v:.1f}) → ({u2:.2f}, {v2:.2f})")

dst = np.array(dst, dtype=np.float64)
min_xy = dst.min(axis=0)
max_xy = dst.max(axis=0)
min_x, min_y = min_xy[0], min_xy[1]
max_x, max_y = max_xy[0], max_xy[1]

pad = 20
translate_x = int(max(0, -np.floor(min_x)) + pad)
translate_y = int(max(0, -np.floor(min_y)) + pad)

print(f"\nComputed translate values:")
print(f"  min_x={min_x:.2f}, min_y={min_y:.2f}")
print(f"  max_x={max_x:.2f}, max_y={max_y:.2f}")
print(f"  Required translate_x: {translate_x}")
print(f"  Required translate_y: {translate_y}")

print(f"\nConclusion:")
if translate_x == 0 and translate_y == 0:
    print("  ✓ No translation needed - projected corners are within image bounds")
else:
    print(f"  ⚠ Translation needed: translate_x={translate_x}, translate_y={translate_y}")
    print(f"    Current stored values: translate_x={pers.get('translate_x')}, translate_y={pers.get('translate_y')}")
    if translate_x != pers.get('translate_x') or translate_y != pers.get('translate_y'):
        print("  ⚠ MISMATCH: Stored values differ from computed values!")
        print("    → Re-run perspective calibration to update stored values")
