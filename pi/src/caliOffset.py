#!/usr/bin/env python3
"""
Minimal Perspective Calibration GUI
- bExit: exits window
- Shows active camera in background
- bSample: changes icon on button press
"""

from PyQt5.QtWidgets import QWidget, QApplication, QGraphicsScene, QDialog, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QIcon
from caliOffsetWin import Ui_Form
from MarkerImageWidget import MarkerImageWidget
import appSettings
import camera
import sys
import cv2
from roundbutton import RoundedButton
from caliDialog import Ui_CalibrationDialog
from PyQt5.QtWidgets import QDialog
import imageProcess 
import markerHelper 

class CalibrationOffsetWindow(QWidget):
    def __init__(self, parent=None, on_back_callback=None) -> None:
        super().__init__(parent)
        self.on_back_callback = on_back_callback
        self.on_exit_callback = on_back_callback
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.scene = QGraphicsScene()
        self.ui.gvCamera.setScene(self.scene)
        self.marker_widget = None
        self.marker_id_counter = 0
        self.freeze_mode = False
        self.camera = camera.Camera()
        self.timer = QTimer()
        self.on_continue_clicked_cnt=0
        self.mouse_press_event_active = True
        self.active_camera_id = None
        self.init_camera()
        self.sample_icon_state = False
        self.timer.timeout.connect(self.update_camera_background)
        self.timer.start(33)  # ~30 FPS
        self.setup_ui()
        self.setup_connections()
          # Load num_offset_marker from appSettings
        self.num_offset_marker = appSettings.get_calibration_settings().get('num_offset_marker', 4)
        # Extrinsic results (azimuth, tx, ty) available to whole class
        self.az = None
        self.tx = None
        self.ty = None
        # Initialize per-group counters (group 0..3)
        self.marker_counters_by_group = {0: 0, 1: 0, 2: 0, 3: 0}
        # Initialize labels: map groups to UI labels
        try:
            self.ui.lXT.setText(f"0/{self.num_offset_marker}")
            self.ui.lXB.setText(f"0/{self.num_offset_marker}")
            self.ui.lYL.setText(f"0/{self.num_offset_marker}")
            self.ui.lYR.setText(f"0/{self.num_offset_marker}")
        except Exception:
            pass

    def setup_ui(self):
        # Ersetze Buttons durch RoundedButton mit echter runder Hit-Area
        # NICHT bExit - der ist im Layout und bleibt wie er ist
        
        # Zoom und Accept/Decline Buttons
        self.ui.bDecline = RoundedButton(icon_path=":/icons/undo.png", diameter=56, parent=self, old_button=self.ui.bDecline)
        self.ui.bAccept = RoundedButton(icon_path=":/icons/ok.png", diameter=56, parent=self, old_button=self.ui.bAccept)
        self.ui.bContinue = RoundedButton(icon_path=":/icons/continue.png", diameter=56, parent=self, old_button=self.ui.bContinue)

        # Marker-Buttons (Richtungs-Buttons) - mit aktivem Icon
        self.ui.bXT = RoundedButton(icon_path=":/icons/offsetXT.png", diameter=56, parent=self, old_button=self.ui.bXT, active_icon_path=":/icons/offsetXTA.png")
        self.ui.bXB = RoundedButton(icon_path=":/icons/offsetXB.png", diameter=56, parent=self, old_button=self.ui.bXB, active_icon_path=":/icons/offsetXBA.png")
        self.ui.bYL = RoundedButton(icon_path=":/icons/offsetYL.png", diameter=56, parent=self, old_button=self.ui.bYL, active_icon_path=":/icons/offsetYLA.png")
        self.ui.bYR = RoundedButton(icon_path=":/icons/offsetYR.png", diameter=56, parent=self, old_button=self.ui.bYR, active_icon_path=":/icons/offsetYRA.png")
        
        # Sample / Foto Button (neu in UI) -> ebenfalls RoundedButton
        self.ui.bSample = RoundedButton(icon_path=":/icons/foto.png", diameter=56, parent=self, old_button=self.ui.bSample, active_icon_path=":/icons/freeze.png")
        # Setup Marker-Buttons Liste
        self.marker_buttons: list[RoundedButton] = [self.ui.bXT, self.ui.bXB, self.ui.bYL, self.ui.bYR]


        for btn in self.marker_buttons:
            btn.setHidden(True)
        self.ui.bAccept.setHidden(True)
        self.ui.bDecline.setHidden(True)    
        self.ui.bContinue.setHidden(True)
        # prepare marker button states
        for btn in self.marker_buttons:
            btn.setCheckable(True)
            btn.setChecked(False)


    def setup_connections(self):
        self.ui.bExit.clicked.connect(self.on_exit_clicked)
        self.ui.bSample.setCheckable(True)
        self.ui.bSample.clicked.connect(self.on_sample_clicked)
        # marker button handlers (index maps to group id)
        for idx, btn in enumerate(self.marker_buttons):
            # use lambda default arg to bind idx
            btn.clicked.connect(lambda checked, i=idx: self.on_marker_button_clicked(i))
        # accept/decline handlers
        self.ui.bAccept.clicked.connect(self.on_accept_clicked)
        self.ui.bDecline.clicked.connect(self.on_decline_clicked)
        # continue handler
        try:
            self.ui.bContinue.clicked.connect(self.on_continue_clicked)
        except Exception:
            pass

    def on_marker_button_clicked(self, idx: int):
        # Select marker group idx and update button checked states
        self.selected_marker_group = idx
        for i, btn in enumerate(self.marker_buttons):
            btn.setChecked(i == idx)
        

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
        if self.ui.bSample.isChecked():
            # Enter freeze mode
            self.on_freeze_mode()
        else:
            self.on_resume_camera_view()


    def on_freeze_mode(self):
        self.mouse_press_event_active = True
        # Enter freeze mode: pause camera updates and show processed image
        self.ui.bSample.setIcon(QIcon(':/icons/freeze.png'))
        if self.timer.isActive():
            self.timer.stop()
        self.freeze_mode = True
        
        # Take 5 images as fast as possible
        images = []
        for _ in range(5):
            if self.camera and hasattr(self.camera, 'read'):
                ret, frame = self.camera.read()
                if ret:
                    images.append(frame.copy())
        if len(images) < 1:
            print("[ERROR] No images captured!")
            return

        
        avg_img = imageProcess.average_image(images)

        # Undistort averaged image
        undistorted_img = avg_img
        if self.active_camera_id:
            try:
                undistorted_img = imageProcess.undistort_image(self.active_camera_id, avg_img)
            except Exception as e:
                print(f"[ERROR] undistort_image failed: {e}")

        # Show result in MarkerImageWidget
        rgb_img = cv2.cvtColor(undistorted_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Remove QGraphicsView content and overlay MarkerImageWidget
        self.ui.gvCamera.setScene(None)
        if self.marker_widget is not None:
            self.marker_widget.setParent(None)
            self.marker_widget.deleteLater()
        self.marker_widget = MarkerImageWidget(self.ui.gvCamera)
        self.marker_widget.set_image(qt_image)
        self.marker_widget.add_marker_group(0, (255,0,0))
        # prepare groups 0..3
        self.marker_widget.add_marker_group(1, (0,255,0))
        self.marker_widget.add_marker_group(2, (0,0,255))
        self.marker_widget.add_marker_group(3, (255,255,0))
        self.marker_id_counters = {0:0, 1:0, 2:0, 3:0}
        self.selected_marker_group = 0
        # show marker buttons and select first
        for btn in self.marker_buttons:
            btn.setHidden(False)
            btn.setChecked(False)
        self.marker_buttons[self.selected_marker_group].setChecked(True)
        self.marker_widget.mousePressEvent = self._marker_mouse_press_event
        layout = QVBoxLayout(self.ui.gvCamera)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.marker_widget)
        self.ui.gvCamera.setLayout(layout)

    def on_resume_camera_view(self):
        # Resume live camera view
        self.ui.bSample.setIcon(QIcon(':/icons/foto.png'))
        self.freeze_mode = False
        if not self.timer.isActive():
            self.timer.start(33)
        # Remove marker widget and restore QGraphicsView
        if self.marker_widget is not None:
            self.marker_widget.setParent(None)
            self.marker_widget.deleteLater()
            self.marker_widget = None
        # Remove layout safely
        layout = self.ui.gvCamera.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            # delete the layout object instead of calling setLayout(None)
            layout.deleteLater()
        # hide marker buttons and reset selection
        for i, btn in enumerate(self.marker_buttons):
            btn.setHidden(True)
            btn.setChecked(False)
        self.selected_marker_group = 0
        # Reset per-group counters to zero and update labels
        self.marker_counters_by_group = {0:0, 1:0, 2:0, 3:0}
        self.ui.lXt.setText(f"0/{self.num_offset_marker}")
        self.ui.lXb.setText(f"0/{self.num_offset_marker}")
        self.ui.lYl.setText(f"0/{self.num_offset_marker}")
        self.ui.lYr.setText(f"0/{self.num_offset_marker}")
        # reset label colors to orange
        orange_style = "QLabel { color: orange; font-weight: bold; font-size: 16pt; }"
        self.ui.lXt.setStyleSheet(orange_style)
        self.ui.lXb.setStyleSheet(orange_style)
        self.ui.lYl.setStyleSheet(orange_style)
        self.ui.lYr.setStyleSheet(orange_style)
        self.marker_id_counters = {}
        # hide continue button on unfreeze
        self.ui.bContinue.setHidden(True)
        self.ui.gvCamera.setScene(self.scene)
    
    def _marker_mouse_press_event(self, event):
        if self.freeze_mode and self.marker_widget and self.mouse_press_event_active:
            x, y = event.x(), event.y()
            # convert widget coords to image coords before storing/updating marker
            ix, iy = self.marker_widget.widget_to_image(x, y)

            # If there's a pending marker (we're in edit mode), update its position
            if hasattr(self, 'pending_marker') and self.pending_marker is not None:
                pg, pmid = self.pending_marker
                # update existing pending marker to new image coords
                self.marker_widget.set_marker(pg, pmid, ix, iy)
                self.marker_widget.update()
                # recenter zoom on updated marker
                try:
                    self.marker_widget.zoom_on_marker(pg, pmid, 4.0)
                except Exception:
                    pass
                return

            # No pending marker: create a new one
            group = getattr(self, 'selected_marker_group', 0)
            # ensure counter exists
            if not hasattr(self, 'marker_id_counters') or group not in self.marker_id_counters:
                if not hasattr(self, 'marker_id_counters'):
                    self.marker_id_counters = {}
                self.marker_id_counters[group] = 0
            mid = self.marker_id_counters[group]
            self.marker_widget.set_marker(group, mid, ix, iy)
            self.marker_id_counters[group] = mid + 1
            self.marker_widget.update()
            # Zoom 4x on the newly placed marker, hide group buttons, show accept/decline
            try:
                self.marker_widget.zoom_on_marker(group, mid, 4.0)
            except Exception:
                pass
            # hide marker selection buttons
            for btn in self.marker_buttons:
                btn.setHidden(True)
            # show accept/decline
            self.ui.bAccept.setHidden(False)
            self.ui.bDecline.setHidden(False)
            # store pending marker for accept/decline
            self.pending_marker = (group, mid)

    def on_accept_clicked(self):
        # Commit pending marker (already in widget). Reset view and UI.
        if not hasattr(self, 'pending_marker') or self.pending_marker is None:
            return
        # Commit: increase label counter for the group
        group, mid = self.pending_marker
        if group in self.marker_counters_by_group:
            self.marker_counters_by_group[group] += 1
        else:
            self.marker_counters_by_group[group] = 1
        # update corresponding label text and color
        try:
            count = self.marker_counters_by_group.get(group, 0)
            if group == 0:
                self.ui.lXt.setText(f"{count}/{self.num_offset_marker}")
                self.ui.lXt.setStyleSheet("QLabel { color: green; font-weight: bold; font-size: 16pt; }" if count >= self.num_offset_marker else "QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
            elif group == 1:
                self.ui.lXb.setText(f"{count}/{self.num_offset_marker}")
                self.ui.lXb.setStyleSheet("QLabel { color: green; font-weight: bold; font-size: 16pt; }" if count >= self.num_offset_marker else "QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
            elif group == 2:
                self.ui.lYl.setText(f"{count}/{self.num_offset_marker}")
                self.ui.lYl.setStyleSheet("QLabel { color: green; font-weight: bold; font-size: 16pt; }" if count >= self.num_offset_marker else "QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
            elif group == 3:
                self.ui.lYr.setText(f"{count}/{self.num_offset_marker}")
                self.ui.lYr.setStyleSheet("QLabel { color: green; font-weight: bold; font-size: 16pt; }" if count >= self.num_offset_marker else "QLabel { color: orange; font-weight: bold; font-size: 16pt; }")
        except Exception:
            pass

        # clear pending state
        self.pending_marker = None
        # reset zoom
        if self.marker_widget:
            try:
                self.marker_widget.reset_zoom()
            except Exception:
                pass
        # hide accept/decline
        self.ui.bAccept.setHidden(True)
        self.ui.bDecline.setHidden(True)
        # show marker selection buttons and restore previous selection
        for i, btn in enumerate(self.marker_buttons):
            btn.setHidden(False)
            btn.setChecked(i == getattr(self, 'selected_marker_group', 0))
        # If all counts reached num_offset_marker, show bContinue
        try:
            all_ok = all(c >= self.num_offset_marker for c in self.marker_counters_by_group.values())
            if all_ok:
                self.on_continue_clicked_cnt=0
                
            self.ui.bContinue.setHidden(not all_ok)
            
        except Exception:
            pass

    def on_decline_clicked(self):
        # Remove pending marker and reset UI
        if not hasattr(self, 'pending_marker') or self.pending_marker is None:
            return
        group, mid = self.pending_marker
        # remove marker
        if self.marker_widget:
            try:
                self.marker_widget.unset_marker(group, mid)
            except Exception:
                pass
        # decrement counter so next marker reuses id
        if hasattr(self, 'marker_id_counters') and group in self.marker_id_counters:
            if self.marker_id_counters[group] > 0:
                self.marker_id_counters[group] -= 1
        self.pending_marker = None
        # reset zoom
        if self.marker_widget:
            try:
                self.marker_widget.reset_zoom()
            except Exception:
                pass
            self.marker_widget.update()
        # hide accept/decline
        self.ui.bAccept.setHidden(True)
        self.ui.bDecline.setHidden(True)
        # show marker selection buttons and restore previous selection
        for i, btn in enumerate(self.marker_buttons):
            btn.setHidden(False)
            btn.setChecked(i == getattr(self, 'selected_marker_group', 0))
        # ensure continue button hidden when declining
        try:
            self.ui.bContinue.setHidden(True)
        except Exception:
            pass

    def on_continue_clicked(self):
        self.mouse_press_event_active = False
        # First press: compute axes from the markers and draw world axes on the image
        if getattr(self, 'on_continue_clicked_cnt', 0) == 0:
            self.ui.bContinue.setHidden(True)
            try:
                # collect marker points from widget in image coordinates
                if self.marker_widget:
                    markers = self.marker_widget.get_markers_for_axes()
                else:
                    markers = {'xt': [], 'xb': [], 'yl': [], 'yr': []}
                # Debug: print marker data to terminal
                print("[DEBUG] Marker data for axes computation:")
                for group, points in markers.items():
                    print(f"  {group}: {points}")

                # compute Az, tx, ty and store to instance for later use
                az, tx, ty = markerHelper.compute_world_axes_from_markers(markers)
                # Scale tx, ty by 'scale' from intrinsic settings
                scale = 1.0
                try:
                    cam_settings = appSettings.get_active_camera_settings()
                    scale_val = cam_settings.get('intrinsic', {}).get('perspective', {}).get('scale_mm_per_pixel', 1.0)
                    if scale_val is None:
                        scale = 1.0
                    else:
                        scale = float(scale_val)
                except Exception as e:
                    print(f"[WARN] Could not get scale from intrinsic: {e}")


                # compute axis coordinates (use image size from widget)
                # First assign computed values (scaled) so we don't pass None into euclid_transform_coord
                self.az = az
                self.tx = tx * scale if tx is not None else None
                self.ty = ty * scale if ty is not None else None
                w = getattr(self.marker_widget, 'img_width', None)
                h = getattr(self.marker_widget, 'img_height', None)
                # Use marker-driven axis computation: Y axis is based on mean x of yl/yr
                coords = markerHelper.euclid_transform_coord(tx, ty, az, w, h)
                # draw X axis (red) and Y axis (green) on the image
                x_start = coords['x_start']
                x_end = coords['x_end']
                y_start = coords['y_start']
                y_end = coords['y_end']
                if self.marker_widget:
                    try:
                        self.marker_widget.draw_line_on_image(x_start, x_end, (255,0,0), width=3)
                        self.marker_widget.draw_line_on_image(y_start, y_end, (0,255,0), width=3)
                    except Exception as e:
                        print(f"[ERROR] drawing axes failed: {e}")
                # set flag so next press opens dialog
                self.on_continue_clicked_cnt = 1
                # keep continue button visible
                self.ui.bContinue.setHidden(False)
            except Exception as e:
                print(f"[ERROR] compute/draw axes failed: {e}")
        else:
            # Second press: open confirmation dialog
            self.on_continue_clicked_cnt = 0
            try:
                dialog = QDialog(self)
                ui = Ui_CalibrationDialog()
                ui.setupUi(dialog)
                # build progress text
                try:
                    az = self.az if self.az is not None else 'N/A'
                    tx = self.tx if self.tx is not None else 'N/A'
                    ty = self.ty if self.ty is not None else 'N/A'
                    msg = (
                        "The following camera offset parameters were determined:\n"
                        f"  az (yaw): {az:.3f}\n"
                        f"  tx: {tx:.3f} mm\n"
                        f"  ty: {ty:.3f} mm\n\n"
                        "If these values look correct, do you want to save them?"
                    )
                    ui.lProgress.setText(msg)
                except Exception:
                    ui.lProgress.setText("Could not display extrinsic parameters.")

                # wire buttons
                ui.bCancel.clicked.connect(dialog.reject)
                def _on_ok():
                    # If extrinsic values are available, save them under the active camera
                    try:
                        cam_settings = appSettings.get_active_camera_settings()
                        extr = cam_settings.setdefault('extrinsic', {})
                        extr['az'] = float(self.az)
                        extr['tx'] = float(self.tx) if self.tx is not None else 0.0
                        extr['ty'] = float(self.ty) if self.ty is not None else 0.0
                        appSettings.set_active_cam_settings(cam_settings)
                        print(f"[LOG] Saved extrinsic parameter: az={self.az}, tx={self.tx}, ty={self.ty}")
                    except Exception as e:
                        print(f"[ERROR] Could not save extrinsic: {e}")
                    dialog.accept()
                    # close this calibration window
                    try:
                        self.close()
                    except Exception:
                        pass
                    # call on_exit_callback if set (restores main UI)
                    try:
                        if hasattr(self, 'on_exit_callback') and self.on_exit_callback:
                            print("[DEBUG] caliOffset: Calling on_exit_callback from dialog OK")
                            self.on_exit_callback()
                    except Exception as e:
                        print(f"[ERROR] on_exit_callback failed: {e}")
                ui.bAccept.clicked.connect(_on_ok)

                dialog.exec_()
            except Exception as e:
                print(f"[ERROR] on_continue_clicked failed: {e}")

    def cleanup(self):
        """Cleanup resources"""
        if self.timer.isActive():
            self.timer.stop()
        self.cleanup_camera()

    def on_exit_clicked(self):
        print("[DEBUG] caliOffset: Exit clicked")
        self.cleanup()
        if hasattr(self, 'on_exit_callback') and self.on_exit_callback:
            print("[DEBUG] caliOffset: Calling on_exit_callback")
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
    window = CalibrationOffsetWindow()
    window.show()
    sys.exit(app.exec_())
