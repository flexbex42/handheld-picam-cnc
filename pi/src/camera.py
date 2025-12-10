#!/usr/bin/env python3
"""
Camera Handling Module
- Zentrale Kamera-Verwaltung für alle Calibration-Windows
- Öffnet Kamera mit korrekten Settings
- Unterstützt ausgewählte Kamera und Fallback
"""

# Imports
import os
import cv2
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage
import appSettings

# Hardware-related: Get unique camera ID (Serial Number or USB Path) for a given index
def get_camera_id(camera_index):
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

# Called in caliDistortion.py line 83 and in this file
def setup_camera():
    """Centralized camera setup: returns (Camera instance, camera_id, camera_settings)."""
    cam = Camera()
    cam_id = None
    cam_settings = {}
    if cam.open():
        cam_id = cam.get_camera_id()
        cam_settings = cam.get_camera_settings()
    return cam, cam_id, cam_settings

# Called in caliSelect.py lines 59, 61 and main.py lines 83, 85
def update_active_camera_info(max_devices=10):
    """
    Returns (camera_id, device_number) for the active camera.
    Logic:
    1. If active camera is connected, return it.
    2. Else, if any camera with settings is connected, set as active and return.
    3. Else, if any camera is present, create new profile, save, set as active, and return.
    4. Else, return None.
    """
    settings = appSettings.load_app_settings()
    active_cam = settings.get('active_camera', {})
    active_id = active_cam.get('id')
    # 1. Check if active camera is connected
    for i in range(max_devices):
        video_path = f"/dev/video{i}"
        if os.path.exists(video_path):
            cam_id = get_camera_id(i)
            if active_id and cam_id == active_id:
                return cam_id, i
    # 2. Check for any camera with settings
    for i in range(max_devices):
        video_path = f"/dev/video{i}"
        if os.path.exists(video_path):
                cam_id = get_camera_id(i)
                if cam_id in settings:
                    appSettings.set_active_camera(i, cam_id)
                return cam_id, i
    # 3. Check for any present camera
    for i in range(max_devices):
        video_path = f"/dev/video{i}"
        if os.path.exists(video_path):
            cam_id = get_camera_id(i)
            # Create new profile
            settings[cam_id] = {"calibration": {}, "resolution": "640x480", "format": "MJPEG", "fps": 30}
            appSettings.save_camera_settings(settings)
            appSettings.set_active_camera(i, cam_id)
            return cam_id, i
    # 4. No camera found
    return None

# Called in caliDevice.py lines 118, 489, caliPerspective.py lines 167, 242, 358, and in this file
def list_video_devices(max_devices=10):
    """List all available /dev/video* devices (as indices)."""
    devices = []
    for i in range(max_devices):
        video_path = f"/dev/video{i}"
        if os.path.exists(video_path):
            # Optionally check if device can be opened with V4L2
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                devices.append(i)
            cap.release()
    return devices


# Called in caliDevice.py lines 145, 216 and in this file
def get_camera_capabilities(camera_index):
    """Query supported formats, resolutions, and FPS using v4l2-ctl."""
    video_device = f"/dev/video{camera_index}"
    try:
        result = subprocess.run(
            ['v4l2-ctl', '--device', video_device, '--list-formats-ext'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"[ERROR] v4l2-ctl failed: {result.stderr}")
            return {}
        output = result.stdout
        formats = {}
        current_format = None
        current_resolution = None
        for line in output.split('\n'):
            # Format line: "[0]: 'MJPG' (Motion-JPEG, compressed)"
            if "'" in line and ":" in line:
                parts = line.split(":", 1)
                if len(parts) > 1 and "'" in parts[1]:
                    fmt = parts[1].split("'", 2)[1]
                    current_format = fmt
                    formats[current_format] = {}
                    continue
            # Resolution line: "Size: Discrete 640x480"
            if "Size: Discrete" in line:
                res = line.split("Size: Discrete", 1)[1].strip()
                current_resolution = res
                if current_format:
                    formats[current_format][current_resolution] = []
                continue
            # FPS line: "Interval: Discrete 0.033s (30.000 fps)"
            if "fps)" in line:
                try:
                    fps = int(float(line.split("(")[-1].split()[0]))
                    if current_format and current_resolution:
                        if fps not in formats[current_format][current_resolution]:
                            formats[current_format][current_resolution].append(fps)
                except Exception:
                    pass
        return formats
    except subprocess.TimeoutExpired:
        print(f"[ERROR] v4l2-ctl timeout for {video_device}")
        return {}
    except FileNotFoundError:
        print(f"[ERROR] v4l2-ctl not found - install with: sudo apt install v4l-utils")
        return {}
    except Exception as e:
        print(f"[ERROR] Could not read camera capabilities: {e}")
        return {}

# Called in caliDevice.py line 481 and in this file
# non-blocking, real-time display, you need a threaded or asynchronous approach
class VideoThread(QThread):
    """Thread for camera capture (non-blocking) provided as a reusable helper.

    This encapsulates the simple capture loop and emits QImage frames via
    the `change_pixmap_signal` so UI code doesn't need to reimplement it.
    """

    change_pixmap_signal = pyqtSignal(QImage)

    def __init__(self, camera_index=0, width=640, height=480, fps=30, fourcc=None):
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.fourcc = fourcc
        self._run_flag = True

    def run(self):
        """Main loop: read frames and emit QImage frames for the UI."""
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)

        if not cap.isOpened():
            print(f"[ERROR] Could not open camera {self.camera_index}")
            return

        if self.fourcc is not None:
            cap.set(cv2.CAP_PROP_FOURCC, self.fourcc)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(cap.get(cv2.CAP_PROP_FPS))

        print(f"[LOG] Camera {self.camera_index} opened: {actual_width}x{actual_height} @ {actual_fps}fps")

        while self._run_flag:
            ret, frame = cap.read()
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.change_pixmap_signal.emit(qt_image)
            else:
                print("[ERROR] Failed to read frame")
                break

        cap.release()
        print(f"[LOG] Camera {self.camera_index} released")

    def stop(self):
        """Stop the thread cleanly."""
        print("[LOG] Stopping video thread...")
        self._run_flag = False
        self.wait()


"""
Camera Handling Module
- Zentrale Kamera-Verwaltung für alle Calibration-Windows
- Öffnet Kamera mit korrekten Settings
- Unterstützt ausgewählte Kamera und Fallback
"""

# Imports
import os
import cv2
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage
import appSettings 


# Camera class and init
# Called in caliDistortion.py line 118, caliOffset.py line 70, caliPerspective.py lines 138, 259, and in this file
# those tasks only need to grab frames occasionally or process images without live display, the synchronous Camera class is fine.
class Camera:
    """
    Kamera-Wrapper für einheitliches Kamera-Handling
    
    Features:
    - Automatische Auswahl der konfigurierten Kamera
    - Fallback auf erste verfügbare Kamera
    - V4L2 Backend für Linux-Kompatibilität
    - Automatische Parametereinstellung (Format, Resolution, FPS)
    """
    
    def __init__(self):
        self.cap = None
        self.camera_id = None
        self.camera_settings = {}
        self.camera_index = None
        
    # Called in: caliOffset.py, caliDistortion.py, caliPerspective.py, camera.py
    def open(self):
        """
        Öffne Kamera mit gespeicherten Settings
        
        Returns:
            bool: True wenn Kamera erfolgreich geöffnet, False sonst
        """
        # use appSettings functions
        saved_settings = appSettings.load_app_settings()
        
        # Prüfe ob eine Kamera ausgewählt wurde
        selected_index, selected_id = appSettings.get_active_camera()
        
        if selected_index is not None and selected_id is not None:
            # Nutze ausgewählte Kamera
            print(f"[Camera] Using selected camera: index={selected_index}, id={selected_id}")
            self.camera_index = selected_index
            self.camera_id = selected_id
            self.camera_settings = saved_settings.get(selected_id, {})
            
            # Öffne Kamera mit V4L2 Backend (wichtig für Linux)
            self.cap = cv2.VideoCapture(selected_index, cv2.CAP_V4L2)
            
            if self.cap and self.cap.isOpened():
                self._apply_settings()
                return True
        
        # Fallback: Finde erste angeschlossene Kamera mit Settings
        print("[Camera] No camera selected, using first available camera with settings")
        for i in range(10):
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                camera_id = get_camera_id(i)
                if camera_id in saved_settings:
                    self.camera_index = i
                    self.camera_id = camera_id
                    self.camera_settings = saved_settings[camera_id]
                    
                    # Öffne Kamera mit V4L2 Backend (wichtig für Linux)
                    self.cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
                    
                    if self.cap and self.cap.isOpened():
                        self._apply_settings()
                        return True
                    break
        
        print("[Camera] ERROR: No camera found or could not open camera!")
        return False
    
    # Called internally by Camera.open()
    def _apply_settings(self):
        """Wende gespeicherte Kamera-Parameter an"""
        if not self.cap or not self.cap.isOpened():
            return
        
        # Setze Format (FOURCC)
        fourcc_str = self.camera_settings.get("format", "MJPEG")
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        
        # Setze Auflösung
        res = self.camera_settings.get("resolution", "640x480")
        width, height = map(int, res.split('x'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Setze FPS
        fps = self.camera_settings.get("fps", 30)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        print(f"[Camera] Initialized: {self.camera_id}")
        print(f"[Camera] Resolution: {width}x{height} @ {fps}fps, Format: {fourcc_str}")
    
    # Called in: caliOffset.py, caliDistortion.py, caliPerspective.py, camera.py
    def read(self):
        """
        Lese ein Frame von der Kamera
        
        Returns:
            tuple: (success, frame) - success ist bool, frame ist numpy array
        """
        if not self.cap or not self.cap.isOpened():
            return False, None
        
        return self.cap.read()
    
    # Called in: caliOffset.py, caliDistortion.py, camera.py
    def is_opened(self):
        """
        Prüfe ob Kamera geöffnet ist
        
        Returns:
            bool: True wenn Kamera geöffnet
        """
        return self.cap is not None and self.cap.isOpened()
    
    # Called in: caliOffset.py, caliDistortion.py, caliPerspective.py, camera.py
    def release(self):
        """Schließe Kamera"""
        if self.cap:
            self.cap.release()
            self.cap = None
            print(f"[Camera] Released")
    
    # Only called in camera.py
    def get_resolution(self):
        """
        Hole aktuelle Auflösung
        
        Returns:
            tuple: (width, height)
        """
        res = self.camera_settings.get("resolution", "640x480")
        width, height = map(int, res.split('x'))
        return width, height
    
    # Called in: caliOffset.py, caliDistortion.py, caliPerspective.py, camera.py
    def get_camera_id(self):
        """
        Hole Kamera-ID
        
        Returns:
            str: Kamera-ID
        """
        return self.camera_id
    
    # Called in: caliOffset.py, caliDistortion.py, caliPerspective.py, camera.py
    def get_camera_settings(self):
        """
        Hole alle Kamera-Settings
        
        Returns:
            dict: Settings Dictionary
        """
        return self.camera_settings
    
    # Used for context management (with statement), not directly called elsewhere
    def __enter__(self):
        """Context Manager: Öffne Kamera"""
        self.open()
        return self

    # Used for context management (with statement), not directly called elsewhere
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager: Schließe Kamera"""
        self.release()
        return False

    # Only called in camera.py
    def get_info(self):
        """Return current camera info (resolution, FPS, format) if opened."""
        if not self.cap or not self.cap.isOpened():
            return None
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        fmt = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        return {"width": width, "height": height, "fps": fps, "format": fmt}
