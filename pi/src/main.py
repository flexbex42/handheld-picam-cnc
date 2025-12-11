#!/usr/bin/env python3
"""
PyQt5 App mit Trennung von UI und Logik
- UI wird aus mainwindow.py geladen (pyuic5-generiert)
- Logik ist hier zentral implementiert
"""

import sys
import cv2  # Wird beim Start geladen (dauert ~16 Sekunden auf Pi)
import os
import json
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt

# Importiere die auto-generierten UIs
from mainWin import Ui_MainWindow
from caliDevice import SettingsWindow
import appSettings
import camera
from caliSelect import CalibrationSelectWindow


class MainApp(QMainWindow):
    """Hauptanwendung mit Button-Logik"""
    
    def __init__(self):
        super().__init__()
        
        # Erstelle Main UI
        self.main_ui = Ui_MainWindow()
        self.main_ui.setupUi(self)
        
        # Entferne Margins vom Layout für Vollbild
        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        
        # Entferne StatusBar
        self.setStatusBar(None)
        
        # Entferne MenuBar
        self.setMenuBar(None)
        
        # Settings Window Referenz
        self.settings_window = None
        
        # Calibration Select Window Referenz
        self.calibration_select_window = None
        
        # Lade zuletzt ausgewählte Kamera beim Start
        self.load_selected_camera_on_startup()
        
        # Zeige normale UI
        self.show_main_view()
    
    def load_selected_camera_on_startup(self):
        """Lade die zuletzt ausgewählte Kamera beim Programmstart"""
        saved_settings = appSettings.get_app_settings()

        # Assume new 'active_camera' object exists in settings. If its id is empty,
        # treat this as no camera selected.
        active_cam = saved_settings['active_camera']
        selected_cam_id = active_cam.get('id') or None

        if selected_cam_id:
            # Versuche die zuletzt ausgewählte Kamera zu finden
            print(f"[LOG] Looking for previously selected camera: {selected_cam_id}")
            for i in range(10):
                video_path = f"/dev/video{i}"
                if os.path.exists(video_path):
                    camera_id = camera.get_camera_id(i)
                    if camera_id == selected_cam_id:
                        # Persistence of active camera will be handled by set_selected_camera()
                        # updating device number
                        appSettings.set_active_camera(i, camera_id)
                        print(f"[LOG] Loaded previously selected camera on startup: index={i}, id={camera_id}")
                        return

            print(f"[LOG] Previously selected camera not found")
        else:
            print("[LOG] No previously selected camera in settings")
        
    def update_camera_status(self):
        """Update Checkboxes mit Kamera-Status und MCU-Status"""
        from camera import update_active_camera_info
        saved_settings = appSettings.get_app_settings()
        result = update_active_camera_info()
        if result is None:
            # No camera found
            self.main_ui.cbCamera.setChecked(False)
            self.main_ui.cbCamera.setText("No Camera")
            self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: red; }")
            print("[LOG] No camera found")
            camera_id = None
        else:
            camera_id, device_number = result
            display_name = camera_id.split('_')[0] if '_' in camera_id else camera_id[:15]
            camera_settings = saved_settings.get(camera_id, {})
            calibration_data = camera_settings.get("calibration", {})
            has_geometric = "geometric" in calibration_data and calibration_data["geometric"]
            has_scale = "scale" in calibration_data and calibration_data["scale"]
            has_offset = "offset" in calibration_data and calibration_data["offset"]
            all_calibrated = has_geometric and has_scale and has_offset
            if all_calibrated:
                self.main_ui.cbCamera.setChecked(True)
                self.main_ui.cbCamera.setText(f"{display_name}")
                self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: green; }")
                print(f"[LOG] Camera fully calibrated: {display_name}")
            else:
                self.main_ui.cbCamera.setChecked(False)
                self.main_ui.cbCamera.setText(f"{display_name}\nCalibrate")
                self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: orange; }")
                print(f"[LOG] Camera needs calibration: {display_name}")
        # MCU Status (Dummy - noch nicht implementiert)
        mcu_detected = False
        self.main_ui.cbMCU.setChecked(False)
        self.main_ui.cbMCU.setText("No MCU")
        self.main_ui.cbMCU.setStyleSheet("QCheckBox { color: red; }")
        # Disable alle Checkboxen (nur Status-Anzeige)
        self.main_ui.cbCamera.setEnabled(False)
        self.main_ui.cbMCU.setEnabled(False)
        # Force Style-Update
        self.main_ui.cbCamera.style().unpolish(self.main_ui.cbCamera)
        self.main_ui.cbCamera.style().polish(self.main_ui.cbCamera)
        self.main_ui.cbMCU.style().unpolish(self.main_ui.cbMCU)
        self.main_ui.cbMCU.style().polish(self.main_ui.cbMCU)
        # ===== Button Aktivierung/Deaktivierung =====
        self.main_ui.bCameraSetup.setEnabled(result is not None)
        self.main_ui.bMCUSetup.setEnabled(mcu_detected)
        both_ready = self.main_ui.cbCamera.isChecked() and self.main_ui.cbMCU.isChecked()
        self.main_ui.bCncMode.setEnabled(both_ready)
        
    def show_main_view(self):
        """Zeige Main View"""
        # Wenn wir von CalibrationSelect oder Settings zurückkommen, stelle die Main UI wieder her
        if self.calibration_select_window is not None or self.settings_window is not None:
            # Erstelle Main UI neu
            self.main_ui = Ui_MainWindow()
            self.main_ui.setupUi(self)
            self.calibration_select_window = None
            self.settings_window = None
        
        # Verbinde Buttons
        self.main_ui.bCameraSetup.clicked.connect(self.on_camera_setup_clicked)
        self.main_ui.bMCUSetup.clicked.connect(self.on_mcu_setup_clicked)
        self.main_ui.bCncMode.clicked.connect(self.on_cnc_mode_clicked)
        self.main_ui.bExit.clicked.connect(self.on_exit_clicked)
        
        # Update Kamera-Status in Checkbox
        self.update_camera_status()
        
        # Fenster-Titel
        self.setWindowTitle("PyQt5 Main Window")
        
    def show_ui_elements(self):
        """Zeige alle UI-Elemente"""
        # Diese Methode wird nicht mehr benötigt
        pass
        
    def show_settings_view(self):
        """Zeige Settings View im gleichen Fenster"""
        # Erstelle Settings Window und übernehme dessen UI
        self.settings_window = SettingsWindow(self, on_back_callback=self.show_calibration_select_view)
        
        # Kopiere das Central Widget vom Settings Window
        self.setCentralWidget(self.settings_window.centralWidget())
        self.setMenuBar(self.settings_window.menuBar())
        self.setStatusBar(self.settings_window.statusBar())
        self.setWindowTitle(self.settings_window.windowTitle())
    
    def show_calibration_select_view(self):
        """Zeige Calibration Select View im gleichen Fenster"""
        # Erstelle Calibration Select Window (ist ein QWidget, kein QMainWindow)
        self.calibration_select_window = CalibrationSelectWindow(
            self, 
            on_back_callback=self.show_main_view,
            on_settings_callback=self.show_settings_view,
            on_distortion_callback=self.show_distortion_calibration_view,
            on_perspective_callback=self.show_perspective_calibration_view,
            on_offset_callback=self.show_offset_calibration_view
        )
        
        # Setze das Widget als Central Widget
        self.setCentralWidget(self.calibration_select_window)
        self.setWindowTitle("Calibration Select")
    
    def show_distortion_calibration_view(self):
        """Zeige Distortion Calibration View im gleichen Fenster"""
        from caliDistortion import CalibrationDistortionWindow
        
        # Erstelle Distortion Calibration Window
        distortion_window = CalibrationDistortionWindow(
            self,
            on_back_callback=self.show_calibration_select_view
        )
        
        # Setze das Widget als Central Widget
        self.setCentralWidget(distortion_window)
        self.setWindowTitle("Distortion Calibration")
    
    def show_perspective_calibration_view(self):
        """Zeige Perspective Calibration View im gleichen Fenster"""
        from caliPerspective import CalibrationPerspectiveWindow
        
        # Erstelle Perspective Calibration Window
        perspective_window = CalibrationPerspectiveWindow()
        perspective_window.on_exit_callback = self.show_calibration_select_view
        # Don't set on_perspective_complete_callback - it would access deleted UI
        
        # Setze das Widget als Central Widget
        self.setCentralWidget(perspective_window)
        self.setWindowTitle("Perspective Calibration")
    
    def show_offset_calibration_view(self):
        """Zeige Offset Calibration View im gleichen Fenster"""
        from caliOffset import CalibrationOffsetWindow
        
        # Erstelle Offset Calibration Window
        offset_window = CalibrationOffsetWindow(
            self,
            on_back_callback=self.show_calibration_select_view
        )
        
        # Setze das Widget als Central Widget
        self.setCentralWidget(offset_window)
        
        # Entferne ALLE Margins und Spacing
        self.setContentsMargins(0, 0, 0, 0)
        if self.centralWidget():
            self.centralWidget().setContentsMargins(0, 0, 0, 0)
        if self.layout():
            self.layout().setContentsMargins(0, 0, 0, 0)
            self.layout().setSpacing(0)
        
        self.setWindowTitle("Offset Calibration")
        
    def on_camera_setup_clicked(self):
        """bCameraSetup: Wechsel zu Calibration Select View"""
        print("[LOG] Camera Setup button pressed")
        self.show_calibration_select_view()
    
    def on_mcu_setup_clicked(self):
        """bMCUSetup: Noch keine Funktion"""
        print("[LOG] MCU Setup button pressed - no function yet")
    
    def on_cnc_mode_clicked(self):
        """bCncMode: Noch keine Funktion"""
        print("[LOG] CNC Mode button pressed - no function yet")
    
    def on_exit_clicked(self):
        """bExit: Beende die Anwendung"""
        print("[LOG] Exit button pressed - closing app")
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Update debug flags from environment
    appSettings.update_debug_flags()

    # Load stylesheet if it exists (in res/ folder, one level up from src/)
    stylesheet_path = os.path.join(os.path.dirname(__file__), "..", "res", "styles.qss")
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, "r") as f:
            app.setStyleSheet(f.read())
            print(f"[LOG] Loaded stylesheet from {stylesheet_path}")
    else:
        print(f"[WARNING] Stylesheet not found at {stylesheet_path}")

    window = MainApp()

    # Use appSettings debug flag
    if appSettings.is_debug_mode():
        # Hole Screen-Größe aus Kalibrierungs-Einstellungen
        hardware_settings = appSettings.get_hardware_settings()
        screen_size = hardware_settings.get("screen_size", {"width": 640, "height": 480})
        screen_width = screen_size["width"]
        screen_height = screen_size["height"]

        print(f"[LOG] DEBUG_MODE aktiv - Fenster {screen_width}x{screen_height}, nicht Vollbild")
        window.setFixedSize(screen_width, screen_height)
        window.show()
    else:
        print("[LOG] Normal mode - Vollbild")
        window.showFullScreen()

    sys.exit(app.exec_())