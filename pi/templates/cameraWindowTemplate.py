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
#TODO insert correct import below
from caliXXXWin import Ui_Form
import appSettings
import camera
import sys
import cv2

#TODO insert correct class name below
class CalibrationXXXWindow(QWidget):
    def __init__(self, parent=None, on_back_callback=None):
        super().__init__(parent)
        self.on_back_callback = on_back_callback
        self.on_exit_callback = on_back_callback
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        self.camera = camera.Camera()
        self.timer = QTimer()
        self.active_camera_id = None
        self.setup_connections()
        self.init_camera()
        self.sample_icon_state = False
        self.timer.timeout.connect(self.update_camera_background)
        self.timer.start(33)  # ~30 FPS

    def setup_connections(self):
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bSample.setCheckable(True)
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
                import cv2
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
        if self.ui.bSample.isChecked():
            self.ui.bSample.setIcon(QIcon(':/icons/freeze.png'))
            # Pause camera updates
            if self.timer.isActive():
                self.timer.stop()
        else:
            self.ui.bSample.setIcon(QIcon(':/icons/foto.png'))
            # Resume camera updates
            if not self.timer.isActive():
                self.timer.start(33)

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
        self.close()

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
    #TODO insert correct class name below
    window = XXXCalibrationPerspectiveWindow()
    window.show()
    sys.exit(app.exec_())
