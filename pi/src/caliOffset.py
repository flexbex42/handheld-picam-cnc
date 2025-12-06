#!/usr/bin/env python3
"""
Calibration Offset Window Logik
- Kamera-zu-Werkzeug Offset Kalibrierung
- Live-Kamerabild mit Zoom-Funktion
- Offset-Anpassung über Tasten
"""

import os
import cv2
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication, QPushButton
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QImage, QPixmap, QRegion, QIcon, QPainterPath
from caliOffsetWin import Ui_Form as Ui_CalibrationOffsetWindow
from caliDevice import load_camera_settings, get_camera_id


class RoundedButton(QPushButton):
    """Round button with circular click area - distance based"""
    def __init__(self, icon_path=None, diameter=56, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self._radius = diameter / 2.0
        
        # Set size constraints BEFORE stylesheet
        self.setMinimumSize(diameter, diameter)
        self.setMaximumSize(diameter, diameter)
        self.setFixedSize(diameter, diameter)
        
        if icon_path:
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(diameter, diameter))
        
        # Transparent background with visual border-radius, explicit size in stylesheet too
        self.setStyleSheet(f"""
            QPushButton {{
                border: none; 
                background: transparent; 
                border-radius: {diameter//2}px;
                min-width: {diameter}px;
                max-width: {diameter}px;
                min-height: {diameter}px;
                max-height: {diameter}px;
            }}
        """)

    def mousePressEvent(self, event):
        """Only accept clicks inside a circular radius"""
        # Calculate distance from center
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        
        dx = event.pos().x() - center_x
        dy = event.pos().y() - center_y
        distance = (dx * dx + dy * dy) ** 0.5
        
        # Absolute position on screen
        abs_pos = self.mapToGlobal(event.pos())
        
        # Only accept if inside radius (with small margin for better UX)
        if distance <= self._radius * 0.9:  # 90% of radius for tighter click area
            print(f"Click inside circle: abs=({abs_pos.x()},{abs_pos.y()}), local=({event.pos().x()},{event.pos().y()}), distance={distance:.1f}, radius={self._radius:.1f}")
            super().mousePressEvent(event)
        else:
            print(f"Click OUTSIDE circle: abs=({abs_pos.x()},{abs_pos.y()}), local=({event.pos().x()},{event.pos().y()}), distance={distance:.1f}, radius={self._radius:.1f}")
            event.ignore()


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
        
        # Ersetze bAccept und bDecline durch RoundedButton mit echter runder Hit-Area
        # bDecline
        old_decline = self.ui.bDecline
        self.ui.bDecline = RoundedButton(icon_path=":/icons/undo.png", diameter=56, parent=self)
        self.ui.bDecline.move(0, 300)
        old_decline.hide()
        # Connection wird in setup_connections() gemacht (falls vorhanden)
        
        # bAccept
        old_accept = self.ui.bAccept
        self.ui.bAccept = RoundedButton(icon_path=":/icons/ok.png", diameter=56, parent=self)
        self.ui.bAccept.move(90, 300)
        old_accept.hide()
        # Connection wird in setup_connections() gemacht
        
        # Debug: Zeige Button-Positionen und Parent-Info
        print(f"[DEBUG] bAccept parent: {self.ui.bAccept.parent()}")
        print(f"[DEBUG] bAccept layoutDirection: {self.ui.bAccept.layoutDirection()}")
        print(f"[DEBUG] Form layoutDirection: {self.layoutDirection()}")
        print(f"[DEBUG] bDecline pos: {self.ui.bDecline.pos()}, geometry: {self.ui.bDecline.geometry()}")
        print(f"[DEBUG] bAccept pos: {self.ui.bAccept.pos()}, geometry: {self.ui.bAccept.geometry()}")
        print(f"[DEBUG] bExit pos: {self.ui.bExit.pos()}, geometry: {self.ui.bExit.geometry()}")
        
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
        self.ui.bDecline.clicked.connect(self.on_decline_clicked)
        # Offset-Buttons
        self.ui.bXT.clicked.connect(self.on_xt_clicked)
        self.ui.bXB.clicked.connect(self.on_xb_clicked)
        self.ui.bYR.clicked.connect(self.on_yr_clicked)
        self.ui.bYL.clicked.connect(self.on_yl_clicked)
    
    def init_camera(self):
        """Initialisiere Kamera mit gespeicherten Settings"""
        # Lade Kamera-Settings
        from caliDevice import get_selected_camera
        saved_settings = load_camera_settings()
        
        # Prüfe ob eine Kamera ausgewählt wurde
        selected_index, selected_id = get_selected_camera()
        
        camera_found = False
        if selected_index is not None and selected_id is not None:
            # Nutze ausgewählte Kamera
            print(f"[LOG] Using selected camera: index={selected_index}, id={selected_id}")
            self.camera_id = selected_id
            self.camera_settings = saved_settings.get(selected_id, {})
            
            # Öffne Kamera mit V4L2 Backend (wichtig für Linux)
            self.camera = cv2.VideoCapture(selected_index, cv2.CAP_V4L2)
            camera_found = True
        else:
            # Fallback: Finde erste angeschlossene Kamera mit Settings
            print("[LOG] No camera selected, using first available camera with settings")
            for i in range(10):
                video_path = f"/dev/video{i}"
                if os.path.exists(video_path):
                    camera_id = get_camera_id(i)
                    if camera_id in saved_settings:
                        self.camera_id = camera_id
                        self.camera_settings = saved_settings[camera_id]
                        
                        # Öffne Kamera mit V4L2 Backend (wichtig für Linux)
                        self.camera = cv2.VideoCapture(i, cv2.CAP_V4L2)
                        camera_found = True
                        break
        
        # Setze Kamera-Parameter (falls Kamera geöffnet wurde)
        if camera_found and self.camera and self.camera.isOpened():
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
            
            print(f"[LOG] Camera initialized: {self.camera_id}")
            print(f"[DEBUG] Camera resolution: {width}x{height}")
            
            # Starte Video-Timer
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(33)  # ~30 FPS
        else:
            print("[ERROR] No camera found or could not open camera!")
    
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

