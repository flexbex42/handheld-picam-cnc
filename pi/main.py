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
from settings import SettingsWindow, load_camera_settings, get_camera_id
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
        
        # Zeige normale UI
        self.show_main_view()
        
    def update_camera_status(self):
        """Update Checkboxes mit Kamera-Status und MCU-Status"""
        # Lade gespeicherte Settings
        saved_settings = load_camera_settings()
        
        # Finde erste angeschlossene Kamera
        camera_found = False
        camera_with_settings = False
        camera_id = None
        
        for i in range(10):
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                camera_found = True
                # Ermittle Kamera-ID
                camera_id = get_camera_id(i)
                
                # Prüfe ob Settings vorhanden
                if camera_id in saved_settings:
                    camera_with_settings = True
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
            self.main_ui.cbCamera.setText("Camera: unknown\nCalibrate!")
            self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: orange; }")
            print("[LOG] Camera found but no settings")
            
        elif camera_with_settings:
            # Fall 3: Bekannte Kamera - prüfe Kalibrierungs-Status
            camera_name = camera_id[:15]  # Max 15 Zeichen
            
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
                self.main_ui.cbCamera.setText(f"Camera: {camera_name}")
                self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: green; }")
                print(f"[LOG] Camera fully calibrated: {camera_name}")
            else:
                # Nicht alle Kalibrierungen vorhanden - orange, unchecked
                self.main_ui.cbCamera.setChecked(False)
                self.main_ui.cbCamera.setText(f"Camera: {camera_name}\nCalibrate")
                self.main_ui.cbCamera.setStyleSheet("QCheckBox { color: orange; }")
                print(f"[LOG] Camera needs calibration: {camera_name}")
        
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
    
    # Load stylesheet if it exists
    stylesheet_path = os.path.join(os.path.dirname(__file__), "styles.qss")
    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, "r") as f:
            app.setStyleSheet(f.read())
            print(f"[LOG] Loaded stylesheet from {stylesheet_path}")
    
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