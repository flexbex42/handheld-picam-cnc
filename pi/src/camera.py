#!/usr/bin/env python3
"""
Camera Handling Module
- Zentrale Kamera-Verwaltung für alle Calibration-Windows
- Öffnet Kamera mit korrekten Settings
- Unterstützt ausgewählte Kamera und Fallback
"""

import os
import cv2


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
        
    def open(self):
        """
        Öffne Kamera mit gespeicherten Settings
        
        Returns:
            bool: True wenn Kamera erfolgreich geöffnet, False sonst
        """
        from caliDevice import get_selected_camera, load_camera_settings, get_camera_id
        
        saved_settings = load_camera_settings()
        
        # Prüfe ob eine Kamera ausgewählt wurde
        selected_index, selected_id = get_selected_camera()
        
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
    
    def read(self):
        """
        Lese ein Frame von der Kamera
        
        Returns:
            tuple: (success, frame) - success ist bool, frame ist numpy array
        """
        if not self.cap or not self.cap.isOpened():
            return False, None
        
        return self.cap.read()
    
    def is_opened(self):
        """
        Prüfe ob Kamera geöffnet ist
        
        Returns:
            bool: True wenn Kamera geöffnet
        """
        return self.cap is not None and self.cap.isOpened()
    
    def release(self):
        """Schließe Kamera"""
        if self.cap:
            self.cap.release()
            self.cap = None
            print(f"[Camera] Released")
    
    def get_resolution(self):
        """
        Hole aktuelle Auflösung
        
        Returns:
            tuple: (width, height)
        """
        res = self.camera_settings.get("resolution", "640x480")
        width, height = map(int, res.split('x'))
        return width, height
    
    def get_camera_id(self):
        """
        Hole Kamera-ID
        
        Returns:
            str: Kamera-ID
        """
        return self.camera_id
    
    def get_camera_settings(self):
        """
        Hole alle Kamera-Settings
        
        Returns:
            dict: Settings Dictionary
        """
        return self.camera_settings
    
    def __enter__(self):
        """Context Manager: Öffne Kamera"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager: Schließe Kamera"""
        self.release()
        return False
