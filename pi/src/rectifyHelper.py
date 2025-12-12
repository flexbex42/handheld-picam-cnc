

import appSettings
import cv2
import numpy as np
import os
"""
rectificationHelper.py
Centralized image rectification helpers for calibration windows.
- Checkerboard detection
- Undistortion
- Perspective/homography correction
- Offset/translation
- Scale calculation
- High-level rectify pipeline

All functions are pure and reusable, with no UI dependencies.
"""





 # Used in caliDistortion.py, caliOffset.py, caliPerspective.py (sample dir setup)
def get_sample_dir():
    """Return the absolute path to the sample directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample"))

 # Used in caliDistortion.py, caliOffset.py, caliPerspective.py (ensure sample dir)
def ensure_sample_dir(sample_dir):
    """Ensure the sample directory exists."""
    os.makedirs(sample_dir, exist_ok=True)

 # Used in caliDistortion.py (camera calibration)
def calibrate_camera_from_samples(sample_dir, max_samples, checkerboard_sizes, detected_checkerboard_size, square_size):
    """Calibrate camera using checkerboard images in sample_dir. Returns (success, camera_matrix, dist_coeffs, error, detected_size, successful_count)."""
    objpoints = []
    imgpoints = []
    image_size = None
    successful_images = 0
    for i in range(1, max_samples + 1):
        filename = f"sample_{i:02d}.jpg"
        filepath = os.path.join(sample_dir, filename)
        if not os.path.exists(filepath):
            continue
        img = cv2.imread(filepath)
        if img is None:
            continue
        found, found_size, found_corners = find_checkerboard_corners(img, checkerboard_sizes, detected_checkerboard_size)
        if found:
            objp = np.zeros((found_size[0] * found_size[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:found_size[0], 0:found_size[1]].T.reshape(-1, 2)
            objp *= square_size
            objpoints.append(objp)
            imgpoints.append(found_corners)
            successful_images += 1
            if image_size is None:
                image_size = img.shape[1], img.shape[0]
            if detected_checkerboard_size is None:
                detected_checkerboard_size = found_size
    if successful_images < 3:
        return False, None, None, None, None, successful_images
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)
    mean_error = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
        mean_error += error
    mean_error /= len(objpoints)
    return True, camera_matrix, dist_coeffs, mean_error, detected_checkerboard_size, successful_images

 # Used in caliOffset.py, caliPerspective.py, rectify_image, compute_perspective_from_samples (undistortion)
def undistort_image(img, camera_matrix, dist_coeffs):
    """Apply camera undistortion to an image."""
    camera_matrix = np.array(camera_matrix, dtype=np.float64)
    dist_coeffs = np.array(dist_coeffs, dtype=np.float64)
    if camera_matrix.shape != (3, 3):
        print(f"[ERROR] camera_matrix shape invalid: {camera_matrix.shape}, expected (3, 3)")
        return img
    if dist_coeffs.ndim != 1 and dist_coeffs.shape[0] != 1:
        print(f"[ERROR] dist_coeffs shape invalid: {dist_coeffs.shape}, expected 1D array")
        return img
    return cv2.undistort(img, camera_matrix, dist_coeffs)

 # Used in caliPerspective.py (pitch/roll/scale from checkerboard)
def compute_perspective_from_samples(samples, max_samples, checkerboard_sizes, detected_checkerboard_size, square_size, camera_matrix, dist_coeffs):
    """Compute pitch, roll, and scale from checkerboard images. Accepts a list/tuple of images (in-memory). Returns (success, pitch_deg, roll_deg, scale_mm_per_pixel, successful_count)."""
    objpoints = []
    imgpoints = []
    successful_images = 0
    if detected_checkerboard_size:
        pattern_size = detected_checkerboard_size
    else:
        pattern_size = checkerboard_sizes[0]
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size

    images = samples[:max_samples]
    for img in images:
        if img is None:
            continue
        img_undistorted = undistort_image(img, camera_matrix, dist_coeffs)
        found, found_size, found_corners = find_checkerboard_corners(img_undistorted, checkerboard_sizes, detected_checkerboard_size)
        if found:
            if found_size != pattern_size:
                pattern_size = found_size
                objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
                objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
                objp *= square_size
            objpoints.append(objp)
            imgpoints.append(found_corners)
            successful_images += 1
    if successful_images < 3:
        return False, 0, 0, 0, successful_images
    rvecs_list = []
    tvecs_list = []
    for obj_pts, img_pts in zip(objpoints, imgpoints):
        obj_pts_np = np.ascontiguousarray(np.array(obj_pts, dtype=np.float32))
        img_pts_np = np.ascontiguousarray(np.array(img_pts, dtype=np.float32))
        success, rvec, tvec = cv2.solvePnP(obj_pts_np, img_pts_np, camera_matrix, None)
        if success:
            rvecs_list.append(rvec)
            tvecs_list.append(tvec)
    if len(rvecs_list) == 0:
        return False, 0, 0, 0, successful_images
    rvec_mean = np.mean(rvecs_list, axis=0)
    tvec_mean = np.mean(tvecs_list, axis=0)
    rmat, _ = cv2.Rodrigues(rvec_mean)
    pitch_rad = np.arcsin(-rmat[2, 0])
    roll_rad = np.arctan2(rmat[1, 0], rmat[0, 0])
    pitch_deg = np.degrees(pitch_rad)
    roll_deg = np.degrees(roll_rad)
    img_pts = imgpoints[0]
    distances_px = []
    for idx in range(len(img_pts) - 1):
        if idx % pattern_size[0] < pattern_size[0] - 1:
            dist = np.linalg.norm(img_pts[idx] - img_pts[idx + 1])
            distances_px.append(dist)
    avg_dist_px = np.mean(distances_px)
    scale_mm_per_pixel = square_size / avg_dist_px
    return True, pitch_deg, roll_deg, scale_mm_per_pixel, successful_images




 # Used in calibrate_camera_from_samples, compute_perspective_from_samples, test scripts (checkerboard detection)
def find_checkerboard_corners(img, checkerboard_sizes, detected_checkerboard_size=None):
    """Try to find checkerboard corners in the image for all given sizes. Returns (found, size, corners)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sizes_to_try = list(checkerboard_sizes)
    if detected_checkerboard_size and detected_checkerboard_size in sizes_to_try:
        sizes_to_try.remove(detected_checkerboard_size)
        sizes_to_try.insert(0, detected_checkerboard_size)
    for size in sizes_to_try:
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        ret, corners = cv2.findChessboardCorners(gray, size, flags)
        if ret:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            return True, size, corners2
    return False, None, None