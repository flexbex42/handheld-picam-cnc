#!/usr/bin/env python3
"""
Calibration Offset Window logic
- Camera-to-tool offset calibration UI
- Live camera preview, zoom, offset buttons
- Sample capture (avg of frames), save pre-correction sample
- Checkerboard-based rectification with fallback to tilt/yaw reconstruction
"""

import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QWidget, QGraphicsScene
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

from caliOffsetWin import Ui_Form as Ui_CalibrationOffsetWindow
from caliDevice import load_camera_settings, get_calibration_settings
from camera import Camera
from roundbutton import RoundedButton


class CalibrationOffsetWindow(QWidget):
    """Offset Calibration Window with camera feed and sample capture."""

    def __init__(self, parent=None, on_back_callback=None):
        super().__init__(parent)

        # Callbacks
        self.on_back_callback = on_back_callback

        # Camera
        self.camera = None
        self.camera_id = None
        self.camera_settings = {}
        self.timer = None

        # Zoom
        self.zoom_level = 1.0
        self.zoom_min = 1.0
        self.zoom_max = 4.0
        self.zoom_step = 0.5

        # Offset buttons
        self.offset_buttons = []
        self.active_offset_button = None

        # UI
        self.ui = Ui_CalibrationOffsetWindow()
        self.ui.setupUi(self)

        self.setup_ui()
        self.setup_connections()

        # Initialize camera wrapper
        self.camera = Camera()
        if self.camera.open():
            self.camera_id = self.camera.get_camera_id()
            try:
                self.camera_settings = self.camera.get_camera_settings()
            except Exception:
                self.camera_settings = {}

            # start timer
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(33)
        else:
            print("[ERROR] Failed to open camera")

    def showEvent(self, event):
        super().showEvent(event)
        # Ensure important buttons are on top
        for name in ('bZoomIn', 'bZoomOut', 'bDecline', 'bAccept', 'bXT', 'bXB', 'bYL', 'bYR', 'bSampel'):
            if hasattr(self.ui, name):
                try:
                    getattr(self.ui, name).raise_()
                except Exception:
                    pass

    def setup_ui(self):
        # Graphics scene for camera preview
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        self.ui.gvCamera.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.gvCamera.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.gvCamera.lower()

        # Replace some buttons with RoundedButton while preserving geometry
        try:
            self.ui.bZoomIn = RoundedButton(icon_path=":/icons/plus.png", diameter=56, parent=self, old_button=self.ui.bZoomIn)
            self.ui.bZoomOut = RoundedButton(icon_path=":/icons/minus.png", diameter=56, parent=self, old_button=self.ui.bZoomOut)
            self.ui.bDecline = RoundedButton(icon_path=":/icons/undo.png", diameter=56, parent=self, old_button=self.ui.bDecline)
            self.ui.bAccept = RoundedButton(icon_path=":/icons/ok.png", diameter=56, parent=self, old_button=self.ui.bAccept)

            self.ui.bXT = RoundedButton(icon_path=":/icons/offsetXT.png", diameter=56, parent=self, old_button=self.ui.bXT, active_icon_path=":/icons/offsetXTA.png")
            self.ui.bXB = RoundedButton(icon_path=":/icons/offsetXB.png", diameter=56, parent=self, old_button=self.ui.bXB, active_icon_path=":/icons/offsetXBA.png")
            self.ui.bYL = RoundedButton(icon_path=":/icons/offsetYL.png", diameter=56, parent=self, old_button=self.ui.bYL, active_icon_path=":/icons/offsetYLA.png")
            self.ui.bYR = RoundedButton(icon_path=":/icons/offsetYR.png", diameter=56, parent=self, old_button=self.ui.bYR, active_icon_path=":/icons/offsetYRA.png")

            self.ui.bSampel = RoundedButton(icon_path=":/icons/foto.png", diameter=56, parent=self, old_button=self.ui.bSampel, active_icon_path=":/icons/freeze.png")
        except Exception:
            # If UI doesn't match exactly, ignore — still workable
            pass

        # offset button list
        for name in ('bXT', 'bXB', 'bYL', 'bYR'):
            if hasattr(self.ui, name):
                self.offset_buttons.append(getattr(self.ui, name))

        # set GraphicsView fixed size from settings if available
        try:
            calib_settings = get_calibration_settings()
            screen = calib_settings.get('screen_size', { 'width': 640, 'height': 480 })
            self.ui.gvCamera.setFixedSize(screen.get('width', 640), screen.get('height', 480))
        except Exception:
            pass

    def setup_connections(self):
        # connect basic buttons if they exist
        if hasattr(self.ui, 'bExit'):
            self.ui.bExit.clicked.connect(self.on_exit_clicked)
        if hasattr(self.ui, 'bZoomIn'):
            self.ui.bZoomIn.clicked.connect(self.on_zoom_in_clicked)
        if hasattr(self.ui, 'bZoomOut'):
            self.ui.bZoomOut.clicked.connect(self.on_zoom_out_clicked)
        if hasattr(self.ui, 'bAccept'):
            self.ui.bAccept.clicked.connect(self.on_accept_clicked)
        if hasattr(self.ui, 'bDecline'):
            self.ui.bDecline.clicked.connect(self.on_decline_clicked)

        # offset buttons
        if hasattr(self.ui, 'bXT'):
            self.ui.bXT.clicked.connect(self.on_xt_clicked)
        if hasattr(self.ui, 'bXB'):
            self.ui.bXB.clicked.connect(self.on_xb_clicked)
        if hasattr(self.ui, 'bYL'):
            self.ui.bYL.clicked.connect(self.on_yl_clicked)
        if hasattr(self.ui, 'bYR'):
            self.ui.bYR.clicked.connect(self.on_yr_clicked)

        # sample button
        if hasattr(self.ui, 'bSampel'):
            self.ui.bSampel.clicked.connect(self.on_sample_clicked)

    def update_frame(self):
        if self.camera is None or not self.camera.is_opened():
            return
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # apply zoom
        if self.zoom_level > 1.0:
            h, w = frame_rgb.shape[:2]
            crop_h = int(h / self.zoom_level)
            crop_w = int(w / self.zoom_level)
            start_y = (h - crop_h) // 2
            start_x = (w - crop_w) // 2
            frame_rgb = frame_rgb[start_y:start_y+crop_h, start_x:start_x+crop_w]

        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(self.ui.gvCamera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.scene.clear()
        self.scene.addPixmap(scaled)

    def on_sample_clicked(self):
        """Capture 4 frames, average, save pre-correction and apply rectification"""
        # resume if toggle released
        try:
            if not getattr(self.ui, 'bSampel').isChecked():
                if self.timer and not self.timer.isActive():
                    self.timer.start(33)
                self.update_frame()
                return
        except Exception:
            # if button missing or not checkable, proceed to capture once
            pass

        if self.timer and self.timer.isActive():
            self.timer.stop()

        if self.camera is None or not self.camera.is_opened():
            print("[ERROR] Camera not opened - cannot take samples")
            return

        frames = []
        for i in range(4):
            ret, frame = self.camera.read()
            if not ret or frame is None:
                continue
            frames.append(frame.astype(np.float32))

        if len(frames) == 0:
            print("[ERROR] No frames captured")
            return

        avg = np.mean(frames, axis=0).astype(np.uint8)

        # save pre-correction sample
        try:
            sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sample'))
            os.makedirs(sample_dir, exist_ok=True)
            sample_path = os.path.join(sample_dir, 'testimage.png')
            cv2.imwrite(sample_path, avg)
            print(f"[LOG] Saved pre-correction sample to: {sample_path}")
        except Exception as e:
            print(f"[WARN] Failed to save pre-correction sample: {e}")

        # undistort if geometric calibration exists
        camera_matrix = None
        dist_coeffs = None
        cam_settings = {}
        try:
            cam_id = self.camera.get_camera_id()
            settings = load_camera_settings()
            cam_settings = settings.get(cam_id, {})
            geom = cam_settings.get('calibration', {}).get('geometric', {})
            if 'camera_matrix' in geom and 'dist_coeffs' in geom:
                camera_matrix = np.array(geom['camera_matrix'], dtype=np.float64)
                dist_coeffs = np.array(geom['dist_coeffs'], dtype=np.float64).reshape(-1)
        except Exception:
            pass

        if camera_matrix is not None and dist_coeffs is not None:
            try:
                undist = cv2.undistort(avg, camera_matrix, dist_coeffs)
            except Exception:
                undist = avg
        else:
            undist = avg

        # Try checkerboard homography rectification first
        try:
            calib = get_calibration_settings()
            boxes = calib.get('checkerboard_boxes', {'x': 11, 'y': 8})
            pattern = (boxes.get('x', 11) - 1, boxes.get('y', 8) - 1)

            gray = cv2.cvtColor(undist, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, pattern,
                                                      flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
            if found and corners is not None:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                pts = corners2.reshape(-1, 2)
                x_min, y_min = pts.min(axis=0)
                x_max, y_max = pts.max(axis=0)
                cols = pattern[0]
                rows = pattern[1]
                xs = np.linspace(x_min, x_max, cols)
                ys = np.linspace(y_min, y_max, rows)
                target = np.array([[x, y] for y in ys for x in xs], dtype=np.float32)
                src = pts.astype(np.float32)
                H, mask = cv2.findHomography(src, target, method=0)
                if H is not None:
                    h, w = undist.shape[:2]
                    # apply stored translate if present
                    pers = cam_settings.get('calibration', {}).get('perspective', {})
                    tx = int(pers.get('translate_x', 0)) if pers else 0
                    ty = int(pers.get('translate_y', 0)) if pers else 0

                    if tx != 0 or ty != 0:
                        dst_max = np.array([[x_max, y_max]])
                        new_w = int(np.ceil(max(w, x_max + tx + 10)))
                        new_h = int(np.ceil(max(h, y_max + ty + 10)))
                        T = np.array([[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]], dtype=np.float64)
                        H_t = T @ H
                        undist = cv2.warpPerspective(undist, H_t, (new_w, new_h), flags=cv2.INTER_LINEAR)
                    else:
                        undist = cv2.warpPerspective(undist, H, (w, h), flags=cv2.INTER_LINEAR)
                else:
                    print('[WARN] Checkerboard homography failed')
            else:
                # fallback below
                pass
        except Exception as e:
            print(f"[WARN] Checkerboard detection failed: {e}")

        # If checkerboard path didn't change image strongly, try perspective params fallback
        try:
            # fallback: use stored perspective tilt/yaw if available
            pers = cam_settings.get('calibration', {}).get('perspective', {})
            tilt_deg = pers.get('tilt_deg')
            yaw_deg = pers.get('yaw_deg')
            if tilt_deg is not None and yaw_deg is not None and camera_matrix is not None:
                tilt_rad = np.deg2rad(tilt_deg)
                yaw_rad = np.deg2rad(yaw_deg)
                c_t = np.cos(tilt_rad)
                s_t = np.sin(tilt_rad)
                c_y = np.cos(yaw_rad)
                s_y = np.sin(yaw_rad)
                col0 = np.array([c_t * c_y, c_t * s_y, -s_t], dtype=np.float64)
                cand_col1_a = np.array([-s_y, c_y, 0.0], dtype=np.float64)
                cand_col1_b = np.array([s_y, -c_y, 0.0], dtype=np.float64)

                def build_R(col1):
                    col1n = col1 / (np.linalg.norm(col1) + 1e-12)
                    col2 = np.cross(col0, col1n)
                    R = np.column_stack((col0, col1n, col2))
                    U, _, Vt = np.linalg.svd(R)
                    return U @ Vt

                R_a = build_R(cand_col1_a)
                R_b = build_R(cand_col1_b)
                z_a = np.arctan2(R_a[1, 0], R_a[0, 0])
                z_b = np.arctan2(R_b[1, 0], R_b[0, 0])
                R_recon = R_a if abs(z_a) <= abs(z_b) else R_b

                h, w = undist.shape[:2]
                fx = camera_matrix[0, 0]
                fy = camera_matrix[1, 1]
                cx = camera_matrix[0, 2]
                cy = camera_matrix[1, 2]

                src_corners = np.array([[0.0, 0.0], [w - 1.0, 0.0], [w - 1.0, h - 1.0], [0.0, h - 1.0]], dtype=np.float32)
                dst_corners = []
                R_inv = R_recon.T
                for (u, v) in src_corners:
                    x = (u - cx) / fx
                    y = (v - cy) / fy
                    vec = np.array([x, y, 1.0], dtype=np.float64)
                    vec_rot = R_inv @ vec
                    if abs(vec_rot[2]) < 1e-9:
                        u2 = cx
                        v2 = cy
                    else:
                        u2 = fx * (vec_rot[0] / vec_rot[2]) + cx
                        v2 = fy * (vec_rot[1] / vec_rot[2]) + cy
                    dst_corners.append([u2, v2])
                dst_corners = np.array(dst_corners, dtype=np.float32)
                H = cv2.getPerspectiveTransform(src_corners, dst_corners)
                # apply stored translate if present
                pers = cam_settings.get('calibration', {}).get('perspective', {})
                tx = int(pers.get('translate_x', 0)) if pers else 0
                ty = int(pers.get('translate_y', 0)) if pers else 0

                if tx != 0 or ty != 0:
                    # compute bounding box of dst_corners to size canvas
                    max_xy = dst_corners.max(axis=0)
                    max_x, max_y = float(max_xy[0]), float(max_xy[1])
                    new_w = int(np.ceil(max(w, max_x + tx + 10)))
                    new_h = int(np.ceil(max(h, max_y + ty + 10)))
                    T = np.array([[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]], dtype=np.float64)
                    H_t = T @ H
                    undist = cv2.warpPerspective(undist, H_t, (new_w, new_h), flags=cv2.INTER_LINEAR)
                else:
                    undist = cv2.warpPerspective(undist, H, (w, h), flags=cv2.INTER_LINEAR)

                # simple 180deg flip detection
                try:
                    pts = np.array([[[cx, cy], [cx, cy - 10], [cx + 10, cy]]], dtype=np.float32)
                    mapped = cv2.perspectiveTransform(pts, H)[0]
                    mc = mapped[0]
                    mup = mapped[1]
                    mright = mapped[2]
                    dy_up = mup[1] - mc[1]
                    dx_right = mright[0] - mc[0]
                    invert_y = (dy_up > 5)
                    invert_x = (dx_right < -5)
                    if invert_x and invert_y:
                        undist = cv2.rotate(undist, cv2.ROTATE_180)
                except Exception:
                    pass
        except Exception:
            # no perspective fallback
            pass

        # show processed image in view
        try:
            # save rectified output (with applied translate if any) for later inspection/tools
            try:
                sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sample'))
                os.makedirs(sample_dir, exist_ok=True)
                out_path = os.path.join(sample_dir, 'testimage_rectified.png')
                cv2.imwrite(out_path, undist)
                print(f"[LOG] Saved rectified sample to: {out_path}")
            except Exception as _e:
                print(f"[WARN] Could not save rectified sample: {_e}")

            frame_rgb = cv2.cvtColor(undist, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            scaled = pixmap.scaled(self.ui.gvCamera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.scene.clear()
            self.scene.addPixmap(scaled)
        except Exception as e:
            print(f"[ERROR] Failed to display processed image: {e}")

    def on_exit_clicked(self):
        # stop
        if self.timer:
            self.timer.stop()
        if self.camera:
            self.camera.release()
        if self.on_back_callback:
            self.on_back_callback()
        self.close()

    def on_zoom_in_clicked(self):
        if self.zoom_level < self.zoom_max:
            self.zoom_level += self.zoom_step

    def on_zoom_out_clicked(self):
        if self.zoom_level > self.zoom_min:
            self.zoom_level -= self.zoom_step

    def on_accept_clicked(self):
        # placeholder for saving offsets
        pass

    def set_active_offset_button(self, button):
        for btn in self.offset_buttons:
            if btn == button:
                btn.setChecked(True)
                self.active_offset_button = btn
            else:
                btn.setChecked(False)

    def on_xt_clicked(self):
        self.set_active_offset_button(getattr(self.ui, 'bXT', None))

    def on_xb_clicked(self):
        self.set_active_offset_button(getattr(self.ui, 'bXB', None))

    def on_yr_clicked(self):
        self.set_active_offset_button(getattr(self.ui, 'bYR', None))

    def on_yl_clicked(self):
        self.set_active_offset_button(getattr(self.ui, 'bYL', None))
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
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from caliOffsetWin import Ui_Form as Ui_CalibrationOffsetWindow
from caliDevice import load_camera_settings, get_camera_id, get_calibration_settings
from camera import Camera
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
        calib_settings = get_calibration_settings()
        screen_size = calib_settings.get("screen_size", {"width": 640, "height": 480})
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

        # Apply camera corrections from settings (undistort) if available
        try:
            from caliDevice import load_camera_settings
            cam_id = self.camera.get_camera_id()
            settings = load_camera_settings()
            cam_settings = settings.get(cam_id, {})
            geom = cam_settings.get('calibration', {}).get('geometric', {})
            camera_matrix = None
            dist_coeffs = None
            if 'camera_matrix' in geom and 'dist_coeffs' in geom:
                camera_matrix = np.array(geom['camera_matrix'], dtype=np.float64)
                dist_coeffs = np.array(geom['dist_coeffs'], dtype=np.float64).reshape(-1)

            if camera_matrix is not None and dist_coeffs is not None:
                print("[LOG] Applying undistort with saved calibration")
                undist = cv2.undistort(avg, camera_matrix, dist_coeffs)
            else:
                print("[LOG] No geometric calibration found - skipping undistort")
                undist = avg
        except Exception as e:
            print(f"[ERROR] Exception while applying calibration: {e}")
            undist = avg

        # Apply perspective correction (tilt / yaw) if available in settings
        try:
            pers = cam_settings.get('calibration', {}).get('perspective', {})
            tilt_deg = pers.get('tilt_deg')
            yaw_deg = pers.get('yaw_deg')
            scale_mm_per_pixel = pers.get('scale_mm_per_pixel')

            # Only apply if tilt/yaw present and we have camera_matrix
            if tilt_deg is not None and yaw_deg is not None and camera_matrix is not None:
                print(f"[LOG] Applying perspective correction: tilt={tilt_deg:.2f}°, yaw={yaw_deg:.2f}°")
                # Reconstruct rotation matrix consistent with caliPerspective extraction.
                # caliPerspective computes:
                #   tilt_rad = asin(-rmat[2,0])
                #   yaw_rad = atan2(rmat[1,0], rmat[0,0])
                # We want to construct a rotation matrix containing only tilt (X) and
                # yaw (Y) components and explicitly ignore any Z-rotation.
                tilt_rad = np.deg2rad(tilt_deg)
                yaw_rad = np.deg2rad(yaw_deg)

                c_t = np.cos(tilt_rad)
                s_t = np.sin(tilt_rad)
                c_y = np.cos(yaw_rad)
                s_y = np.sin(yaw_rad)

                # First column derived from caliPerspective convention
                col0 = np.array([c_t * c_y, c_t * s_y, -s_t], dtype=np.float64)

                # Candidate second columns (two reasonable, orthogonal choices in XY plane)
                cand_col1_a = np.array([-s_y, c_y, 0.0], dtype=np.float64)
                cand_col1_b = np.array([s_y, -c_y, 0.0], dtype=np.float64)

                # Build two candidate rotation matrices (no Z-rotation) and pick the one
                # whose implied Z-rotation is smaller (this avoids accidental 180deg flips).
                def build_R(col1):
                    col1n = col1 / (np.linalg.norm(col1) + 1e-12)
                    col2 = np.cross(col0, col1n)
                    R = np.column_stack((col0, col1n, col2))
                    # Orthonormalize via SVD to be numerically stable
                    U, _, Vt = np.linalg.svd(R)
                    R_ortho = U @ Vt
                    return R_ortho

                R_a = build_R(cand_col1_a)
                R_b = build_R(cand_col1_b)

                # Estimate residual Z-rotation angle for each candidate: atan2(r21, r11)
                z_a = np.arctan2(R_a[1, 0], R_a[0, 0])
                z_b = np.arctan2(R_b[1, 0], R_b[0, 0])

                # Pick candidate with smaller absolute z-rotation (we want to ignore Z)
                R_recon = R_a if abs(z_a) <= abs(z_b) else R_b

                h, w = undist.shape[:2]
                fx = camera_matrix[0, 0]
                fy = camera_matrix[1, 1]
                cx = camera_matrix[0, 2]
                cy = camera_matrix[1, 2]

                # Map image corners through the inverse rotation (transpose) to compute destination quad
                src_corners = np.array([[0.0, 0.0], [w - 1.0, 0.0], [w - 1.0, h - 1.0], [0.0, h - 1.0]], dtype=np.float32)
                dst_corners = []
                R_inv = R_recon.T
                for (u, v) in src_corners:
                    x = (u - cx) / fx
                    y = (v - cy) / fy
                    vec = np.array([x, y, 1.0], dtype=np.float64)
                    vec_rot = R_inv @ vec
                    # project back
                    if abs(vec_rot[2]) < 1e-9:
                        u2 = cx
                        v2 = cy
                    else:
                        u2 = fx * (vec_rot[0] / vec_rot[2]) + cx
                        v2 = fy * (vec_rot[1] / vec_rot[2]) + cy
                    dst_corners.append([u2, v2])

                dst_corners = np.array(dst_corners, dtype=np.float32)

                # Compute homography that maps original image to the rectified view
                H = cv2.getPerspectiveTransform(src_corners, dst_corners)
                # Warp using same output size
                undist = cv2.warpPerspective(undist, H, (w, h), flags=cv2.INTER_LINEAR)
            else:
                print("[LOG] No perspective calibration or camera matrix found - skipping perspective correction")
        except Exception as e:
            print(f"[ERROR] Exception while applying perspective correction: {e}")
            # keep undist as-is

        # Convert to QPixmap and show in scene (replace live feed)
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

