#!/usr/bin/env python3
"""
Calibration Offset Window Logik
- Kamera-zu-Werkzeug Offset Kalibrierung
- Live-Kamerabild mit Zoom-Funktion
- Offset-Anpassung über Tasten
"""

import os
import cv2
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from caliOffsetWin import Ui_Form as Ui_CalibrationOffsetWindow
from settings import load_camera_settings, get_camera_id


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
        
        # Entferne Margins
        #self.setContentsMargins(0, 0, 0, 0)
        ##if self.layout():
        #   self.layout().setContentsMargins(0, 0, 0, 0)
        
        # Setup UI und Kamera
        self.setup_ui()
        self.setup_connections()
        self.init_camera()
        
        print("[DEBUG] CalibrationOffsetWindow.__init__() complete")
    
    def setup_ui(self):
        """Initialisiere UI-Elemente"""
        # Erstelle QGraphicsScene für GraphicsView
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        
        # Deaktiviere Scrollbars
        self.ui.gvCamera.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.gvCamera.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Style Counter (orange und bold, wie in caliDistortion)
        self.ui.lCount.setStyleSheet("QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
        
        # Setup Offset-Buttons als checkable (für Icon-Wechsel)
        self.offset_buttons = [self.ui.bXT, self.ui.bXB, self.ui.bYL, self.ui.bYR]
        for btn in self.offset_buttons:
            btn.setCheckable(True)
            btn.setChecked(False)
        
        # Fixe Größe für Pi Zero 2 W (640x480)
        # Im Debug-Modus wird das Fenster nicht fullscreen, daher feste Größe
        screen_width = 640
        screen_height = 480
        
        print(f"[DEBUG] Setting GraphicsView to fixed size: {screen_width}x{screen_height}")
        self.ui.gvCamera.setFixedSize(screen_width, screen_height)
    
    def setup_connections(self):
        """Verbinde UI-Elemente mit Logik"""
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bZoomIn.clicked.connect(self.on_zoom_in_clicked)
        self.ui.bZoomOut.clicked.connect(self.on_zoom_out_clicked)
        self.ui.bAccept.clicked.connect(self.on_accept_clicked)
        
        # Offset-Buttons
        self.ui.bXT.clicked.connect(self.on_xt_clicked)
        self.ui.bXB.clicked.connect(self.on_xb_clicked)
        self.ui.bYR.clicked.connect(self.on_yr_clicked)
        self.ui.bYL.clicked.connect(self.on_yl_clicked)
    
    def init_camera(self):
        """Initialisiere Kamera mit gespeicherten Settings"""
        # Lade Kamera-Settings
        saved_settings = load_camera_settings()
        
        # Finde erste angeschlossene Kamera mit Settings
        for i in range(10):
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                camera_id = get_camera_id(i)
                if camera_id in saved_settings:
                    self.camera_id = camera_id
                    self.camera_settings = saved_settings[camera_id]
                    
                    # Öffne Kamera
                    self.camera = cv2.VideoCapture(i)
                    
                    # Setze Kamera-Parameter
                    fourcc_str = self.camera_settings.get("format", "MJPEG")
                    fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
                    self.camera.set(cv2.CAP_PROP_FOURCC, fourcc)
                    
                    res = self.camera_settings.get("resolution", "640x480")
                    width, height = map(int, res.split('x'))
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    
                    fps = self.camera_settings.get("fps", 30)
                    self.camera.set(cv2.CAP_PROP_FPS, fps)
                    
                    print(f"[LOG] Camera initialized: {camera_id}")
                    print(f"[DEBUG] Camera resolution: {width}x{height}")
                    
                    # Starte Video-Timer
                    self.timer = QTimer(self)
                    self.timer.timeout.connect(self.update_frame)
                    self.timer.start(33)  # ~30 FPS
                    break
        
        if not self.camera:
            print("[ERROR] No camera found with settings!")
    
    def update_frame(self):
        """Aktualisiere Kamera-Bild"""
        if self.camera is None:
            return
            
        ret, frame = self.camera.read()
        if not ret:
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
        # TODO: Speichere Offset-Werte
        self.on_exit_clicked()
    
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
