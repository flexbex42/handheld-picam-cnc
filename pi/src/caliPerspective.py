#!/usr/bin/env python3
"""
Minimal Perspective Calibration GUI
- bExit: exits window
- Shows active camera in background
- bSample: changes icon on button press
"""

from PyQt5.QtWidgets import QWidget, QApplication, QGraphicsScene, QDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QIcon
from caliPerspectiveWin import Ui_Form as Ui_CalibrationPerspectiveWindow
import appSettings
import camera
import sys
import cv2
import numpy as np
from caliDialog import Ui_CalibrationDialog
from caliPerspectiveThread import CaliPerspectiveThread

class CalibrationPerspectiveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_CalibrationPerspectiveWindow()
        self.ui.setupUi(self)
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        self.camera = camera.Camera()
        self.timer = QTimer()
        self.active_camera_id = None
        self.setup_connections()
        self.init_camera()
        self.sample_icon_state = False
        self.captured_samples = []  # Store captured images here
        self.timer.timeout.connect(self.update_camera_background)
        self.timer.start(33)  # ~30 FPS

    def setup_connections(self):
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bSample.clicked.connect(self.on_sample_clicked)

    def init_camera(self):
        if self.camera.open():
            _, self.active_camera_id = appSettings.get_active_camera()
        else:
            self.active_camera_id = None

    def update_camera_background(self):
        if self.camera and hasattr(self.camera, 'read'):
            ret, frame = self.camera.read()
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                self.scene.clear()
                self.scene.addPixmap(pixmap)
                self.ui.gvCamera.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        # Show active camera ID in window title
        if self.active_camera_id:
            self.setWindowTitle(f"Perspective Calibration - Active Camera: {self.active_camera_id}")
        else:
            self.setWindowTitle("Perspective Calibration - No Camera")

    def on_sample_clicked(self):
        # Toggle icon state based on checked state
        self.ui.bSample.setDisabled(True)
        # Take 5 photos and save to array
        self.captured_samples = []
        for i in range(5):
            if self.camera and hasattr(self.camera, 'read'):
                ret, frame = self.camera.read()
                if ret:
                    frame_bgr = np.ascontiguousarray(frame.astype(np.uint8))
                    self.captured_samples.append(frame_bgr)
        # Pause camera updates
        if self.timer.isActive():
            self.timer.stop()
        # Show dialog after capturing samples
        self.show_processing_dialog()
        # Start processing thread
        self.processing_thread = CaliPerspectiveThread(self.captured_samples)
        self.processing_thread.result_ready.connect(self.on_processing_result)
        self.processing_thread.error.connect(self.on_processing_error)
        self.processing_thread.start()

    def show_processing_dialog(self):
        self.calibration_dialog = QDialog(self)
        self.calibration_dialog.setWindowFlags(Qt.FramelessWindowHint)
        self.calibration_dialog.dialog_ui = Ui_CalibrationDialog()
        self.calibration_dialog.dialog_ui.setupUi(self.calibration_dialog)
        hardware_settings = appSettings.get_hardware_settings()
        screen_size = hardware_settings.get("screen_size", {"width": 640, "height": 480})
        screen_width = screen_size.get("width", 640)
        screen_height = screen_size.get("height", 480)
        dialog_width = 400
        dialog_height = 350
        self.calibration_dialog.setFixedSize(dialog_width, dialog_height)
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.calibration_dialog.move(x, y)
        self.calibration_dialog.dialog_ui.lTitle.setText("Processing Perspective Calibration")
        self.calibration_dialog.dialog_ui.lProgress.setText("Processing...")
        self.calibration_dialog.dialog_ui.bAccept.setEnabled(False)
        self.calibration_dialog.dialog_ui.bAccept.clicked.connect(self.on_accept_clicked)
        self.calibration_dialog.dialog_ui.bCancel.clicked.connect(self.on_cancel_clicked)
        self.calibration_dialog.show()
        self.processing_dialog = self.calibration_dialog

    def on_processing_result(self, roll, pitch, scale):
        self.calibration_dialog.dialog_ui.lProgress.setText(f"Roll: {roll:.2f}\nPitch: {pitch:.2f}\nScale: {scale:.4f} mm/px")
        self.calibration_dialog.dialog_ui.bAccept.setEnabled(True)
        self.calibration_dialog.dialog_ui.bCancel.setEnabled(True)
        self.last_result = (roll, pitch, scale)

    def on_processing_error(self, error_msg):
        self.calibration_dialog.dialog_ui.lProgress.setText(f"Error: {error_msg}")
        self.calibration_dialog.dialog_ui.bAccept.setEnabled(False)
        self.calibration_dialog.dialog_ui.bCancel.setEnabled(True)
        self.last_result = None

    def on_accept_clicked(self):
        # Store roll, pitch, scale in app_settings.json under active camera
        if hasattr(self, 'last_result') and self.last_result:
            roll, pitch, scale = self.last_result
            # Get the active camera id and all settings
            settings = appSettings.get_app_settings()
            active_camera = settings.get('active_camera', {})
            camera_id = active_camera.get('id', None)
            if camera_id and camera_id in settings:
                cam_settings = settings[camera_id]
                intrinsic = cam_settings.setdefault('intrinsic', {})
                intrinsic['roll_deg'] = float(roll)
                intrinsic['pitch_deg'] = float(pitch)
                intrinsic['scale_mm_per_pixel'] = float(scale)
                settings[camera_id] = cam_settings
                appSettings.save_camera_settings(settings)
        self.on_cancel_clicked()

    def on_cancel_clicked(self):
        if hasattr(self, 'calibration_dialog') and self.calibration_dialog:
            self.calibration_dialog.close()
            self.calibration_dialog = None
        # Resume camera updates
        if not self.timer.isActive():
            self.timer.start(33)
        self.ui.bSample.setDisabled(False)

    def cleanup(self):
        """Cleanup resources"""
        if self.timer.isActive():
            self.timer.stop()
        self.cleanup_camera()

    def on_exit_clicked(self):
        print("[LOG] Exit clicked")
        self.cleanup()
        if hasattr(self, 'on_exit_callback') and self.on_exit_callback:
            self.on_exit_callback()
        #self.close()

    def cleanup_camera(self):
        if hasattr(self, 'camera') and self.camera:
            self.camera.release()
            self.camera = None
            print("[LOG] Camera released")

    def closeEvent(self, event):
        self.cleanup()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CalibrationPerspectiveWindow()
    window.show()
    sys.exit(app.exec_())
