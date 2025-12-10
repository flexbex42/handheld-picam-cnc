
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
import rectifyHelper
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QTransform
from caliOffsetWin import Ui_Form as Ui_CalibrationOffsetWindow
import appSettings
import camera
from roundbutton import RoundedButton


class CalibrationOffsetWindow(QWidget):
    """Offset Calibration Window mit Kamera-Feed"""

    def reset_marker_workflow(self):
        self.marker_workflow_active = False
        self.current_marker = None
        self.current_marker_btn = None
        self.marker_moving = False
        # Hide Accept/Decline
        self.ui.bAccept.hide()
        self.ui.bDecline.hide()
        # Show offset buttons only if bSampel is checked
        if hasattr(self.ui, 'bSampel') and self.ui.bSampel.isChecked():
            for btn in self.offset_buttons:
                btn.show()
        else:
            for btn in self.offset_buttons:
                btn.hide()
        # Reset zoom to 1x
        self.zoom_level = 1.0
        # Reset view transform and center on full image
        transform = QTransform()
        self.ui.gvCamera.setTransform(transform)
        self.ui.gvCamera.centerOn(self.scene.sceneRect().center())

    def start_marker_workflow(self, btn_name, x, y):
        self.marker_workflow_active = True
        self.current_marker_btn = btn_name
        self.current_marker = (x, y)
        self.marker_moving = False
        self.last_marker_btn_name = btn_name  # Track which button the marker is for
        # Zoom 4x on marker
        self.zoom_level = 4.0
        self.zoom_to_position(x, y)
        # Hide offset buttons
        for btn in self.offset_buttons:
            btn.hide()
        # Show Accept/Decline
        self.ui.bAccept.show()
        self.ui.bDecline.show()

    def zoom_to_position(self, x, y):
        # Center the view on (x, y) and apply zoom using QTransform
        self.ui.gvCamera.centerOn(x, y)
        transform = QTransform()
        transform.scale(self.zoom_level, self.zoom_level)
        self.ui.gvCamera.setTransform(transform)

    def eventFilter(self, obj, event):
        if obj == self.ui.gvCamera.viewport() and event.type() == event.MouseButtonPress:
            pos = event.pos()
            scene_pos = self.ui.gvCamera.mapToScene(pos)
            x, y = scene_pos.x(), scene_pos.y()
            if not hasattr(self, 'marker_workflow_active'):
                self.reset_marker_workflow()
            # Marker placement workflow
            if not self.marker_workflow_active:
                # Place marker for active button
                active_btn = self.active_offset_button
                if active_btn is not None:
                    btn_name = self.button_to_name.get(active_btn)
                    if btn_name:
                        self.markers[btn_name].append((x, y))
                        color_map = {
                            'bXT': Qt.red,
                            'bXB': Qt.blue,
                            'bYL': Qt.green,
                            'bYR': Qt.yellow
                        }
                        marker_color = color_map.get(btn_name, Qt.white)
                        radius = 8
                        # Draw crosshair: two lines intersecting at (x, y)
                        h_line = self.scene.addLine(x-radius, y, x+radius, y, pen=marker_color)
                        v_line = self.scene.addLine(x, y-radius, x, y+radius, pen=marker_color)
                        # Optionally, add a small center dot for visibility
                        dot = self.scene.addEllipse(x-2, y-2, 4, 4, pen=marker_color, brush=marker_color)
                        # Store marker items as a tuple
                        self.current_marker_item = (h_line, v_line, dot)
                        # Immediately zoom 4x on marker position
                        self.zoom_level = 4.0
                        self.zoom_to_position(x, y)
                        self.start_marker_workflow(btn_name, x, y)

                return True
            elif self.marker_workflow_active:
                # Allow unlimited repositioning of marker until Accept/Decline
                self.current_marker = (x, y)
                # Move crosshair and dot to new position
                h_line, v_line, dot = self.current_marker_item
                radius = 8
                h_line.setLine(x-radius, y, x+radius, y)
                v_line.setLine(x, y-radius, x, y+radius)
                dot.setRect(x-2, y-2, 4, 4)
                self.zoom_to_position(x, y)
                return True
            return False
        return super().eventFilter(obj, event)
    """Offset Calibration Window mit Kamera-Feed"""

    def setup_marker_logic(self):
        """Setup marker storage and mouse event for placing markers on the image."""
        # Dictionary to store markers for each button
        self.markers = {
            'bXT': [],
            'bXB': [],
            'bYL': [],
            'bYR': []
        }
        # Map button objects to names
        self.button_to_name = {
            self.ui.bXT: 'bXT',
            self.ui.bXB: 'bXB',
            self.ui.bYL: 'bYL',
            self.ui.bYR: 'bYR'
        }
        # Install event filter on the QGraphicsView
        self.ui.gvCamera.viewport().installEventFilter(self)

    
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
        self.camera = camera.Camera()
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

        # Setup marker logic
        self.setup_marker_logic()

        # --- Offset marker counters and label setup ---
        # Load num_offset_marker from appSettings
        from appSettings import get_calibration_settings
        self.num_offset_marker = get_calibration_settings().get('num_offset_marker', 4)
        # Initialize counters for each label
        self.marker_counters = {
            'lXt': 0,
            'lXb': 0,
            'lYl': 0,
            'lYr': 0
        }
        # Set initial label text
        self.ui.lXt.setText(f"0/{self.num_offset_marker}")
        self.ui.lXb.setText(f"0/{self.num_offset_marker}")
        self.ui.lYl.setText(f"0/{self.num_offset_marker}")
        self.ui.lYr.setText(f"0/{self.num_offset_marker}")
    
    def showEvent(self, event):
        """Override showEvent to ensure buttons are visible"""
        super().showEvent(event)
        print(f"[DEBUG] showEvent called. bSampel checked: {getattr(self.ui.bSampel, 'isChecked', lambda: False)()}")
        if hasattr(self.ui, 'bSampel') and isinstance(self.ui.bSampel, RoundedButton):
            self.ui.bSampel.raise_()
        if hasattr(self.ui, 'bExit') and isinstance(self.ui.bExit, RoundedButton):
            self.ui.bExit.raise_()
        print("[DEBUG] Raised only bSampel and bExit to front")
    
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
            # When Accept is pressed, finalize marker placement and update counter/label
            if self.current_marker_btn:
                label_map = {
                    'bXT': 'lXt',
                    'bXB': 'lXb',
                    'bYL': 'lYl',
                    'bYR': 'lYr'
                }
                label_name = label_map.get(self.current_marker_btn)
                if label_name:
                    self.marker_counters[label_name] += 1
                    label_widget = getattr(self.ui, label_name)
                    label_widget.setText(f"{self.marker_counters[label_name]}/{self.num_offset_marker}")
                    # Update label color: green if enough, else orange
                    if self.marker_counters[label_name] >= self.num_offset_marker:
                        label_widget.setStyleSheet("QLabel { color: green; font-weight: bold; font-size: 16pt; }")
                    else:
                        label_widget.setStyleSheet("QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
            # Reset marker workflow after accepting
            self.reset_marker_workflow()

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
        hardware_settings = appSettings.get_hardware_settings()
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

        # Hide Accept/Decline initially
        self.ui.bAccept.hide()
        self.ui.bDecline.hide()
    
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


        # Show/hide offset buttons depending on sample button state
        print(f"[DEBUG] on_sample_clicked called. bSampel checked: {self.ui.bSampel.isChecked()}")
        if self.ui.bSampel.isChecked():
            print("[DEBUG] Showing offset buttons")
            for btn in self.offset_buttons:
                btn.show()
            # Set bYL as active (checked) and deactivate others
            self.set_active_offset_button(self.ui.bYL)
        else:
            print("[DEBUG] Hiding offset buttons")
            for btn in self.offset_buttons:
                btn.hide()
            print("[LOG] Resume live camera")
            if self.timer and not self.timer.isActive():
                self.timer.start(33)
            # Force one frame update
            self.update_frame()
            return

        # Stoppe Live-Update for freeze/capture
        if self.timer and self.timer.isActive():
            self.timer.stop()

        import appSettings
        if appSettings.is_debug_no_cam():
            test_img_path = '/home/flex/diy/handheld-picam-cnc/pi/test/test1.jpg'
            if not os.path.exists(test_img_path):
                print(f"[ERROR] Test image not found: {test_img_path}")
                return
            frame = cv2.imread(test_img_path)
            if frame is None:
                print(f"[ERROR] Could not load test image: {test_img_path}")
                return
            frames = [frame.astype(np.float32)] * 4
        else:
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
        # Save original image
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sample'))
        os.makedirs(sample_dir, exist_ok=True)
        out_path_orig = os.path.join(sample_dir, 'testimage_original.png')
        cv2.imwrite(out_path_orig, avg)
        print(f"[LOG] Saved original sample to: {out_path_orig}")

        # Apply camera corrections (undistortion only)
        cam_id = self.camera.get_camera_id()
        settings = appSettings.load_app_settings()
        cam_settings = appSettings.get_active_camera_settings()
        geom = cam_settings.get('calibration', {}).get('geometric', {})
        camera_matrix = None
        dist_coeffs = None
        if 'camera_matrix' in geom and 'dist_coeffs' in geom:
            camera_matrix = np.array(geom['camera_matrix'], dtype=np.float64)
            dist_coeffs = np.array(geom['dist_coeffs'], dtype=np.float64).reshape(-1)
        if camera_matrix is not None and dist_coeffs is not None:
            print("[LOG] Applying undistort only (no perspective)")
            undist = rectifyHelper.undistort_image(avg, camera_matrix, dist_coeffs)
            out_path_undist = os.path.join(sample_dir, 'testimage_undistorted.png')
            cv2.imwrite(out_path_undist, undist)
            print(f"[LOG] Saved undistorted sample to: {out_path_undist}")
        else:
            print("[LOG] No geometric calibration found - skipping undistort")
            undist = avg

        # Display the undistorted (or original) image in the scene
        try:
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
        """Accept Button: Speichere Marker und beende Workflow"""
        print("[LOG] Accept Marker")
        # Only increment counter and update label for the last marker placed
        if hasattr(self, 'last_marker_btn_name'):
            label_map = {
                'bXT': 'lXt',
                'bXB': 'lXb',
                'bYL': 'lYl',
                'bYR': 'lYr'
            }
            label_name = label_map.get(self.last_marker_btn_name)
            if label_name:
                self.marker_counters[label_name] += 1
                label_widget = getattr(self.ui, label_name)
                label_widget.setText(f"{self.marker_counters[label_name]}/{self.num_offset_marker}")
                # Update label color: green if enough, else orange
                if self.marker_counters[label_name] >= self.num_offset_marker:
                    label_widget.setStyleSheet("QLabel { color: green; font-weight: bold; font-size: 16pt; }")
                else:
                    label_widget.setStyleSheet("QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
        self.reset_marker_workflow()

    
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
        """Decline Button: Lösche Marker und beende Workflow"""
        print("[LOG] Decline Marker")
        # Remove marker from storage and scene
        if self.current_marker_btn and self.current_marker:
            if self.current_marker in self.markers[self.current_marker_btn]:
                self.markers[self.current_marker_btn].remove(self.current_marker)
        if hasattr(self, 'current_marker_item') and self.current_marker_item:
            # Remove all marker items (crosshair and dot)
            for item in self.current_marker_item:
                self.scene.removeItem(item)
            self.current_marker_item = None
        self.reset_marker_workflow()

