import cv2
import numpy as np
import appSettings

def rot_scale(image):
    """
    Detects a chessboard in the image and calculates roll, pitch, and scale.
    Uses checkerboard size/dimensions from app_settings calibration.
    Returns (roll_deg, pitch_deg, scale_mm_per_pixel).
    """
    # Get checkerboard config from appSettings
    checkerboard_size, square_size = appSettings.get_checkerboard_config()  # (corners_x, corners_y), size_mm
    # Find chessboard corners
    ret, corners = cv2.findChessboardCorners(image, checkerboard_size, None)
    if not ret:
        raise ValueError("Chessboard not detected in image.")
    # Refine corner locations
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                               criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
    # Prepare object points (real world coordinates)
    objp = np.zeros((checkerboard_size[0]*checkerboard_size[1], 3), np.float32)
    objp[:,:2] = np.mgrid[0:checkerboard_size[0], 0:checkerboard_size[1]].T.reshape(-1,2)
    objp *= square_size
    # Get camera matrix and distortion from active camera
    cam_settings = appSettings.get_active_camera_settings()
    intrinsic = cam_settings.get('intrinsic', {})
    geom = intrinsic.get('geometric', {})
    camera_matrix = np.array(geom.get('camera_matrix'))
    dist_coeffs = np.array(geom.get('dist_coeffs'))
    # Solve for pose
    retval, rvec, tvec = cv2.solvePnP(objp, corners, camera_matrix, dist_coeffs)
    if not retval:
        raise ValueError("Could not solvePnP for chessboard pose.")
    # Convert rotation vector to rotation matrix
    R, _ = cv2.Rodrigues(rvec)
    # Extract roll and pitch from rotation matrix
    # Camera facing down: roll = rotation around x, pitch = rotation around y
    sy = np.sqrt(R[0,0]**2 + R[1,0]**2)
    singular = sy < 1e-6
    if not singular:
        pitch = np.arctan2(-R[2,0], sy)
        roll = np.arctan2(R[2,1], R[2,2])
    else:
        pitch = np.arctan2(-R[2,0], sy)
        roll = 0
    roll_deg = np.degrees(roll)
    pitch_deg = np.degrees(pitch)
    # Calculate scale (mm per pixel)
    # Use distance between first two adjacent corners
    pixel_dist = np.linalg.norm(corners[0] - corners[1])
    scale_mm_per_pixel = square_size / pixel_dist
    return roll_deg, pitch_deg, scale_mm_per_pixel
