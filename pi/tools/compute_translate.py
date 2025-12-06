#!/usr/bin/env python3
import json, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
SETTINGS = os.path.join(ROOT, 'res', 'camera_settings.json')

with open(SETTINGS,'r') as f:
    data = json.load(f)

selected = data.get('selected_camera')
if not selected:
    print('No selected_camera in settings')
    raise SystemExit(1)

cam = data.get(selected, {})
pers = cam.get('calibration', {}).get('perspective', {})
geom = cam.get('calibration', {}).get('geometric', {})

if not pers:
    print('No perspective block for selected camera')
    raise SystemExit(1)

tilt_deg = pers.get('tilt_deg')
yaw_deg = pers.get('yaw_deg')
print('Using tilt_deg, yaw_deg from file:', tilt_deg, yaw_deg)

res_str = cam.get('resolution')
if res_str and 'x' in res_str:
    w,h = map(int,res_str.split('x'))
else:
    screen = data.get('calibration_settings',{}).get('screen_size',{})
    w = int(screen.get('width',640))
    h = int(screen.get('height',480))

cam_mat = None
if geom and geom.get('camera_matrix'):
    cam_mat = np.array(geom.get('camera_matrix'),dtype=np.float64)

translate_x=0
translate_y=0
pad=20

if cam_mat is not None and tilt_deg is not None and yaw_deg is not None:
    def build_rotation(tilt_d, yaw_d):
        tr = np.deg2rad(tilt_d)
        yr = np.deg2rad(yaw_d)
        ct = np.cos(tr); st = np.sin(tr)
        cy = np.cos(yr); sy = np.sin(yr)
        col0 = np.array([ct*cy, ct*sy, -st], dtype=np.float64)
        cand_col1_a = np.array([-sy, cy, 0.0], dtype=np.float64)
        cand_col1_b = np.array([sy, -cy, 0.0], dtype=np.float64)
        def build_R(col1):
            col1n = col1 / (np.linalg.norm(col1)+1e-12)
            col2 = np.cross(col0, col1n)
            R = np.column_stack((col0, col1n, col2))
            U,_,Vt = np.linalg.svd(R)
            return U@Vt
        R_a = build_R(cand_col1_a)
        R_b = build_R(cand_col1_b)
        z_a = np.arctan2(R_a[1,0], R_a[0,0])
        z_b = np.arctan2(R_b[1,0], R_b[0,0])
        return R_a if abs(z_a)<=abs(z_b) else R_b

    R_recon = build_rotation(tilt_deg, yaw_deg)
    fx = cam_mat[0,0]; fy = cam_mat[1,1]; cx = cam_mat[0,2]; cy = cam_mat[1,2]
    src_corners = np.array([[0.0,0.0],[w-1.0,0.0],[w-1.0,h-1.0],[0.0,h-1.0]], dtype=np.float64)
    dst=[]
    R_inv = R_recon.T
    for (u,v) in src_corners:
        x=(u-cx)/fx; y=(v-cy)/fy
        vec=np.array([x,y,1.0],dtype=np.float64)
        vec_rot = R_inv @ vec
        if abs(vec_rot[2])<1e-9:
            u2=cx; v2=cy
        else:
            u2 = fx*(vec_rot[0]/vec_rot[2])+cx
            v2 = fy*(vec_rot[1]/vec_rot[2])+cy
        dst.append([u2,v2])
    dst=np.array(dst)
    min_xy = dst.min(axis=0)
    min_x, min_y = min_xy[0], min_xy[1]
    off_x = int(max(0, -np.floor(min_x))+pad)
    off_y = int(max(0, -np.floor(min_y))+pad)
    translate_x=off_x; translate_y=off_y

print('Computed translate_x, translate_y:', translate_x, translate_y)

# write back
if 'calibration' not in cam:
    cam['calibration'] = {}
if 'perspective' not in cam['calibration']:
    cam['calibration']['perspective'] = {}
cam['calibration']['perspective']['translate_x'] = int(translate_x)
cam['calibration']['perspective']['translate_y'] = int(translate_y)

with open(SETTINGS,'w') as f:
    json.dump(data, f, indent=4)
print('Updated', SETTINGS)
