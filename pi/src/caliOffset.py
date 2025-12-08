
#!/usr/bin/env python3
"""
Calibration Offset Window Logik
- Kamera-zu-Werkzeug Offset Kalibrierung
- Live-Kamerabild mit Zoom-Funktion
- Offset-Anpassung über Tasten
"""

import os
import cv2
import numpy as np
from rectificationHelper import undistort_image, rectify_image
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from caliOffsetWin import Ui_Form as Ui_CalibrationOffsetWindow
from appSettings import load_camera_settings, get_calibration_settings, get_hardware_settings
import camera
from roundbutton import RoundedButton


class CalibrationOffsetWindow(QWidget):
    """Offset Calibration Window mit Kamera-Feed"""
    
    def __init__(self, parent=None, on_back_callback=None):
        super().__init__(parent)
        
        print("[DEBUG] CalibrationOffsetWindow.__init__() called")
        
        # Callbacks
        self.on_back_callback = on_back_callback
        
        # Kamera Setup
        self.camera = None
        self.camera_id = None
        self.camera_settings = {}
        self.timer = None
        
        # Zoom-Einstellungen
        self.zoom_level = 1.0
        self.zoom_min = 1.0
        self.zoom_max = 4.0
        self.zoom_step = 0.5
        
        # Offset-Button Gruppe (für exklusives Verhalten)
        self.offset_buttons = []
        self.active_offset_button = None
        
        # UI Setup
        print("[DEBUG] Setting up UI...")
        self.ui = Ui_CalibrationOffsetWindow()
        self.ui.setupUi(self)
        print("[DEBUG] UI setup complete")
        
        # Debug: Zeige Widget-Geometrie
        print(f"[DEBUG] Form Widget Geometry: {self.geometry()}")
        print(f"[DEBUG] Form Widget Size: {self.size()}")
        print(f"[DEBUG] Form Widget Pos: {self.pos()}")
        
        # Entferne Margins
        #self.setContentsMargins(0, 0, 0, 0)
        ##if self.layout():
        #   self.layout().setContentsMargins(0, 0, 0, 0)
        
        # Setup UI und Kamera
        self.setup_ui()
        self.setup_connections()
        
        # Initialisiere Kamera mit Camera-Klasse
        self.camera = Camera()
        if self.camera.open():
            self.camera_id = self.camera.get_camera_id()
            self.camera_settings = self.camera.get_camera_settings()
            print(f"[LOG] Camera initialized: {self.camera_id}")
            
            # Starte Video-Timer
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(33)  # ~30 FPS
        else:
            print("[ERROR] Failed to open camera!")
        
        print("[DEBUG] CalibrationOffsetWindow.__init__() complete")
    
    def showEvent(self, event):
        """Override showEvent to ensure buttons are visible"""
        super().showEvent(event)
        # Force buttons to show after window is visible
        if hasattr(self.ui, 'bZoomIn') and isinstance(self.ui.bZoomIn, RoundedButton):
            self.ui.bZoomIn.raise_()
            self.ui.bZoomOut.raise_()
            self.ui.bDecline.raise_()
            self.ui.bAccept.raise_()
            self.ui.bXT.raise_()
            self.ui.bXB.raise_()
            self.ui.bYL.raise_()
            self.ui.bYR.raise_()
            # optional: raise newly added sample button if present
            if hasattr(self.ui, 'bSampel') and isinstance(self.ui.bSampel, RoundedButton):
                self.ui.bSampel.raise_()
            print("[DEBUG] Raised all RoundedButtons to front")
    
    def setup_ui(self):
        """Initialisiere UI-Elemente"""
        # Erstelle QGraphicsScene für GraphicsView
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        
        # Deaktiviere Scrollbars
        self.ui.gvCamera.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.gvCamera.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Schiebe GraphicsView nach hinten in der Z-Order
        self.ui.gvCamera.lower()
        
        # Style Counter (orange und bold, wie in caliDistortion)
        self.ui.lCount.setStyleSheet("QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
        
        # Ersetze Buttons durch RoundedButton mit echter runder Hit-Area
        # NICHT bExit - der ist im Layout und bleibt wie er ist
        
        # Zoom und Accept/Decline Buttons
        self.ui.bZoomIn = RoundedButton(icon_path=":/icons/plus.png", diameter=56, parent=self, old_button=self.ui.bZoomIn)
        self.ui.bZoomOut = RoundedButton(icon_path=":/icons/minus.png", diameter=56, parent=self, old_button=self.ui.bZoomOut)
        self.ui.bDecline = RoundedButton(icon_path=":/icons/undo.png", diameter=56, parent=self, old_button=self.ui.bDecline)
        self.ui.bAccept = RoundedButton(icon_path=":/icons/ok.png", diameter=56, parent=self, old_button=self.ui.bAccept)
        
        # Offset-Buttons (Richtungs-Buttons) - mit aktivem Icon
        self.ui.bXT = RoundedButton(icon_path=":/icons/offsetXT.png", diameter=56, parent=self, old_button=self.ui.bXT, active_icon_path=":/icons/offsetXTA.png")
        self.ui.bXB = RoundedButton(icon_path=":/icons/offsetXB.png", diameter=56, parent=self, old_button=self.ui.bXB, active_icon_path=":/icons/offsetXBA.png")
        self.ui.bYL = RoundedButton(icon_path=":/icons/offsetYL.png", diameter=56, parent=self, old_button=self.ui.bYL, active_icon_path=":/icons/offsetYLA.png")
        self.ui.bYR = RoundedButton(icon_path=":/icons/offsetYR.png", diameter=56, parent=self, old_button=self.ui.bYR, active_icon_path=":/icons/offsetYRA.png")
        
        # Sample / Foto Button (neu in UI) -> ebenfalls RoundedButton
        self.ui.bSampel = RoundedButton(icon_path=":/icons/foto.png", diameter=56, parent=self, old_button=self.ui.bSampel, active_icon_path=":/icons/freeze.png")
           
        
        
        # Setup Offset-Buttons Liste
        self.offset_buttons = [self.ui.bXT, self.ui.bXB, self.ui.bYL, self.ui.bYR]

        # Initially hide controls: keep only bExit and bSampel visible
        # This lets the UI start in a minimal mode; other controls can be shown later
        try:
            for btn in (self.ui.bZoomIn, self.ui.bZoomOut, self.ui.bDecline, self.ui.bAccept,
                        self.ui.bXT, self.ui.bXB, self.ui.bYL, self.ui.bYR):
                if hasattr(btn, 'hide'):
                    btn.hide()
        except Exception:
            # Non-fatal: if any button is missing, continue
            pass

        # Ensure Exit and Sample remain visible
        try:
            if hasattr(self.ui, 'bExit'):
                self.ui.bExit.show()
            if hasattr(self.ui, 'bSampel'):
                self.ui.bSampel.show()
        except Exception:
            pass

        # Raise all buttons to front (wichtig für Z-Order)
        
        # Hole Screen-Größe aus Kalibrierungs-Einstellungen
        hardware_settings = get_hardware_settings()
        screen_size = hardware_settings.get("screen_size", {"width": 640, "height": 480})
        screen_width = screen_size["width"]
        screen_height = screen_size["height"]
        
        print(f"[DEBUG] Setting GraphicsView to fixed size: {screen_width}x{screen_height}")
        self.ui.gvCamera.setFixedSize(screen_width, screen_height)
    
    def setup_connections(self):
        """Verbinde UI-Elemente mit Logik"""
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bZoomIn.clicked.connect(self.on_zoom_in_clicked)
        self.ui.bZoomOut.clicked.connect(self.on_zoom_out_clicked)
        self.ui.bAccept.clicked.connect(self.on_accept_clicked)
        self.ui.bDecline.clicked.connect(self.on_decline_clicked)
        # Offset-Buttons
        self.ui.bXT.clicked.connect(self.on_xt_clicked)
        self.ui.bXB.clicked.connect(self.on_xb_clicked)
        self.ui.bYR.clicked.connect(self.on_yr_clicked)
        self.ui.bYL.clicked.connect(self.on_yl_clicked)
        # Sample / Foto Button
        # bSampel exists in this UI; connect directly
        self.ui.bSampel.clicked.connect(self.on_sample_clicked)
    
    def update_frame(self):
        """Aktualisiere Kamera-Bild"""
        if self.camera is None or not self.camera.is_opened():
            return
            
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return
        
        # Konvertiere BGR zu RGB für Anzeige
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Wende Zoom an
        if self.zoom_level > 1.0:
            h, w = frame_rgb.shape[:2]
            # Berechne Crop-Region für Zoom (zentriert)
            crop_h = int(h / self.zoom_level)
            crop_w = int(w / self.zoom_level)
            start_y = (h - crop_h) // 2
            start_x = (w - crop_w) // 2
            frame_rgb = frame_rgb[start_y:start_y+crop_h, start_x:start_x+crop_w]
        
        # Zeige Bild in GraphicsView
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        
        # Skaliere auf GraphicsView-Größe
        scaled_pixmap = pixmap.scaled(self.ui.gvCamera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.scene.clear()
        self.scene.addPixmap(scaled_pixmap)

    def on_sample_clicked(self):
        """Nimmt 4 stehende Fotos, verbessert (mittelt), wendet Kamerakorrekturen an und zeigt Ergebnis.
        Versteckt das Live-Bild (Timer wird gestoppt).
        """
        print("[LOG] Sample button clicked")

        # If the sample button is now UNCHECKED -> resume live feed
        if not self.ui.bSampel.isChecked():
            print("[LOG] Resume live camera")
            if self.timer and not self.timer.isActive():
                self.timer.start(33)
            # Force one frame update
            self.update_frame()
            return

        # Stoppe Live-Update for freeze/capture
        if self.timer and self.timer.isActive():
            self.timer.stop()

        if self.camera is None or not self.camera.is_opened():
            print("[ERROR] Camera not opened - cannot take samples")
            return

        frames = []
        # Capture 4 frames as stills
        for i in range(4):
            ret, frame = self.camera.read()
            if not ret or frame is None:
                print(f"[WARN] Failed to read frame {i}")
                continue
            frames.append(frame.astype(np.float32))

        if len(frames) == 0:
            print("[ERROR] No frames captured")
            return

        # Average frames to reduce noise
        avg = np.mean(frames, axis=0).astype(np.uint8)

        # Apply camera corrections and perspective rectification using rectificationHelper
        from appSettings import load_camera_settings
        cam_id = self.camera.get_camera_id()
        settings = load_camera_settings()
        cam_settings = settings.get(cam_id, {})
        geom = cam_settings.get('calibration', {}).get('geometric', {})
        camera_matrix = None
        dist_coeffs = None
        if 'camera_matrix' in geom and 'dist_coeffs' in geom:
            camera_matrix = np.array(geom['camera_matrix'], dtype=np.float64)
            dist_coeffs = np.array(geom['dist_coeffs'], dtype=np.float64).reshape(-1)
        pers = cam_settings.get('calibration', {}).get('perspective', {})
        tilt_deg = pers.get('tilt_deg')
        yaw_deg = pers.get('yaw_deg')
        if camera_matrix is not None and dist_coeffs is not None:
            if tilt_deg is not None and yaw_deg is not None:
                print(f"[LOG] Applying undistort and perspective rectification: tilt={tilt_deg:.2f}°, yaw={yaw_deg:.2f}°")
                undist = rectify_image(avg, camera_matrix, dist_coeffs, tilt_deg, yaw_deg)
            else:
                print("[LOG] Applying undistort only (no perspective)")
                undist = undistort_image(avg, camera_matrix, dist_coeffs)
        else:
            print("[LOG] No geometric calibration found - skipping undistort")
            undist = avg

        # Convert to QPixmap and show in scene (replace live feed)
        try:
            # Save rectified output so it's persisted for tools and inspection
            try:
                sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sample'))
                os.makedirs(sample_dir, exist_ok=True)
                out_path = os.path.join(sample_dir, 'testimage_rectified.png')
                cv2.imwrite(out_path, undist)
                print(f"[LOG] Saved rectified sample to: {out_path}")

                # reload to ensure displayed image matches file
                try:
                    loaded = cv2.imread(out_path)
                    if loaded is not None:
                        undist = loaded
                        print(f"[LOG] Loaded rectified sample from disk for display: {out_path}")
                    else:
                        print(f"[WARN] Saved rectified file could not be reloaded: {out_path}")
                except Exception as _e2:
                    print(f"[WARN] Failed to reload rectified sample: {_e2}")
            except Exception as _e:
                print(f"[WARN] Could not save rectified sample: {_e}")

            frame_rgb = cv2.cvtColor(undist, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(self.ui.gvCamera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.scene.clear()
            self.scene.addPixmap(scaled_pixmap)
            print("[LOG] Processed sample displayed")
        except Exception as e:
            print(f"[ERROR] Failed to display processed image: {e}")
    
    def on_exit_clicked(self):
        """Exit Button: Schließe Fenster"""
        print("[LOG] Exit Offset Calibration")
        
        # Stoppe Kamera
        if self.timer:
            self.timer.stop()
        if self.camera:
            self.camera.release()
        
        if self.on_back_callback:
            self.on_back_callback()
        self.close()
    
    def on_zoom_in_clicked(self):
        """Zoom In Button"""
        if self.zoom_level < self.zoom_max:
            self.zoom_level += self.zoom_step
            print(f"[LOG] Zoom In: {self.zoom_level}x")
    
    def on_zoom_out_clicked(self):
        """Zoom Out Button"""
        if self.zoom_level > self.zoom_min:
            self.zoom_level -= self.zoom_step
            print(f"[LOG] Zoom Out: {self.zoom_level}x")
    
    def on_accept_clicked(self):
        """Accept Button: Speichere Offset"""
        print("[LOG] Accept Offset Calibration")

    
    def set_active_offset_button(self, button):
        """Setze einen Offset-Button als aktiv und deaktiviere alle anderen"""
        for btn in self.offset_buttons:
            if btn == button:
                btn.setChecked(True)
                self.active_offset_button = btn
            else:
                btn.setChecked(False)
    
    def on_xt_clicked(self):
        """X Top Button: Bewege Offset nach oben"""
        print("[LOG] Offset X Top (Up)")
        self.set_active_offset_button(self.ui.bXT)
        # TODO: Implementiere Offset-Anpassung
    
    def on_xb_clicked(self):
        """X Bottom Button: Bewege Offset nach unten"""
        print("[LOG] Offset X Bottom (Down)")
        self.set_active_offset_button(self.ui.bXB)
        # TODO: Implementiere Offset-Anpassung
    
    def on_yr_clicked(self):
        """Y Right Button: Bewege Offset nach rechts"""
        print("[LOG] Offset Y Right")
        self.set_active_offset_button(self.ui.bYR)
        # TODO: Implementiere Offset-Anpassung
    
    def on_yl_clicked(self):
        """Y Left Button: Bewege Offset nach links"""
        print("[LOG] Offset Y Left")
        self.set_active_offset_button(self.ui.bYL)
        # TODO: Implementiere Offset-Anpassung

    def on_decline_clicked(self):
        """Decline Button: Verwerfe Änderungen und schließe Fenster"""
        print("[LOG] Decline Offset Calibration")

