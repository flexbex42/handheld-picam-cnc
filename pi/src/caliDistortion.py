#!/usr/bin/env python3
"""
Calibration Distortion Window Logik
- Kalibrierung der Linsenverzerrung mittels Schachbrettmuster
- Sammelt 15 Bilder und berechnet Kamera-Matrix und Verzerrungskoeffizienten
"""

import os
import cv2
import numpy as np
import rectifyHelper
import json
import icons_rc  # Qt Resource File für Icons
from PyQt5.QtWidgets import QWidget, QDialogButtonBox, QGraphicsScene, QApplication
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from caliDistortionWin import Ui_Form as Ui_CalibrationDistortionWindow
from caliDialog import Ui_CalibrationDialog
import appSettings
import camera


class ProcessingThread(QThread):
    """Hintergrund-Thread für Foto-Verarbeitung"""
    progress_updated = pyqtSignal(str)  # Text für Progress-Label
    processing_complete = pyqtSignal(bool, object, object, object, object, int)  # success, camera_matrix, dist_coeffs, error, detected_size, successful_count
    
    def __init__(self, sample_dir, max_samples, checkerboard_sizes, detected_size, square_size):
        super().__init__()
        self.sample_dir = sample_dir
        self.max_samples = max_samples
        self.checkerboard_sizes = checkerboard_sizes
        self.detected_checkerboard_size = detected_size
        self.square_size = square_size
        
    def run(self):
        """Verarbeite Fotos im Hintergrund (refactored to use rectificationHelper)."""
        try:
            self.progress_updated.emit("Processing calibration samples...")
            result = rectifyHelper.calibrate_camera_from_samples(
                self.sample_dir,
                self.max_samples,
                self.checkerboard_sizes,
                self.detected_checkerboard_size,
                self.square_size
            )
            success, camera_matrix, dist_coeffs, mean_error, detected_size, successful_count = result
            if not success:
                error_text = f"Error: Only {successful_count}/{self.max_samples} photos contain valid checkerboards.\n\n"
                error_text += "At least 3 photos with checkerboards are required for calibration.\n\n"
                error_text += "Please cancel and try again with better focus and lighting."
                self.progress_updated.emit(error_text)
                self.processing_complete.emit(False, None, None, None, None, successful_count)
                return
            self.processing_complete.emit(True, camera_matrix, dist_coeffs, mean_error, detected_size, successful_count)
        except Exception as e:
            print(f"[ERROR] Processing failed: {e}")
            import traceback
            traceback.print_exc()
            self.progress_updated.emit(f"Error during processing:\n{str(e)}")
            self.processing_complete.emit(False, None, None, None, None, 0)


class CalibrationDistortionWindow(QWidget):
    """Distortion Calibration Window mit Logik"""
    
    
    def __init__(self, parent=None, on_back_callback=None):
        super().__init__(parent)
        
        # Callbacks
        self.on_back_callback = on_back_callback
        
        # Setup UI
        self.ui = Ui_CalibrationDistortionWindow()
        self.ui.setupUi(self)
        
        # Entferne alle Margins
        self.setContentsMargins(0, 0, 0, 0)
        if self.layout():
            self.layout().setContentsMargins(0, 0, 0, 0)
        
        # Kamera Setup (centralized)
        self.camera, self.camera_id, self.camera_settings = camera.setup_camera()
        self.timer = None

        # Kalibrierungs-Daten
        self.sample_dir = rectifyHelper.get_sample_dir()
        self.max_samples = 15
        self.current_sample = 0

        # Ensure sample directory exists
        rectifyHelper.ensure_sample_dir(self.sample_dir)

        # Load checkerboard config from appSettings (centralized)
        self.checkerboard_size, self.square_size = appSettings.get_checkerboard_config()
        print(f"[INFO] Distortion calibration using checkerboard from settings:")
        print(f"  Boxes: {self.checkerboard_size[0]+1}x{self.checkerboard_size[1]+1} ({self.checkerboard_size[0]}x{self.checkerboard_size[1]} inner corners)")
        print(f"  Square size: {self.square_size}mm")

        self.checkerboard_sizes = [self.checkerboard_size]
        self.detected_checkerboard_size = None  # Set on first successful image

        # Calibration results
        self.camera_matrix = None
        self.dist_coeffs = None
        self.calibration_error = None
        
        # Status-Tracking für Button-Farbe
        self.detection_timer = QTimer(self)
        self.detection_timer.timeout.connect(self.reset_sample_button_color)
        self.detection_timer.setSingleShot(True)
        
        # Setup UI
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
        
        
        print("[LOG] Distortion Calibration window loaded")
        
    def cleanup_sample_directory(self):
        """Lösche alle vorhandenen Sample-Bilder"""
        if os.path.exists(self.sample_dir):
            for filename in os.listdir(self.sample_dir):
                if filename.endswith('.jpg') or filename.endswith('.png'):
                    filepath = os.path.join(self.sample_dir, filename)
                    try:
                        os.remove(filepath)
                        print(f"[LOG] Removed old sample: {filename}")
                    except Exception as e:
                        print(f"[ERROR] Failed to remove {filename}: {e}")
        
    def setup_ui(self):
        """Initialisiere UI-Elemente"""
        # Hole Screen-Größe aus Kalibrierungs-Einstellungen
        hardware_settings = appSettings.get_hardware_settings()
        screen_size = hardware_settings.get("screen_size", {"width": 640, "height": 480})
        screen_width = screen_size["width"]
        screen_height = screen_size["height"]

        print(f"[DEBUG] GraphicsView current size: {self.ui.gvCamera.width()}x{self.ui.gvCamera.height()}")
        
        # Erstelle QGraphicsScene für GraphicsView
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        
        # Deaktiviere Scrollbars
        self.ui.gvCamera.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.gvCamera.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Style Sample Counter (orange und bold)
        self.ui.lSamples.setStyleSheet("QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
        
        # Erstelle Calibration Dialog
        from PyQt5.QtWidgets import QFrame
        self.dialog_widget = QFrame(self)
        self.dialog_ui = Ui_CalibrationDialog()
        self.dialog_ui.setupUi(self.dialog_widget)
        
        # Setze feste Größe des Dialogs
        dialog_width = 400
        dialog_height = 350
        self.dialog_widget.setFixedSize(dialog_width, dialog_height)
        
        # Positioniere Dialog in der Mitte
        x = (640 - dialog_width) // 2
        y = (480 - dialog_height) // 2
        self.dialog_widget.move(x, y)
        
        # Verbinde Dialog-Buttons
        self.dialog_ui.bAccept.clicked.connect(self.on_accept_clicked)
        self.dialog_ui.bCancel.clicked.connect(self.on_cancel_clicked)
        
        # Verstecke Dialog am Anfang
        self.dialog_widget.setVisible(False)
        

        
    def setup_connections(self):
        """Verbinde UI-Elemente mit Logik"""
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bSample.clicked.connect(self.on_sample_clicked)
        self.ui.bUndo.clicked.connect(self.on_undo_clicked)
        
    def update_frame(self):
        """Aktualisiere Kamera-Bild"""
        if self.camera is None or not self.camera.is_opened():
            return
            
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return
        
        # Konvertiere BGR zu RGB für Anzeige
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Zeige Bild in GraphicsView
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        
        # Skaliere auf GraphicsView-Größe
        scaled_pixmap = pixmap.scaled(self.ui.gvCamera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.scene.clear()
        self.scene.addPixmap(scaled_pixmap)
        
    def update_sample_counter(self):
        """Aktualisiere Sample-Counter Anzeige"""
        self.ui.lSamples.setText(f"{self.current_sample}/{self.max_samples}")
        
    def on_sample_clicked(self):
        """bSample: Nehme ein Foto auf (über Camera-Klasse)"""
        if self.camera is None:
            print("[ERROR] No camera available")
            return
        # Wenn Counter bei 0, lösche alte Samples (neue Session)
        if self.current_sample == 0:
            self.cleanup_sample_directory()
            print("[LOG] Starting new sample session")
        # Prüfe ob bereits alle Samples gesammelt
        if self.current_sample >= self.max_samples:
            print("[WARNING] All samples already collected!")
            return
        # Capture aktuelles Frame über Camera-Klasse
        ret, frame = self.camera.read() if hasattr(self.camera, 'read') else (False, None)
        if not ret:
            print("[ERROR] Failed to capture frame")
            return
        # Speichere Bild als JPG
        filename = f"sample_{self.current_sample + 1:02d}.jpg"
        filepath = os.path.join(self.sample_dir, filename)
        cv2.imwrite(filepath, frame)
        print(f"[DEBUG] Saved photo: {filepath}")
        print(f"[DEBUG] Frame shape: {frame.shape}, dtype: {frame.dtype}")
        self.current_sample += 1
        self.update_sample_counter()
        # Aktiviere Undo-Button
        self.ui.bUndo.setEnabled(True)
        # Zeige kurz grün an (500ms) dann zurück zu blau
        self.ui.bSample.setStyleSheet("QPushButton { background-color: green; }")
        self.detection_timer.start(500)  # Nach 500ms zurück zu blau
        
        print(f"[LOG] Photo {self.current_sample}/{self.max_samples} saved: {filename}")
        
        # Wenn alle Samples gesammelt, zeige Dialog
        if self.current_sample >= self.max_samples:
            self.show_processing_dialog()
    
    def on_processing_progress(self, message):
        """Update Progress-Label während Verarbeitung"""
        self.dialog_ui.lProgress.setText(message)
    
    def on_processing_complete(self, success, camera_matrix, dist_coeffs, error, detected_size, successful_count):
        """Verarbeitung abgeschlossen - zeige Ergebnisse"""
        if success:
            # Speichere Ergebnisse
            self.camera_matrix = camera_matrix
            self.dist_coeffs = dist_coeffs
            self.calibration_error = error
            self.detected_checkerboard_size = detected_size
            
            # Zeige Ergebnisse
            result_text = f"Valid photos: {successful_count}/{self.max_samples}\n"
            result_text += f"Reprojection Error: {error:.4f} pixels\n\n"
            result_text += "Calibration successful!"
            
            self.dialog_ui.lTitle.setText("Calibration Complete!")
            self.dialog_ui.lProgress.setText(result_text)
            
            # Aktiviere Accept-Button nur bei Erfolg
            self.dialog_ui.bAccept.setEnabled(True)
        else:
            # Fehlerfall - zeige Fehlermeldung
            error_text = f"Calibration failed!\n\n"
            error_text += f"Not enough valid photos.\n"
            error_text += f"Found: {successful_count}/{self.max_samples}\n\n"
            error_text += "Please ensure:\n"
            error_text += "- Checkerboard clearly visible\n"
            error_text += "- Good lighting conditions\n"
            error_text += "- Various angles captured"
            
            self.dialog_ui.lTitle.setText("Calibration Failed")
            self.dialog_ui.lProgress.setText(error_text)
            
            # Accept-Button bleibt deaktiviert bei Fehler
            self.dialog_ui.bAccept.setEnabled(False)
        
        # Cancel-Button immer aktiviert
        self.dialog_ui.bCancel.setEnabled(True)
    
    def reset_sample_button_color(self):
        """Setze Sample-Button zurück zu Standardfarbe (blau durch Stylesheet)"""
        self.ui.bSample.setStyleSheet("")  # Zurück zu globalem Stylesheet (blau)
            
    def on_undo_clicked(self):
        """bUndo: Lösche letztes Foto"""
        if self.current_sample > 0:
            # Lösche letztes gespeichertes Foto
            filename = f"sample_{self.current_sample:02d}.jpg"
            filepath = os.path.join(self.sample_dir, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"[LOG] Removed photo: {filename}")
            
            self.current_sample -= 1
            self.update_sample_counter()
            
            # Deaktiviere Undo wenn keine Bilder mehr
            if self.current_sample == 0:
                self.ui.bUndo.setEnabled(False)
            
            print(f"[LOG] Now at {self.current_sample}/{self.max_samples}")
    
    def show_processing_dialog(self):
        """Zeige Dialog sofort und starte Verarbeitung nach kurzer Verzögerung"""
        # Deaktiviere Buttons
        self.ui.bExit.setEnabled(False)
        self.ui.bSample.setEnabled(False)
        self.ui.bUndo.setEnabled(False)
        
        # Stoppe Video-Stream während Verarbeitung
        if self.timer:
            self.timer.stop()
        
        # Zeige Dialog mit Progress und deaktivierten Buttons
        self.dialog_widget.setVisible(True)
        self.dialog_widget.raise_()  # Bringe Dialog nach vorne
        self.dialog_ui.lTitle.setText("Processing Calibration")
        self.dialog_ui.lProgress.setText("Processing photos...")
        self.dialog_ui.bAccept.setEnabled(False)
        self.dialog_ui.bCancel.setEnabled(True)
        
        # Starte Verarbeitung nach kurzer Verzögerung (damit Dialog sichtbar wird)
        QTimer.singleShot(100, self.start_processing_thread)
    
    def start_processing_thread(self):
        """Starte den Verarbeitungs-Thread"""
        # Starte Verarbeitung im Hintergrund-Thread
        self.processing_thread = ProcessingThread(
            self.sample_dir,
            self.max_samples,
            self.checkerboard_sizes,
            self.detected_checkerboard_size,
            self.square_size
        )
        self.processing_thread.progress_updated.connect(self.on_processing_progress)
        self.processing_thread.processing_complete.connect(self.on_processing_complete)
        self.processing_thread.start()
    
    def on_accept_clicked(self):
        """Accept: Speichere Kalibrierung und gehe zurück"""
        print("[LOG] Saving calibration data...")
        
        # Lade aktuelle Settings
        saved_settings = appSettings.load_app_settings()
        
        # Stelle sicher dass Calibration-Dict existiert
        if "calibration" not in saved_settings[self.camera_id]:
            saved_settings[self.camera_id]["calibration"] = {}
        
        # Speichere Distortion-Daten
        saved_settings[self.camera_id]["calibration"]["geometric"] = {
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.tolist(),
            "reprojection_error": float(self.calibration_error),
            "checkerboard_size": self.detected_checkerboard_size,
            "num_images": self.max_samples
        }
        
        # Speichere zu Datei
        appSettings.save_camera_settings(saved_settings)
        
        print("[LOG] Calibration data saved")
        print("[INFO] Sample photos kept in /home/flex/uis/sample/ for review")
        
        # Schließe Kamera
        self.cleanup_camera()
        
        # Gehe zurück
        if self.on_back_callback:
            self.on_back_callback()
            
    def on_cancel_clicked(self):
        """Cancel: Verwerfe Kalibrierung und setze zurück"""
        print("[LOG] Calibration cancelled, resetting...")
        print("[INFO] Sample photos kept in /home/flex/uis/sample/ for review")
        
        # Reset Daten (aber Fotos NICHT löschen!)
        self.current_sample = 0
        self.camera_matrix = None
        self.dist_coeffs = None
        self.calibration_error = None
        
        # Update UI
        self.update_sample_counter()
        self.dialog_widget.setVisible(False)
        
        # Aktiviere Buttons
        self.ui.bExit.setEnabled(True)
        self.ui.bSample.setEnabled(True)
        self.ui.bUndo.setEnabled(False)
        
        # Starte Video-Stream wieder
        if self.timer and not self.timer.isActive():
            self.timer.start(33)
        
    def on_exit_clicked(self):
        """bExit: Schließe ohne zu speichern"""
        print("[LOG] Exit without saving")
        
        # Schließe Kamera
        self.cleanup_camera()
        
        # Gehe zurück
        if self.on_back_callback:
            self.on_back_callback()
            
    def cleanup_camera(self):
        """Schließe Kamera und Timer"""
        if self.timer:
            self.timer.stop()
            self.timer = None
            
        if self.camera:
            self.camera.release()
            self.camera = None
            
    def closeEvent(self, event):
        """Cleanup beim Schließen des Fensters"""
        self.cleanup_camera()
        event.accept()
