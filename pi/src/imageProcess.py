import numpy as np
import cv2
import appSettings

def average_image(images):
    """
    Takes a list of images (numpy arrays) and returns their average as a single image.
    Images must be the same shape and dtype.
    """
    if not images:
        raise ValueError("No images provided for averaging.")
    # Stack images and compute mean
    avg_img = np.mean(np.stack(images, axis=0), axis=0)
    # Convert to uint8 for display/processing
    avg_img_uint8 = cv2.convertScaleAbs(avg_img)
    return avg_img_uint8

def undistort_image(camera_id, image):
    """
    Undistorts the given image using geometric calibration data from app_settings for the specified camera_id.
    Returns the undistorted image.
    """
    cam_settings = appSettings.get_camera_settings(camera_id)
    calibration = cam_settings.get('calibration', {})
    geom = calibration.get('geometric', {})
    camera_matrix = np.array(geom.get('camera_matrix'), dtype=np.float32)
    dist_coeffs = np.array(geom.get('dist_coeffs'), dtype=np.float32)
    # Only reshape/flatten if needed
    if camera_matrix.shape != (3, 3):
        raise ValueError(f"camera_matrix shape is {camera_matrix.shape}, expected (3, 3)")
    if dist_coeffs.ndim == 2 and dist_coeffs.shape[0] == 1:
        dist_coeffs = dist_coeffs.flatten()
    if dist_coeffs.ndim != 1:
        raise ValueError(f"dist_coeffs shape is {dist_coeffs.shape}, expected 1D array")
    undistorted = cv2.undistort(image, camera_matrix, dist_coeffs)
    return undistorted
