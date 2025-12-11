#!/usr/bin/env python3
"""
Centralized settings file management for the application.
Handles camera selection, calibration settings, and global config.
"""

# Imports
import os
import json
import subprocess

from pydantic import BaseSettings

# Constants and global variables
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "res", "app_settings.json")
_ACTIVE_CAMERA_INDEX = None
_ACTIVE_CAMERA_ID = None

# Global debug flags
_DEBUG_MODE = False
_DEBUG_NO_CAM = False

# Debug flag updater (call at startup)
def update_debug_flags():
    """
    Update debug flags from environment variables.
    Set APP_DEBUG_MODE=1 and/or APP_DEBUG_NO_CAM=1 in your environment to enable.
    """
    global _DEBUG_MODE, _DEBUG_NO_CAM
    _DEBUG_MODE = os.environ.get("APP_DEBUG_MODE", "0") in ("1", "true", "True")
    _DEBUG_NO_CAM = os.environ.get("APP_DEBUG_NO_CAM", "0") in ("1", "true", "True")

# Debug flag getters
def is_debug_mode():
    return _DEBUG_MODE

def is_debug_no_cam():
    return _DEBUG_NO_CAM

# Init functions (helpers)
# Used in caliDistortion.py, caliPerspective.py, camera.py (checkerboard config for calibration)
def get_checkerboard_config():
    """Return (checkerboard_size, square_size_mm) from calibration settings, with defaults."""
    calib_settings = get_calibration_settings()
    if calib_settings:
        checkerboard_boxes = calib_settings.get("checkerboard_boxes", {"x": 11, "y": 8})
        checkerboard_dim = calib_settings.get("checkerboard_dim", {"size_mm": 5})
        checkerboard_size = (checkerboard_boxes["x"] - 1, checkerboard_boxes["y"] - 1)
        square_size = checkerboard_dim["size_mm"]
    else:
        checkerboard_size = (10, 7)
        square_size = 5
    return checkerboard_size, square_size


# Used in caliDistortion.py, caliPerspective.py, camera.py (load calibration settings)
def get_calibration_settings():
    """Get calibration settings from config."""
    return get_app_settings()["calibration_settings"]



# Used in caliDevice.py, camera.py, main.py, caliSelect.py (load all app settings)
def get_app_settings():
    """Load saved camera settings from JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        print("[LOG] No settings file found, creating with defaults")
        settings = {}
        # Add default calibration_settings
        settings["calibration_settings"] = {
            "checkerboard_boxes": {"x": 11, "y": 8},
            "checkerboard_dim": {"size_mm": 5},
            "num_offset_marker": 4
        }
        # Add default hardware_setting with screen_size
        settings["hardware_setting"] = {"screen_size": {"width": 640, "height": 480}}
        save_camera_settings(settings)
        return settings
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            print(f"[LOG] Loaded settings for {len(settings)} camera(s)")
            return settings
    except Exception as e:
        print(f"[ERROR] Could not load settings: {e}")
        return {}



# Used in caliDevice.py, camera.py, main.py (read hardware settings)
def get_hardware_settings():
    """Return hardware_setting from app settings (read-only)."""
    settings = get_app_settings()
    return settings.get("hardware_setting", {})


# Used in caliDevice.py, main.py, camera.py (set selected camera globally)
def set_active_camera(camera_index, camera_id):
    """Set the currently selected camera (global for all windows) and persist to settings file."""
    global _ACTIVE_CAMERA_INDEX, _ACTIVE_CAMERA_ID
    _ACTIVE_CAMERA_INDEX = camera_index
    _ACTIVE_CAMERA_ID = camera_id
    print(f"[LOG] Selected camera set to index={camera_index}, id={camera_id}")
    try:
        settings = get_app_settings()
        settings['active_camera'] = {'id': camera_id, 'device': camera_index}
        save_camera_settings(settings)
        print(f"[LOG] Persisted active_camera to settings: id={camera_id}, device={camera_index}")
    except Exception as e:
        print(f"[ERROR] Could not persist active_camera to settings: {e}")


# Used in caliDevice.py, camera.py, main.py (get selected camera index and id)
def get_active_camera():
    """Get the currently selected camera (index, id) from runtime globals."""
    return _ACTIVE_CAMERA_INDEX, _ACTIVE_CAMERA_ID

# Used in camera.py, main.py (get selected camera id only)
def get_active_camera_id():
    return _ACTIVE_CAMERA_ID


# Used in caliDevice.py, camera.py, main.py (save all app settings to disk)
def save_camera_settings(settings):
    """Save camera settings to JSON file."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        print(f"[DEBUG] Saving settings to: {SETTINGS_FILE}")
        print(f"[DEBUG] Settings dict: {json.dumps(settings, indent=2)}")
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"[LOG] Settings saved to {SETTINGS_FILE}")
        return True
    except Exception as e:
        print(f"[ERROR] Could not save settings: {e}")
        return False


# Used in caliDevice.py (save current camera settings and calibration)
def save_current_camera_settings(saved_settings, camera_id, camera_index, current_format, current_resolution, current_fps):
    """Update and save camera settings, including calibration and active_camera."""
    if not camera_id:
        return

    existing_settings = saved_settings.get(camera_id, {})
    format_changed = existing_settings.get('format') != current_format
    resolution_changed = existing_settings.get('resolution') != current_resolution
    fps_changed = existing_settings.get('fps') != int(current_fps)
    critical_change = format_changed or resolution_changed or fps_changed
    #when we see changes that affect the calibration the camera has to be recalibrated
    if critical_change:
        calibration_data = {}
        if existing_settings:
            print(f"[LOG] Critical camera parameters changed - calibration reset required!")
            print(f"  Format: {existing_settings.get('format')} → {current_format} (changed: {format_changed})")
            print(f"  Resolution: {existing_settings.get('resolution')} → {current_resolution} (changed: {resolution_changed})")
            print(f"  FPS: {existing_settings.get('fps')} → {int(current_fps)} (changed: {fps_changed})")
    else:
        calibration_data = existing_settings.get('calibration', {})
        if calibration_data:
            print(f"[LOG] Device number changed, but calibration data preserved")

    saved_settings[camera_id] = {
        'device': camera_index,
        'format': current_format,
        'resolution': current_resolution,
        'fps': int(current_fps),
        'calibration': calibration_data
    }

    # Ensure active_camera in this in-memory dict matches the runtime selection
    try:
        saved_settings['active_camera'] = {'id': camera_id, 'device': camera_index}
    except Exception:
        saved_settings = get_app_settings()
        saved_settings['active_camera'] = {'id': camera_id, 'device': camera_index}

    if save_camera_settings(saved_settings):
        print(f"[LOG] Saved settings for camera {camera_id}")
    else:
        print(f"[ERROR] Failed to save settings")




# Used in caliPerspective.py, camera.py, caliDevice.py (get settings for a specific camera)
def get_camera_settings(camera_id):
    """Return the settings dict for the given camera_id from the app settings file, or an empty dict if not found."""
    settings = get_app_settings()
    return settings.get(camera_id, {})

def get_active_camera_settings():
    settings = get_app_settings()
    return settings.get(_ACTIVE_CAMERA_ID, {})

# Used in caliPerspective.py, camera.py, caliDevice.py (get calibration for a specific camera)
def get_camera_calibration(camera_id):
    """Return the calibration dict for the given camera_id from the app settings file, or an empty dict if not found."""
    if camera_id is None:
        camera_id=get_active_camera()
    settings = get_app_settings()
    camera_settings = settings.get(camera_id, {})
    return camera_settings.get('calibration', {})
