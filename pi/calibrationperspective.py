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
import json
import time
import icons_rc  # Qt Resource File für Icons
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication, QDialog
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from calibrationperspectivewindow import Ui_Form as Ui_CalibrationPerspectiveWindow
from calibrationdialog import Ui_CalibrationDialog
from settings import load_camera_settings, get_camera_id, save_camera_settings, get_calibration_settings


# Debug-Modus: Dialog sofort anzeigen für Testing
DEBUG_SHOW_DIALOG = False


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
        """Verarbeite Fotos im Hintergrund"""
        try:
            print("[LOG] Processing perspective photos in background thread...")
            print(f"[DEBUG] Sample directory: {self.sample_dir}")
            print(f"[DEBUG] Trying checkerboard patterns: {self.checkerboard_sizes}")
            print(f"[DEBUG] Using distortion coefficients: {self.dist_coeffs}")
            
            # Sammle Objekt-Punkte und Bild-Punkte
            objpoints = []  # 3D-Punkte im realen Raum
            imgpoints = []  # 2D-Punkte im Bild
            
            successful_images = 0
            
            # Erstelle 3D-Punkte für das Schachbrettmuster (z=0 Ebene)
            if self.detected_checkerboard_size:
                pattern_size = self.detected_checkerboard_size
            else:
                pattern_size = self.checkerboard_sizes[0]
            
            objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
            objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
            objp *= self.square_size  # Skaliere auf tatsächliche Größe in mm
            
            # Durchsuche alle Fotos nach Checkerboards
            for i in range(1, self.max_samples + 1):
                filename = f"sample_{i:02d}.jpg"
                filepath = os.path.join(self.sample_dir, filename)
                
                self.progress_updated.emit(f"Searching checkerboard in photo {i}/{self.max_samples}...")
                print(f"\n[LOG] ===== Processing {filename} =====")
                
                if not os.path.exists(filepath):
                    print(f"[WARNING] File not found: {filepath}")
                    continue
                
                # Lade Bild
                img = cv2.imread(filepath)
                if img is None:
                    print(f"[ERROR] Failed to load {filename}")
                    continue
                
                print(f"[DEBUG] Image loaded: shape={img.shape}, dtype={img.dtype}")
                
                # Entzerrung mit Distortion-Koeffizienten
                img_undistorted = cv2.undistort(img, self.camera_matrix, self.dist_coeffs)
                print(f"[DEBUG] Image undistorted using camera matrix and dist coeffs")
                
                gray = cv2.cvtColor(img_undistorted, cv2.COLOR_BGR2GRAY)
                print(f"[DEBUG] Gray image: shape={gray.shape}, dtype={gray.dtype}")
                
                # Versuche verschiedene Checkerboard-Größen
                found = False
                found_size = None
                found_corners = None
                
                # Wenn bereits eine Größe erkannt wurde, versuche diese zuerst
                sizes_to_try = self.checkerboard_sizes.copy()
                if self.detected_checkerboard_size:
                    sizes_to_try.remove(self.detected_checkerboard_size)
                    sizes_to_try.insert(0, self.detected_checkerboard_size)
                
                for size in sizes_to_try:
                    print(f"[DEBUG] Trying checkerboard size: {size}")
                    ret, corners = cv2.findChessboardCorners(
                        gray,
                        size,
                        flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
                    )
                    
                    if ret:
                        print(f"[SUCCESS] Checkerboard found with size {size}! Refining corners...")
                        found = True
                        found_size = size
                        
                        # Verfeinere Ecken
                        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                        found_corners = corners2
                        
                        # Speichere erkannte Größe für nächste Iteration
                        if not self.detected_checkerboard_size:
                            self.detected_checkerboard_size = size
                            print(f"[INFO] Auto-detected checkerboard size: {size}")
                        
                        break
                    else:
                        print(f"[DEBUG] Size {size} failed")
                
                if found:
                    # Wenn die Größe sich ändert, passe objp an
                    if found_size != pattern_size:
                        pattern_size = found_size
                        objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
                        objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
                        objp *= self.square_size
                    
                    objpoints.append(objp)
                    imgpoints.append(found_corners)
                    successful_images += 1
                    print(f"[SUCCESS] Photo {i} added to calibration set (total: {successful_images})")
                else:
                    print(f"[WARNING] No checkerboard found in {filename}")
            
            # Berechne Perspective Calibration
            self.progress_updated.emit(f"Calculating perspective from {successful_images} photos...")
            print(f"\n[LOG] ===== Calculating Perspective =====")
            print(f"[INFO] Using {successful_images} successful images")
            
            if successful_images < 3:
                print("[ERROR] Not enough successful images (need at least 3)")
                self.processing_complete.emit(False, 0, 0, 0, successful_images)
                return
            
            # Verwende solvePnP für jedes Bild und mittele die Ergebnisse
            rvecs_list = []
            tvecs_list = []
            
            for obj_pts, img_pts in zip(objpoints, imgpoints):
                success, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, self.camera_matrix, None)
                if success:
                    rvecs_list.append(rvec)
                    tvecs_list.append(tvec)
            
            if len(rvecs_list) == 0:
                print("[ERROR] solvePnP failed for all images")
                self.processing_complete.emit(False, 0, 0, 0, successful_images)
                return
            
            # Mittele Rotation Vectors
            rvec_mean = np.mean(rvecs_list, axis=0)
            tvec_mean = np.mean(tvecs_list, axis=0)
            
            # Konvertiere Rotation Vector zu Rotation Matrix
            rmat, _ = cv2.Rodrigues(rvec_mean)
            
            # Berechne Tilt und Yaw aus Rotation Matrix
            # Tilt: Rotation um X-Achse (pitch)
            # Yaw: Rotation um Y-Achse
            tilt_rad = np.arcsin(-rmat[2, 0])
            yaw_rad = np.arctan2(rmat[1, 0], rmat[0, 0])
            
            tilt_deg = np.degrees(tilt_rad)
            yaw_deg = np.degrees(yaw_rad)
            
            # Berechne Scale (mm/pixel)
            # Verwende die mittlere Distanz der Ecken im Bild
            # und vergleiche mit der bekannten realen Distanz
            
            # Nehme ersten erfolgreichen Bildpunkt-Set für Scale-Berechnung
            img_pts = imgpoints[0]
            
            # Berechne durchschnittlichen Abstand zwischen benachbarten Ecken im Bild (in Pixel)
            distances_px = []
            for idx in range(len(img_pts) - 1):
                if idx % pattern_size[0] < pattern_size[0] - 1:  # Horizontale Nachbarn
                    dist = np.linalg.norm(img_pts[idx] - img_pts[idx + 1])
                    distances_px.append(dist)
            
            avg_dist_px = np.mean(distances_px)
            
            # Reale Distanz ist square_size in mm
            scale_mm_per_pixel = self.square_size / avg_dist_px
            
            print(f"[RESULT] Tilt: {tilt_deg:.2f}°")
            print(f"[RESULT] Yaw: {yaw_deg:.2f}°")
            print(f"[RESULT] Scale: {scale_mm_per_pixel:.4f} mm/pixel")
            print(f"[RESULT] Successful images: {successful_images}/{self.max_samples}")
            
            self.processing_complete.emit(True, tilt_deg, yaw_deg, scale_mm_per_pixel, successful_images)
            
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
        self.sample_dir = "/home/flex/uis/sample"
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
        
        # Debug: Zeige Dialog sofort
        if DEBUG_SHOW_DIALOG:
            self.debug_show_dialog()
    
    def load_distortion_coefficients(self):
        """Lade Distortion-Koeffizienten aus JSON"""
        # Lade Kamera-Settings
        saved_settings = load_camera_settings()
        
        # Finde erste angeschlossene Kamera mit Settings
        camera_id = None
        for i in range(10):
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                cam_id = get_camera_id(i)
                if cam_id in saved_settings:
                    camera_id = cam_id
                    break
        
        if not camera_id:
            print("[ERROR] No camera ID found")
            return False
        
        settings = saved_settings[camera_id]
        if not settings:
            print("[ERROR] No camera settings found")
            return False
        
        calibration = settings.get("calibration", {})
        geometric = calibration.get("geometric", {})
        
        camera_matrix_list = geometric.get("camera_matrix")
        dist_coeffs_list = geometric.get("dist_coeffs")
        
        if not camera_matrix_list or not dist_coeffs_list:
            print("[ERROR] No distortion coefficients found")
            return False
        
        self.camera_matrix = np.array(camera_matrix_list)
        self.dist_coeffs = np.array(dist_coeffs_list)
        
        print(f"[INFO] Loaded distortion coefficients:")
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
    
    def debug_show_dialog(self):
        """Debug: Zeige Dialog sofort für Testing"""
        print("[DEBUG] Showing dialog in debug mode...")
        self.show_processing_dialog()
        if self.calibration_dialog:
            self.calibration_dialog.dialog_ui.lTitle.setText("Debug Mode")
            self.calibration_dialog.dialog_ui.lProgress.setText("This is a test dialog.\n\nYou can test the buttons.")
            self.calibration_dialog.dialog_ui.bAccept.setEnabled(True)
    
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
        
        # Finde erste angeschlossene Kamera mit Settings
        camera_id = None
        for i in range(10):
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                cam_id = get_camera_id(i)
                if cam_id in saved_settings:
                    camera_id = cam_id
                    break
        
        if not camera_id:
            print("[ERROR] No camera ID found")
            return
        
        settings = saved_settings[camera_id]
        if not settings:
            print("[ERROR] No camera settings found")
            return
        
        device_path = settings.get("devicePath", "/dev/video0")
        
        # Öffne Kamera
        self.cap = cv2.VideoCapture(device_path)
        if not self.cap.isOpened():
            print(f"[ERROR] Failed to open camera: {device_path}")
            return
        
        print(f"[INFO] Camera opened: {device_path}")
        
        # Setze Kamera-Parameter aus Settings
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.get("width", 640))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.get("height", 480))
        self.cap.set(cv2.CAP_PROP_FPS, settings.get("fps", 30))
        
        # Starte Timer für Frame-Updates
        self.timer.start(33)  # ~30 FPS
    
    def update_frame(self):
        """Update camera frame"""
        if not self.cap or not self.cap.isOpened():
            return
        
        ret, frame = self.cap.read()
        if not ret:
            return
        
        # Konvertiere zu QImage
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Zeige in GraphicsView
        pixmap = QPixmap.fromImage(qt_image)
        self.scene.clear()
        self.scene.addPixmap(pixmap)
        self.ui.gvCamera.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def on_start_clicked(self):
        """bStart: Starte Auto-Capture"""
        if self.auto_capture_active:
            print("[LOG] Auto-capture already active")
            return
        
        if not self.cap or not self.cap.isOpened():
            print("[ERROR] Camera not available")
            return
        
        # Erstelle Sample-Verzeichnis
        os.makedirs(self.sample_dir, exist_ok=True)
        
        # Lösche alte Samples
        for i in range(1, self.max_samples + 1):
            filepath = os.path.join(self.sample_dir, f"sample_{i:02d}.jpg")
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Reset Sample Count
        self.sample_count = 0
        self.ui.lSamples.setText(f"{self.sample_count}/{self.max_samples}")
        
        # Deaktiviere Start-Button
        self.ui.bStart.setEnabled(False)
        
        # Starte Auto-Capture
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
        if not self.cap or not self.cap.isOpened():
            print("[ERROR] Camera not available")
            self.auto_capture_timer.stop()
            self.auto_capture_active = False
            return
        
        ret, frame = self.cap.read()
        if not ret:
            print("[ERROR] Failed to capture frame")
            return
        
        self.sample_count += 1
        filename = f"sample_{self.sample_count:02d}.jpg"
        filepath = os.path.join(self.sample_dir, filename)
        cv2.imwrite(filepath, frame)
        
        print(f"[LOG] Captured {filename}")
        
        # Update UI
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
            
            # Finde erste angeschlossene Kamera mit Settings
            camera_id = None
            for i in range(10):
                video_path = f"/dev/video{i}"
                if os.path.exists(video_path):
                    cam_id = get_camera_id(i)
                    if cam_id in saved_settings:
                        camera_id = cam_id
                        break
            
            if camera_id:
                # Stelle sicher dass Calibration-Dict existiert
                if "calibration" not in saved_settings[camera_id]:
                    saved_settings[camera_id]["calibration"] = {}
                
                # Speichere Perspective-Daten
                saved_settings[camera_id]["calibration"]["perspective"] = {
                    "tilt_deg": float(tilt_deg),
                    "yaw_deg": float(yaw_deg),
                    "scale_mm_per_pixel": float(scale_mm_per_pixel),
                    "successful_images": successful_count
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
        if self.cap:
            self.cap.release()
            self.cap = None
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
