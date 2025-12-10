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
import rectifyHelper
import json
import time
import icons_rc  # Qt Resource File für Icons
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QApplication, QDialog
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from caliPerspectiveWin import Ui_Form as Ui_CalibrationPerspectiveWindow
from caliDialog import Ui_CalibrationDialog
import appSettings
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
            result = rectifyHelper.compute_perspective_from_samples(
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
    def init_camera(self):
        """Initialisiere Kamera"""
        # Öffne Kamera über Camera-Klasse
        self.camera = camera.Camera()
        if not self.camera.open():
            print(f"[ERROR] Failed to open camera: ")
            return
        print(f"[INFO] Camera opened: ")
        # Starte Timer für Frame-Updates
        self.timer.start(33)  # ~30 FPS
    def setup_connections(self):
        """Signal-Verbindungen einrichten"""
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bStart.clicked.connect(self.on_start_clicked)
        self.timer.timeout.connect(self.update_frame)
        self.auto_capture_timer.timeout.connect(self.on_auto_capture_tick)
    def setup_ui(self):
        """UI initialisieren"""
        self.ui.gvCamera.setScene(self.scene)
        self.ui.lSamples.setText(f"{self.sample_count}/{self.max_samples}")
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
        self.sample_dir = rectifyHelper.get_sample_dir()
        
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
        calib_settings = appSettings.get_calibration_settings()
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

        #get camera calibration data
        _, camera_id = appSettings.get_active_camera()
        print(f"[DEBUG] Active camera_id: {camera_id}")
        settings = appSettings.load_app_settings()
        print(f"[DEBUG] All settings keys: {list(settings.keys())}")
        cam_settings = appSettings.get_camera_settings(camera_id)
        print(f"[DEBUG] cam_settings for camera_id '{camera_id}': {cam_settings}")
        calibration = cam_settings.get('calibration', {})
        geom = calibration.get('geometric', {})
        camera_matrix_list = geom.get('camera_matrix')
        dist_coeffs_list = geom.get('dist_coeffs')
        print("[DEBUG] Loaded camera_matrix_list from settings:")
        print(camera_matrix_list)
        print("[DEBUG] Loaded dist_coeffs_list from settings:")
        print(dist_coeffs_list)
        self.camera_matrix = np.array(camera_matrix_list)
        self.dist_coeffs = np.array(dist_coeffs_list)
        print(f"[DEBUG] self.camera_matrix after np.array: {self.camera_matrix}, shape: {self.camera_matrix.shape}")
        print(f"[DEBUG] self.dist_coeffs after np.array: {self.dist_coeffs}, shape: {self.dist_coeffs.shape}")
                
        # Initialisiere Kamera
        self.init_camera()
       
    
      
    def cleanup(self):
        """Cleanup resources"""
        if self.timer.isActive():
            self.timer.stop()
        if self.auto_capture_timer.isActive():
            self.auto_capture_timer.stop()
        self.cleanup_camera()
    
    def run(self):
        """Verarbeite Fotos im Hintergrund (refactored to use rectificationHelper)."""
        try:
            print("[DEBUG] ProcessingThread.run: camera_matrix:")
            print(self.camera_matrix)
            print(f"[DEBUG] camera_matrix type: {type(self.camera_matrix)}, shape: {getattr(self.camera_matrix, 'shape', None)}")
            print("[DEBUG] ProcessingThread.run: dist_coeffs:")
            print(self.dist_coeffs)
            print(f"[DEBUG] dist_coeffs type: {type(self.dist_coeffs)}, shape: {getattr(self.dist_coeffs, 'shape', None)}")
            self.progress_updated.emit("Processing perspective calibration samples...")
            result = rectifyHelper.compute_perspective_from_samples(
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
        NO_CAM_MODE = appSettings.is_debug_no_cam()
        if self.sample_count >= self.max_samples:
            # Alle Samples gesammelt
            self.auto_capture_timer.stop()
            self.auto_capture_active = False
            print("[LOG] Auto-capture complete")
            # Starte Processing
            self.start_processing_thread()
            return
        # Nehme Foto
        if NO_CAM_MODE:
            test_img_path = '/home/flex/diy/handheld-picam-cnc/pi/test/test1.jpg'
            if not os.path.exists(test_img_path):
                print(f"[ERROR] Test image not found: {test_img_path}")
                self.auto_capture_timer.stop()
                self.auto_capture_active = False
                return
            frame = cv2.imread(test_img_path)
            if frame is None:
                print(f"[ERROR] Failed to load test image: {test_img_path}")
                self.auto_capture_timer.stop()
                self.auto_capture_active = False
                return
            ret = True
        else:
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
            # Always use the active_camera from settings for saving calibration
            camera_id = appSettings.get_active_camera_id()
            print(f"[DEBUG] Using active_camera for saving perspective calibration: {camera_id}")

            # Load all settings and get this camera's calibration dict
            saved_settings = appSettings.load_app_settings()
            if camera_id not in saved_settings:
                saved_settings[camera_id] = {}
            if 'calibration' not in saved_settings[camera_id]:
                saved_settings[camera_id]['calibration'] = {}
            calibration = saved_settings[camera_id]['calibration']

            # Store tilt as negated and yaw shifted by +180° per new convention
            stored_tilt = float(-tilt_deg)
            stored_yaw = float(yaw_deg + 180.0)
            print(f"[DEBUG] Perspective save: raw tilt={tilt_deg:.2f}°, yaw={yaw_deg:.2f}° → stored tilt={stored_tilt:.2f}°, yaw={stored_yaw:.2f}°")

            # Compute minimal translation to make projected corners visible (dummy values for now)
            # TODO: Replace with actual translation calculation if needed
            translate_x = 0
            translate_y = 0

            # Save perspective calibration as a subkey of calibration
            calibration['perspective'] = {
                'tilt_deg': stored_tilt,
                'yaw_deg': stored_yaw,
                'scale_mm_per_pixel': scale_mm_per_pixel,
                'successful_images': successful_count,
                'translate_x': translate_x,
                'translate_y': translate_y
            }

            # Save to file
            print("[DEBUG] Calling appSettings.save_camera_settings(...) to persist perspective calibration")
            appSettings.save_camera_settings(saved_settings)
            print(f"[SUCCESS] Perspective calibration saved for camera_id={camera_id}")

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
