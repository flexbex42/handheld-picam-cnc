from PyQt5.QtCore import QThread, pyqtSignal
import appSettings
from imageProcess import average_image, undistort_image
from cameraProcess import rot_scale

class CaliPerspectiveThread(QThread):
    # Signal to emit results: roll, pitch, scale
    result_ready = pyqtSignal(float, float, float)
    error = pyqtSignal(str)

    def __init__(self, images):
        super().__init__()
        self.images = images

    def run(self):
        try:
            avg_img = average_image(self.images)
            # Get the correct camera_id (camera name, not device number)
            settings = appSettings.get_app_settings()
            active_camera = settings.get('active_camera', {})
            camera_id = active_camera.get('id', None)
            if camera_id is None:
                self.error.emit('No active camera ID found.')
                return
            undistorted_img = undistort_image(camera_id, avg_img)
            roll, pitch, scale = rot_scale(undistorted_img)
            self.result_ready.emit(roll, pitch, scale)
        except Exception as e:
            self.error.emit(str(e))
