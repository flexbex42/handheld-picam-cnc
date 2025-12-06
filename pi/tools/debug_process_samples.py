#!/usr/bin/env python3
import os, json, cv2, numpy as np
ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE_DIR = os.path.join(ROOT, 'sample')
SETTINGS = os.path.join(ROOT, 'res', 'camera_settings.json')

print('Using sample dir:', SAMPLE_DIR)
with open(SETTINGS,'r') as f:
    settings = json.load(f)
calib = settings.get('calibration_settings', {})
boxes = calib.get('checkerboard_boxes', {'x':11,'y':8})
pattern = (boxes.get('x')-1, boxes.get('y')-1)
print('Pattern to try:', pattern)

# find a camera entry with geometric if any
cam_entry = None
for k,v in settings.items():
    if isinstance(v, dict) and 'calibration' in v and 'geometric' in v['calibration']:
        cam_entry = v
        break

camera_matrix = None
dist_coeffs = None
if cam_entry:
    geom = cam_entry['calibration']['geometric']
    if 'camera_matrix' in geom and 'dist_coeffs' in geom:
        camera_matrix = np.array(geom['camera_matrix'],dtype=np.float64)
        dist_coeffs = np.array(geom['dist_coeffs'],dtype=np.float64).reshape(-1)
        print('Found geometric calibration in', k)

for i in range(1, 16):
    fname = f'sample_{i:02d}.jpg'
    path = os.path.join(SAMPLE_DIR, fname)
    print('\n----', fname, '----')
    if not os.path.exists(path):
        print('missing')
        continue
    img = cv2.imread(path)
    if img is None:
        print('cv2.imread returned None')
        continue
    print('loaded shape', img.shape, 'dtype', img.dtype)
    if camera_matrix is not None and dist_coeffs is not None:
        try:
            und = cv2.undistort(img, camera_matrix, dist_coeffs)
            print('undistorted shape', und.shape)
        except Exception as e:
            print('undistort failed', e)
            und = img
    else:
        und = img
    try:
        gray = cv2.cvtColor(und, cv2.COLOR_BGR2GRAY)
        gray = np.ascontiguousarray(gray, dtype=np.uint8)
        print('gray shape', gray.shape, 'dtype', gray.dtype)
    except Exception as e:
        print('cvtColor failed', e)
        continue
    try:
        ret, corners = cv2.findChessboardCorners(gray, pattern, flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
        print('findChessboardCorners returned', ret, 'corners type', type(corners))
    except Exception as e:
        print('findChessboardCorners crashed or raised', e)
        continue
    if ret and corners is not None:
        try:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
            print('cornerSubPix ok, corners2 shape', corners2.shape)
        except Exception as e:
            print('cornerSubPix raised', e)
    else:
        print('no corners found')
print('\nDone')
