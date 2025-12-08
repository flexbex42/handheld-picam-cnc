#!/usr/bin/env python3
"""
Calibration Perspective Window Logik
- Kalibrierung der Perspektive (Tilt, Yaw, Scale)
- Auto-Capture: 15 Bilder ohne manuelle Klicks
- Verwendet Distortion-Koeffizienten zur Entzerrung
- Berechnet: Tilt (Grad), Yaw (Grad), Scale (mm/pixel)
"""

import os
import cv2
import numpy as np
from rectificationHelper import find_checkerboard_corners, undistort_image, compute_perspective_from_samples
import json
import time
import icons_rc  # Qt Resource File für Icons
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication, QDialog
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from caliPerspectiveWin import Ui_Form as Ui_CalibrationPerspectiveWindow
from caliDialog import Ui_CalibrationDialog
from appSettings import load_camera_settings, save_camera_settings, get_calibration_settings, get_selected_camera, get_hardware_settings
import camera




class ProcessingThread(QThread):
    """Hintergrund-Thread für Foto-Verarbeitung"""
    progress_updated = pyqtSignal(str)  # Text für Progress-Label
    processing_complete = pyqtSignal(bool, float, float, float, int)  # success, tilt_deg, yaw_deg, scale_mm_per_pixel, successful_count
    
    def __init__(self, sample_dir, max_samples, checkerboard_sizes, detected_size, square_size, camera_matrix, dist_coeffs):
        super().__init__()
        self.sample_dir = sample_dir
        self.max_samples = max_samples
        self.checkerboard_sizes = checkerboard_sizes
        self.detected_checkerboard_size = detected_size
        self.square_size = square_size  # in mm
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        
    def run(self):
        """Verarbeite Fotos im Hintergrund (refactored to use rectificationHelper)."""
        try:
            self.progress_updated.emit("Processing perspective calibration samples...")
            result = compute_perspective_from_samples(
                self.sample_dir,
                self.max_samples,
                self.checkerboard_sizes,
                self.detected_checkerboard_size,
                self.square_size,
                self.camera_matrix,
                self.dist_coeffs
            )
            success, tilt_deg, yaw_deg, scale_mm_per_pixel, successful_count = result
            if not success:
                self.processing_complete.emit(False, 0, 0, 0, successful_count)
                return
            self.processing_complete.emit(True, tilt_deg, yaw_deg, scale_mm_per_pixel, successful_count)
        except Exception as e:
            print(f"[ERROR] Exception in processing thread: {e}")
            import traceback
            traceback.print_exc()
            self.processing_complete.emit(False, 0, 0, 0, 0)


class CalibrationPerspectiveWindow(QWidget):
    """Calibration Perspective Window"""
    on_exit_callback = None
    on_perspective_complete_callback = None
    
    def __init__(self):
        super().__init__()
        self.ui = Ui_CalibrationPerspectiveWindow()
        self.ui.setupUi(self)
        
        # Kamera-Variablen
        self.cap = None
        self.timer = QTimer()
        self.scene = QGraphicsScene()
        
        # Kalibrierungs-Variablen
        self.sample_count = 0
        self.max_samples = 15
        # sample directory should be relative to the pi package so it works on
        # laptop and Raspberry Pi setups. Use pi/sample next to this file.
        self.sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sample'))
        self.detected_checkerboard_size = None  # Automatisch erkannte Größe
        self.square_size = 5  # Default: 5mm, wird aus Config gelesen
        
        # Distortion-Koeffizienten
        self.camera_matrix = None
        self.dist_coeffs = None
        
        # Processing Thread
        self.processing_thread = None
        
        # CalibrationDialog
        self.calibration_dialog = None
        
        # Auto-Capture Variablen
        self.auto_capture_active = False
        self.auto_capture_timer = QTimer()
        self.auto_capture_interval = 500  # ms zwischen Captures
        
        self.setup_ui()
        self.setup_connections()
        
        # Checkerboard-Konfiguration laden
        calib_settings = get_calibration_settings()
        if calib_settings:
            self.square_size = calib_settings.get("checkerboard_dim", {}).get("size_mm", 5)
            boxes = calib_settings.get("checkerboard_boxes", {})
            boxes_x = boxes.get("x", 11)
            boxes_y = boxes.get("y", 8)
            # Verwende nur die konfigurierte Größe aus Settings
            self.checkerboard_sizes = [(boxes_x - 1, boxes_y - 1)]
            print(f"[INFO] Perspective calibration using checkerboard from settings:")
            print(f"  Boxes: {boxes_x}x{boxes_y} ({boxes_x-1}x{boxes_y-1} inner corners)")
            print(f"  Square size: {self.square_size}mm")
        else:
            # Fallback wenn keine Settings vorhanden
            print("[WARNING] No calibration settings found, using defaults: 11x8 boxes, 5mm squares")
            self.square_size = 5
            self.checkerboard_sizes = [(10, 7)]  # Default 11x8 boxes
        
        # Lade Distortion-Koeffizienten
        self.load_distortion_coefficients()
        
        # Initialisiere Kamera
        self.init_camera()
        
    
    def load_distortion_coefficients(self):
        """Lade Distortion-Koeffizienten aus JSON"""
        # Prefer using the central Camera helper (same logic as caliDistortion)
        try:
            cam = Camera()
            if cam.open():
                cam_id = cam.get_camera_id()
                cam_settings = cam.get_camera_settings() or {}
                # Camera._apply_settings already printed init info
                geom = cam_settings.get('calibration', {}).get('geometric', {})
                camera_matrix_list = geom.get('camera_matrix')
                dist_coeffs_list = geom.get('dist_coeffs')

                if camera_matrix_list is not None and dist_coeffs_list is not None:
                    self.camera_matrix = np.array(camera_matrix_list)
                    self.dist_coeffs = np.array(dist_coeffs_list)
                    print(f"[INFO] Loaded distortion coefficients from Camera wrapper for {cam_id}")
                    print(f"  Camera matrix: {self.camera_matrix}")
                    print(f"  Dist coeffs: {self.dist_coeffs}")
                    return True
                else:
                    print(f"[WARNING] Camera wrapper opened {cam_id} but no geometric calibration found in settings")
            else:
                print("[WARNING] Camera wrapper could not open a camera, falling back to settings scan")
        except Exception as e:
            print(f"[WARN] Camera wrapper failed: {e}")

        # Fallback: Lade direkt aus saved settings (legacy behavior)
        saved_settings = load_camera_settings()
        # Prefer selected_camera from settings file
        camera_id = saved_settings.get('selected_camera')
        if not camera_id:
            # scan /dev/video* for a matching camera id in settings
            for i in list_video_devices():
                cam_id = get_camera_id(i)
                if cam_id in saved_settings:
                    camera_id = cam_id
                    break

        if not camera_id:
            print("[ERROR] No camera ID found in settings")
            return False

        settings = saved_settings.get(camera_id, {})
        if not settings:
            print("[ERROR] No camera settings found for camera_id")
            return False

        calibration = settings.get("calibration", {})
        geometric = calibration.get("geometric", {})

        camera_matrix_list = geometric.get("camera_matrix")
        dist_coeffs_list = geometric.get("dist_coeffs")

        if not camera_matrix_list or not dist_coeffs_list:
            print("[ERROR] No distortion coefficients found in settings")
            return False

        self.camera_matrix = np.array(camera_matrix_list)
        self.dist_coeffs = np.array(dist_coeffs_list)

        print(f"[INFO] Loaded distortion coefficients from settings for {camera_id}")
        print(f"  Camera matrix: {self.camera_matrix}")
        print(f"  Dist coeffs: {self.dist_coeffs}")

        return True
    
    def cleanup(self):
        """Cleanup resources"""
        if self.timer.isActive():
            self.timer.stop()
        if self.auto_capture_timer.isActive():
            self.auto_capture_timer.stop()
        self.cleanup_camera()
    
    def setup_ui(self):
        """UI initialisieren"""
        self.ui.gvCamera.setScene(self.scene)
        self.ui.lSamples.setText(f"{self.sample_count}/{self.max_samples}")
    

    
    def setup_connections(self):
        """Signal-Verbindungen einrichten"""
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bStart.clicked.connect(self.on_start_clicked)
        self.timer.timeout.connect(self.update_frame)
        self.auto_capture_timer.timeout.connect(self.on_auto_capture_tick)
    
    def init_camera(self):
        """Initialisiere Kamera"""
        # Lade Kamera-Settings
        saved_settings = load_camera_settings()

        # Prüfe ob eine Kamera ausgewählt wurde
        selected_index, selected_id = get_selected_camera()

        camera_id = None
        device_index = None

        if selected_index is not None and selected_id is not None:
            # Nutze ausgewählte Kamera
            print(f"[LOG] Using selected camera: index={selected_index}, id={selected_id}")
            camera_id = selected_id
            device_index = selected_index
        else:
            # Fallback: Finde erste angeschlossene Kamera mit Settings
            print("[LOG] No camera selected, using first available camera with settings")
            for i in list_video_devices():
                cam_id = get_camera_id(i)
                if cam_id in saved_settings:
                    camera_id = cam_id
                    device_index = i
                    break

        if not camera_id or device_index is None:
            print("[ERROR] No camera found")
            return

        settings = saved_settings.get(camera_id, {})
        if not settings:
            print("[ERROR] No camera settings found")
            return

        # Öffne Kamera über Camera-Klasse
        self.camera = Camera()
        if not self.camera.open():
            print(f"[ERROR] Failed to open camera: /dev/video{device_index}")
            return
        print(f"[INFO] Camera opened: /dev/video{device_index}")
        # Starte Timer für Frame-Updates
        self.timer.start(33)  # ~30 FPS
    
    def update_frame(self):
        """Update camera frame"""
        if not self.camera or not hasattr(self.camera, 'read'):
            return
        ret, frame = self.camera.read()
        if not ret:
            return
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.scene.clear()
        self.scene.addPixmap(pixmap)
        self.ui.gvCamera.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def on_start_clicked(self):
        """bStart: Starte Auto-Capture"""
        if self.auto_capture_active:
            print("[LOG] Auto-capture already active")
            return
        
        if not self.camera or not hasattr(self.camera, 'read'):
            print("[ERROR] Camera not available")
            return
        os.makedirs(self.sample_dir, exist_ok=True)
        for i in range(1, self.max_samples + 1):
            filepath = os.path.join(self.sample_dir, f"sample_{i:02d}.jpg")
            if os.path.exists(filepath):
                os.remove(filepath)
        self.sample_count = 0
        self.ui.lSamples.setText(f"{self.sample_count}/{self.max_samples}")
        self.ui.bStart.setEnabled(False)
        self.auto_capture_active = True
        self.auto_capture_timer.start(self.auto_capture_interval)
        print("[LOG] Auto-capture started")
    
    def on_auto_capture_tick(self):
        """Auto-Capture Tick: Nehme nächstes Foto"""
        if self.sample_count >= self.max_samples:
            # Alle Samples gesammelt
            self.auto_capture_timer.stop()
            self.auto_capture_active = False
            print("[LOG] Auto-capture complete")
            
            # Starte Processing
            self.start_processing_thread()
            return
        
        # Nehme Foto
        if not self.camera or not hasattr(self.camera, 'read'):
            print("[ERROR] Camera not available")
            self.auto_capture_timer.stop()
            self.auto_capture_active = False
            return
        ret, frame = self.camera.read()
        if not ret:
            print("[ERROR] Failed to capture frame")
            return
        self.sample_count += 1
        filename = f"sample_{self.sample_count:02d}.jpg"
        filepath = os.path.join(self.sample_dir, filename)
        cv2.imwrite(filepath, frame)
        print(f"[LOG] Captured {filename}")
        self.ui.lSamples.setText(f"{self.sample_count}/{self.max_samples}")
    
    def on_processing_progress(self, message):
        """Processing Progress Update"""
        if self.calibration_dialog:
            self.calibration_dialog.dialog_ui.lProgress.setText(message)
    
    def on_processing_complete(self, success, tilt_deg, yaw_deg, scale_mm_per_pixel, successful_count):
        """Processing Complete"""
        print(f"\n[LOG] ===== Processing Complete =====")
        print(f"[INFO] Success: {success}")
        
        if not self.calibration_dialog:
            print("[WARNING] Dialog not available")
            return
        
        if success:
            # Speichere Ergebnisse
            # Lade Kamera-Settings
            saved_settings = load_camera_settings()

            # Prefer the explicitly selected camera in settings (selected_camera)
            # This avoids scanning /dev/video* and ensures we operate on the
            # currently active camera chosen in the Settings UI.
            camera_id = saved_settings.get('selected_camera')

            # Fallback for legacy setups: scan /dev/video* for a camera that has settings
            if not camera_id:
                for i in list_video_devices():
                    cam_id = get_camera_id(i)
                    if cam_id in saved_settings:
                        camera_id = cam_id
                        break
            
            if camera_id:
                # Stelle sicher dass Calibration-Dict existiert
                if "calibration" not in saved_settings[camera_id]:
                    saved_settings[camera_id]["calibration"] = {}
                
                # Speichere Perspective-Daten
                # store tilt as negated and yaw shifted by +180° per new convention
                stored_tilt = float(-tilt_deg)
                stored_yaw = float(yaw_deg + 180.0)
                print(f"[DEBUG] Perspective save: raw tilt={tilt_deg:.2f}°, yaw={yaw_deg:.2f}° → stored tilt={stored_tilt:.2f}°, yaw={stored_yaw:.2f}°")

                # Determine image size: try camera resolution, then global calibration screen size, fallback to 640x480
                res_str = saved_settings.get(camera_id, {}).get('resolution')
                if res_str and isinstance(res_str, str) and 'x' in res_str:
                    try:
                        w_str, h_str = res_str.split('x')
                        w_img = int(w_str)
                        h_img = int(h_str)
                    except Exception:
                        w_img, h_img = 640, 480
                else:
                    screen = saved_settings.get('hardware_setting', {}).get('screen_size', {})
                    w_img = int(screen.get('width', 640))
                    h_img = int(screen.get('height', 480))

                # Get camera_matrix (use geometric if available, else self.camera_matrix)
                cam_geom = saved_settings.get(camera_id, {}).get('calibration', {}).get('geometric', {})
                cam_mat = None
                if cam_geom and cam_geom.get('camera_matrix'):
                    cam_mat = np.array(cam_geom.get('camera_matrix'), dtype=np.float64)
                elif self.camera_matrix is not None:
                    cam_mat = np.array(self.camera_matrix, dtype=np.float64)
                
                print(f"[DEBUG] Camera matrix for translate calc: {'LOADED' if cam_mat is not None else 'MISSING'}")
                if cam_mat is not None:
                    print(f"[DEBUG] Camera matrix fx={cam_mat[0,0]:.2f}, fy={cam_mat[1,1]:.2f}, cx={cam_mat[0,2]:.2f}, cy={cam_mat[1,2]:.2f}")

                translate_x = 0
                translate_y = 0
                pad = 20

                # Compute minimal translation to make projected corners visible
                try:
                    if cam_mat is not None:
                        # Build rotation from stored tilt/yaw (use same convention as rectify)
                        def build_rotation(tilt_d, yaw_d):
                            tr = np.deg2rad(tilt_d)
                            yr = np.deg2rad(yaw_d)
                            ct = np.cos(tr)
                            st = np.sin(tr)
                            cy = np.cos(yr)
                            sy = np.sin(yr)
                            col0 = np.array([ct * cy, ct * sy, -st], dtype=np.float64)
                            cand_col1_a = np.array([-sy, cy, 0.0], dtype=np.float64)
                            cand_col1_b = np.array([sy, -cy, 0.0], dtype=np.float64)

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
                            chosen = R_a if abs(z_a) <= abs(z_b) else R_b
                            return chosen

                        R_recon = build_rotation(stored_tilt, stored_yaw)

                        fx = cam_mat[0, 0]
                        fy = cam_mat[1, 1]
                        cx = cam_mat[0, 2]
                        cy = cam_mat[1, 2]

                        src_corners = np.array([[0.0, 0.0], [w_img - 1.0, 0.0], [w_img - 1.0, h_img - 1.0], [0.0, h_img - 1.0]], dtype=np.float64)
                        dst = []
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
                            dst.append([u2, v2])
                        dst = np.array(dst, dtype=np.float64)
                        min_xy = dst.min(axis=0)
                        min_x, min_y = min_xy[0], min_xy[1]

                        off_x = int(max(0, -np.floor(min_x)) + pad)
                        off_y = int(max(0, -np.floor(min_y)) + pad)
                        translate_x = off_x
                        translate_y = off_y
                        print(f"[DEBUG] Computed translate from perspective: min_x={min_x:.2f}, min_y={min_y:.2f}, translate_x={translate_x}, translate_y={translate_y}")
                        print(f"[DEBUG] Used stored_tilt={stored_tilt:.2f}, stored_yaw={stored_yaw:.2f} for translate calculation")
                except Exception as e:
                    print(f"[WARNING] Failed to compute translate_x/translate_y automatically: {e}")
                    import traceback
                    traceback.print_exc()

                saved_settings[camera_id]["calibration"]["perspective"] = {
                    "tilt_deg": stored_tilt,
                    "yaw_deg": stored_yaw,
                    "scale_mm_per_pixel": float(scale_mm_per_pixel),
                    "successful_images": successful_count,
                    "translate_x": int(translate_x),
                    "translate_y": int(translate_y)
                }

                # Speichere zu Datei
                save_camera_settings(saved_settings)
                print(f"[SUCCESS] Perspective calibration saved")
            
            # Update Dialog
            self.calibration_dialog.dialog_ui.lTitle.setText("Perspective Calibration Complete")
            result_text = f"Calibration successful!\n\n"
            result_text += f"Tilt: {tilt_deg:.2f}°\n"
            result_text += f"Yaw: {yaw_deg:.2f}°\n"
            result_text += f"Scale: {scale_mm_per_pixel:.4f} mm/px"
            self.calibration_dialog.dialog_ui.lProgress.setText(result_text)
            self.calibration_dialog.dialog_ui.bAccept.setEnabled(True)
        else:
            # Fehler - Accept-Button bleibt deaktiviert
            self.calibration_dialog.dialog_ui.lTitle.setText("Perspective Calibration Failed")
            error_text = f"Calibration failed!\n\n"
            error_text += f"Not enough successful images.\n"
            error_text += f"Images found: {successful_count}/{self.max_samples}\n\n"
            error_text += "Please ensure:\n"
            error_text += "- Checkerboard is clearly visible\n"
            error_text += "- Checkerboard is stationary\n"
            error_text += "- Good lighting conditions"
            self.calibration_dialog.dialog_ui.lProgress.setText(error_text)
            # Accept-Button bleibt deaktiviert bei Fehler
            self.calibration_dialog.dialog_ui.bAccept.setEnabled(False)
    
    def show_processing_dialog(self):
        """Zeige CalibrationDialog"""
        self.calibration_dialog = QDialog(self)
        self.calibration_dialog.setWindowFlags(Qt.FramelessWindowHint)
        self.calibration_dialog.dialog_ui = Ui_CalibrationDialog()
        self.calibration_dialog.dialog_ui.setupUi(self.calibration_dialog)
        
        # Setze feste Größe des Dialogs
        dialog_width = 400
        dialog_height = 350
        self.calibration_dialog.setFixedSize(dialog_width, dialog_height)
        
        # Positioniere Dialog in der Mitte
        x = (640 - dialog_width) // 2
        y = (480 - dialog_height) // 2
        self.calibration_dialog.move(x, y)
        
        # Initial Text
        self.calibration_dialog.dialog_ui.lTitle.setText("Processing Perspective Calibration")
        self.calibration_dialog.dialog_ui.lProgress.setText("Starting processing...")
        
        # Buttons initial deaktiviert
        self.calibration_dialog.dialog_ui.bAccept.setEnabled(False)
        
        # Button Connections
        self.calibration_dialog.dialog_ui.bAccept.clicked.connect(self.on_accept_clicked)
        self.calibration_dialog.dialog_ui.bCancel.clicked.connect(self.on_cancel_clicked)
        
        # Zeige Dialog
        self.calibration_dialog.show()
        print("[LOG] CalibrationDialog shown")
    
    def start_processing_thread(self):
        """Starte Processing Thread"""
        print("[LOG] Starting processing thread...")
        
        # Zeige Dialog
        self.show_processing_dialog()
        
        # Starte Thread
        self.processing_thread = ProcessingThread(
            self.sample_dir,
            self.max_samples,
            self.checkerboard_sizes,
            self.detected_checkerboard_size,
            self.square_size,
            self.camera_matrix,
            self.dist_coeffs
        )
        
        self.processing_thread.progress_updated.connect(self.on_processing_progress)
        self.processing_thread.processing_complete.connect(self.on_processing_complete)
        
        self.processing_thread.start()
        print("[LOG] Processing thread started")
    
    def on_accept_clicked(self):
        """bAccept clicked in CalibrationDialog"""
        print("[LOG] Accept clicked")
        if self.calibration_dialog:
            self.calibration_dialog.close()
            self.calibration_dialog = None
        
        # Callback aufrufen
        if self.on_perspective_complete_callback:
            self.on_perspective_complete_callback()
        
        # Zurück zur Auswahl
        self.on_exit_clicked()
    
    def on_cancel_clicked(self):
        """bCancel clicked in CalibrationDialog"""
        print("[LOG] Cancel clicked")
        if self.calibration_dialog:
            self.calibration_dialog.close()
            self.calibration_dialog = None
        
        # Aktiviere Start-Button wieder
        self.ui.bStart.setEnabled(True)
    
    def on_exit_clicked(self):
        """bExit: Zurück zur Auswahl"""
        print("[LOG] Exit clicked")
        self.cleanup()
        if self.on_exit_callback:
            self.on_exit_callback()
    
    def cleanup_camera(self):
        """Cleanup camera"""
        if hasattr(self, 'camera') and self.camera:
            self.camera.release()
            self.camera = None
            print("[LOG] Camera released")
    
    def closeEvent(self, event):
        """Window close event"""
        self.cleanup()
        event.accept()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = CalibrationPerspectiveWindow()
    window.show()
    sys.exit(app.exec_())
