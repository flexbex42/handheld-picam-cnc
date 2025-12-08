#!/usr/bin/env python3
"""
Centralized settings file management for the application.
Handles camera selection, calibration settings, and global config.
"""

import os
import json
import subprocess

# Settings File Path (relative to src/)
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "res", "app_settings.json")

# Global variable for selected camera (runtime only)
_SELECTED_CAMERA_INDEX = None
_SELECTED_CAMERA_ID = None


def set_selected_camera(camera_index, camera_id):
    """Set the currently selected camera (global for all windows) and persist to settings file."""
    global _SELECTED_CAMERA_INDEX, _SELECTED_CAMERA_ID
    _SELECTED_CAMERA_INDEX = camera_index
    _SELECTED_CAMERA_ID = camera_id
    print(f"[LOG] Selected camera set to index={camera_index}, id={camera_id}")
    try:
        settings = load_camera_settings()
        settings['active_camera'] = {'id': camera_id, 'device': camera_index}
        save_camera_settings(settings)
        print(f"[LOG] Persisted active_camera to settings: id={camera_id}, device={camera_index}")
    except Exception as e:
        print(f"[ERROR] Could not persist active_camera to settings: {e}")


def get_selected_camera():
    """Get the currently selected camera (index, id) from runtime globals."""
    return _SELECTED_CAMERA_INDEX, _SELECTED_CAMERA_ID


def get_camera_id(camera_index):
    """Get unique camera ID (Serial Number or USB Path) for a given index."""
    try:
        video_device = f"/dev/video{camera_index}"
        result = subprocess.run(
            ['udevadm', 'info', '--query=property', '--name', video_device],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            serial = None
            path = None
            for line in result.stdout.split('\n'):
                if line.startswith('ID_SERIAL='):
                    serial = line.split('=', 1)[1]
                elif line.startswith('ID_PATH='):
                    path = line.split('=', 1)[1]
            camera_id = serial or path or f"video{camera_index}"
            print(f"[LOG] Camera {camera_index} ID: {camera_id}")
            return camera_id
    except Exception as e:
        print(f"[ERROR] Could not get camera ID: {e}")
    return f"video{camera_index}"


def load_camera_settings():
    """Load saved camera settings from JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        print("[LOG] No settings file found, creating with defaults")
        settings = {}
        # Add default calibration_settings
        settings["calibration_settings"] = get_default_calibration_settings()
        # Add default hardware_setting with screen_size
        settings["hardware_setting"] = {"screen_size": {"width": 640, "height": 480}}
        save_camera_settings(settings)
        return settings
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            print(f"[LOG] Loaded settings for {len(settings)} camera(s)")
            if "calibration_settings" not in settings:
                settings["calibration_settings"] = get_default_calibration_settings()
                save_camera_settings(settings)
                print("[LOG] Added default calibration_settings to config")
            return settings
    except Exception as e:
        print(f"[ERROR] Could not load settings: {e}")
        return {}


def get_default_calibration_settings():
    """Return default calibration settings."""
    return {
        "checkerboard_boxes": {"x": 11, "y": 8},
        "checkerboard_dim": {"size_mm": 5}
    }
def get_hardware_settings():
    """Return hardware_setting from app settings (read-only)."""
    settings = load_camera_settings()
    return settings.get("hardware_setting", {})


def get_calibration_settings():
    """Get calibration settings from config."""
    settings = load_camera_settings()
    if "calibration_settings" in settings:
        return settings["calibration_settings"]
    return get_default_calibration_settings()


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
        saved_settings = load_camera_settings()
        saved_settings['active_camera'] = {'id': camera_id, 'device': camera_index}

    if save_camera_settings(saved_settings):
        print(f"[LOG] Saved settings for camera {camera_id}")
    else:
        print(f"[ERROR] Failed to save settings")
