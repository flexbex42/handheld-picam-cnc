#!/usr/bin/env python3
import os,json,cv2,numpy as np
ROOT = os.path.dirname(os.path.dirname(__file__))
SAMPLE_DIR = os.path.join(ROOT,'sample')
SETTINGS = os.path.join(ROOT,'res','camera_settings.json')
with open(SETTINGS,'r') as f:
    settings = json.load(f)
calib = settings.get('calibration_settings',{})
boxes = calib.get('checkerboard_boxes',{'x':11,'y':8})
pattern = (boxes.get('x')-1, boxes.get('y')-1)
square_size = calib.get('checkerboard_dim',{}).get('size_mm',5)

print('pattern',pattern,'square_size',square_size)

objpoints=[]
imgpoints=[]
successful=0

# prepare object points for pattern (z=0)
objp_base = np.zeros((pattern[0]*pattern[1],3),np.float32)
objp_base[:,:2] = np.mgrid[0:pattern[0],0:pattern[1]].T.reshape(-1,2)
objp_base *= square_size

for i in range(1,16):
    fn = f'sample_{i:02d}.jpg'
    p = os.path.join(SAMPLE_DIR,fn)
    print('\n--',fn,'--')
    if not os.path.exists(p):
        print('missing')
        continue
    img = cv2.imread(p)
    if img is None:
        print('read fail')
        continue
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    gray = np.ascontiguousarray(gray,dtype=np.uint8)
    ret,corners = cv2.findChessboardCorners(gray,pattern,flags=cv2.CALIB_CB_ADAPTIVE_THRESH+cv2.CALIB_CB_NORMALIZE_IMAGE)
    print('findChessboardCorners',ret,type(corners))
    if ret:
        try:
            criteria = (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,30,0.001)
            corners2 = cv2.cornerSubPix(gray,corners,(11,11),(-1,-1),criteria)
            print('cornerSubPix ok',corners2.shape)
            objpoints.append(objp_base.copy())
            imgpoints.append(corners2)
            successful += 1
        except Exception as e:
            print('cornerSubPix failed',e)

print('\ncollected',successful,'images')
if successful < 3:
    print('not enough images, abort')
    raise SystemExit(1)

# try solvePnP using first set
# use geometric from selected camera if available
selected = settings.get('selected_camera')
cam = settings.get(selected, {})
geom = cam.get('intrinsic',{}).get('geometric',{})
if not geom or 'camera_matrix' not in geom:
    print('no camera matrix available, abort')
    raise SystemExit(1)
cam_mat = np.array(geom['camera_matrix'],dtype=np.float64)

rvecs=[]
tvecs=[]
for objp,imgp in zip(objpoints,imgpoints):
    try:
        ok, rvec, tvec = cv2.solvePnP(objp, imgp, cam_mat, None)
        print('solvePnP returned', ok)
        if ok:
            rvecs.append(rvec)
            tvecs.append(tvec)
    except Exception as e:
        print('solvePnP exception',e)

if len(rvecs)==0:
    print('solvePnP failed for all')
    raise SystemExit(1)

rvec_mean = np.mean(rvecs, axis=0)
tvec_mean = np.mean(tvecs, axis=0)
print('rvec_mean',rvec_mean.flatten())
print('tvec_mean',tvec_mean.flatten())

rmat,_ = cv2.Rodrigues(rvec_mean)
print('rmat shape', rmat.shape)

tilt_rad = np.arcsin(-rmat[2,0])
yaw_rad = np.arctan2(rmat[1,0], rmat[0,0])
print('tilt_deg', np.degrees(tilt_rad), 'yaw_deg', np.degrees(yaw_rad))
print('\nDone')
