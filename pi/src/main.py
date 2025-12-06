#!/usr/bin/env python3
"""
PyQt5 App mit Trennung von UI und Logik
- UI wird aus mainwindow.py geladen (pyuic5-generiert)
- Logik ist hier zentral implementiert
"""

import sys
import cv2  # Wird beim Start geladen (dauert ~16 Sekunden auf Pi)
import os
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt

# Importiere die auto-generierten UIs
from mainWin import Ui_MainWindow
from caliDevice import SettingsWindow, load_camera_settings, get_camera_id
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
        from caliDevice import set_selected_camera
        saved_settings = load_camera_settings()
        
        selected_cam_id = saved_settings.get("selected_camera")
        
        if selected_cam_id:
            # Versuche die zuletzt ausgewählte Kamera zu finden
            print(f"[LOG] Looking for previously selected camera: {selected_cam_id}")
            for i in range(10):
                video_path = f"/dev/video{i}"
                if os.path.exists(video_path):
                    camera_id = get_camera_id(i)
                    if camera_id == selected_cam_id:
                        set_selected_camera(i, camera_id)
                        print(f"[LOG] Loaded previously selected camera on startup: index={i}, id={camera_id}")
                        return
            
            print(f"[LOG] Previously selected camera not found")
        else:
            print("[LOG] No previously selected camera in settings")
        
    def update_camera_status(self):
        """Update Checkboxes mit Kamera-Status und MCU-Status"""
        from caliDevice import get_selected_camera
        
        # Lade gespeicherte Settings
        saved_settings = load_camera_settings()
        
        # Hole ausgewählte Kamera
        selected_index, selected_id = get_selected_camera()
        
        # Finde erste angeschlossene Kamera
        camera_found = False
        camera_with_settings = False
        camera_id = None
        display_name = "Camera"
        
        # Prüfe zuerst ob ausgewählte Kamera verfügbar ist
        if selected_index is not None and selected_id is not None:
            video_path = f"/dev/video{selected_index}"
            if os.path.exists(video_path):
                camera_found = True
                camera_id = selected_id
                if camera_id in saved_settings:
                    camera_with_settings = True
                    # Zeige kurze Version der ID
                    display_name = camera_id.split('_')[0] if '_' in camera_id else camera_id[:15]
        
        # Fallback: Suche nach irgendeiner Kamera
        if not camera_found:
            for i in range(10):
                video_path = f"/dev/video{i}"
                if os.path.exists(video_path):
                    camera_found = True
                    # Ermittle Kamera-ID
                    camera_id = get_camera_id(i)
                    
                    # Prüfe ob Settings vorhanden
                    if camera_id in saved_settings:
                        camera_with_settings = True
                        display_name = camera_id.split('_')[0] if '_' in camera_id else camera_id[:15]
                        break
        
        # Update cbCamera basierend auf Kamera-Status
        if not camera_found:
            # Fall 1: Keine Kamera gefunden - rot, unchecked
            self.main_ui.cbCamera.setChecked(False)
            self.main_ui.cbCamera.setText("No Camera")
            self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: red; }")
            print("[LOG] No camera found")
            
        elif camera_found and not camera_with_settings:
            # Fall 2: Unbekannte Kamera - gelb, unchecked
            self.main_ui.cbCamera.setChecked(False)
            self.main_ui.cbCamera.setText(f"{display_name}\nCalibrate!")
            self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: orange; }")
            print("[LOG] Camera found but no settings")
            
        elif camera_with_settings:
            # Fall 3: Bekannte Kamera - prüfe Kalibrierungs-Status
            
            # Lade Kalibrierungs-Daten
            camera_settings = saved_settings.get(camera_id, {})
            calibration_data = camera_settings.get("calibration", {})
            
            # Prüfe ob alle Kalibrierungen vorhanden sind
            has_geometric = "geometric" in calibration_data and calibration_data["geometric"]
            has_scale = "scale" in calibration_data and calibration_data["scale"]
            has_offset = "offset" in calibration_data and calibration_data["offset"]
            all_calibrated = has_geometric and has_scale and has_offset
            
            if all_calibrated:
                # Alle Kalibrierungen vorhanden - grün, checked
                self.main_ui.cbCamera.setChecked(True)
                self.main_ui.cbCamera.setText(f"{display_name}")
                self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: green; }")
                print(f"[LOG] Camera fully calibrated: {display_name}")
            else:
                # Nicht alle Kalibrierungen vorhanden - orange, unchecked
                self.main_ui.cbCamera.setChecked(False)
                self.main_ui.cbCamera.setText(f"{display_name}\nCalibrate")
                self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: orange; }")
                print(f"[LOG] Camera needs calibration: {display_name}")
        
        # MCU Status (Dummy - noch nicht implementiert)
        mcu_detected = False
        
        # Update cbMCU
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
        # bCameraSetup: Nur aktiv wenn Kamera erkannt
        self.main_ui.bCameraSetup.setEnabled(camera_found)
        
        # bMCUSetup: Nur aktiv wenn MCU erkannt
        self.main_ui.bMCUSetup.setEnabled(mcu_detected)
        
        # bCncMode: Nur aktiv wenn beide Checkboxen checked sind
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
    
    # Load stylesheet if it exists (in res/ folder, one level up from src/)
    stylesheet_path = os.path.join(os.path.dirname(__file__), "..", "res", "styles.qss")
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, "r") as f:
            app.setStyleSheet(f.read())
            print(f"[LOG] Loaded stylesheet from {stylesheet_path}")
    else:
        print(f"[WARNING] Stylesheet not found at {stylesheet_path}")
    
    window = MainApp()
    
    # Check für Debug-Modus (Laptop-Entwicklung)
    debug_mode = os.environ.get('DEBUG_MODE', '0') == '1'
    
    if debug_mode:
        print("[LOG] DEBUG_MODE aktiv - Fenster 640x480, nicht Vollbild")
        window.setFixedSize(640, 480)
        window.show()
    else:
        print("[LOG] Normal mode - Vollbild")
        window.showFullScreen()
    
    sys.exit(app.exec_())