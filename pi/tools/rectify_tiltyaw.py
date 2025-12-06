#!/usr/bin/env python3
import json
import os
import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
SETTINGS = os.path.join(ROOT, 'res', 'camera_settings.json')
SAMPLE = os.path.join(ROOT, 'sample', 'testimage.png')
OUT = os.path.join(ROOT, 'sample', 'testimage_rectified_tiltyaw.png')

if not os.path.exists(SETTINGS):
    print('camera_settings.json not found at', SETTINGS)
    raise SystemExit(1)

with open(SETTINGS, 'r') as f:
    data = json.load(f)

selected = data.get('selected_camera')
if selected is None:
    print('No selected_camera in settings')
    raise SystemExit(1)

cam = data.get(selected)
if cam is None:
    print('Selected camera', selected, 'not found')
    raise SystemExit(1)

pers = cam.get('calibration', {}).get('perspective', {})
geom = cam.get('calibration', {}).get('geometric', {})

tilt_deg = pers.get('tilt_deg')
yaw_deg = pers.get('yaw_deg')

if tilt_deg is None or yaw_deg is None:
    print('No tilt/yaw in perspective settings for', selected)
    raise SystemExit(1)

if 'camera_matrix' not in geom:
    print('No camera_matrix in geometric calibration for', selected)
    raise SystemExit(1)

camera_matrix = np.array(geom['camera_matrix'], dtype=np.float64)

print('Selected camera:', selected)
print('tilt_deg:', tilt_deg, 'yaw_deg:', yaw_deg)
print('camera_matrix fx,fy,cx,cy:', camera_matrix[0,0], camera_matrix[1,1], camera_matrix[0,2], camera_matrix[1,2])

if not os.path.exists(SAMPLE):
    print('Sample image not found at', SAMPLE)
    raise SystemExit(1)

img = cv2.imread(SAMPLE)
if img is None:
    print('Failed to load image')
    raise SystemExit(1)

# reconstruct rotation using method used in caliOffset
tilt_rad = np.deg2rad(tilt_deg)
yaw_rad = np.deg2rad(yaw_deg)
ct = np.cos(tilt_rad)
st = np.sin(tilt_rad)
cy = np.cos(yaw_rad)
sy = np.sin(yaw_rad)
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

z_a = np.arctan2(R_a[1,0], R_a[0,0])
z_b = np.arctan2(R_b[1,0], R_b[0,0])

print('z_a (rad):', z_a, 'z_b (rad):', z_b)

R_recon = R_a if abs(z_a) <= abs(z_b) else R_b
chosen = 'a' if abs(z_a) <= abs(z_b) else 'b'
print('Chosen candidate:', chosen)

h, w = img.shape[:2]
fx = camera_matrix[0,0]
fy = camera_matrix[1,1]
cx = camera_matrix[0,2]
cy = camera_matrix[1,2]

src_corners = np.array([[0.0,0.0],[w-1.0,0.0],[w-1.0,h-1.0],[0.0,h-1.0]], dtype=np.float32)
dst_corners = []
R_inv = R_recon.T
for (u,v) in src_corners:
    x = (u - cx) / fx
    y = (v - cy) / fy
    vec = np.array([x,y,1.0], dtype=np.float64)
    vec_rot = R_inv @ vec
    if abs(vec_rot[2]) < 1e-9:
        u2 = cx
        v2 = cy
    else:
        u2 = fx * (vec_rot[0] / vec_rot[2]) + cx
        v2 = fy * (vec_rot[1] / vec_rot[2]) + cy
    dst_corners.append([u2, v2])

dst_corners = np.array(dst_corners, dtype=np.float32)
print('src_corners:', src_corners)
print('dst_corners:', dst_corners)

H = cv2.getPerspectiveTransform(src_corners, dst_corners)
res = cv2.warpPerspective(img, H, (w,h), flags=cv2.INTER_LINEAR)
cv2.imwrite(OUT, res)
print('Wrote rectified image to', OUT)
