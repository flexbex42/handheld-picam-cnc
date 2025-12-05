#!/usr/bin/env python3
"""
Calibration Select Window Logik
- Auswahl verschiedener Kalibrierungs-Optionen
- Zugriff auf Settings
"""

import os
from PyQt5.QtWidgets import QWidget
from caliSelectWin import Ui_Form as Ui_CalibrationSelectWindow
from settings import load_camera_settings, get_camera_id
from caliDistortion import CalibrationDistortionWindow


class CalibrationSelectWindow(QWidget):
    """Calibration Select Window mit Logik"""
    
    def __init__(self, parent=None, on_back_callback=None, on_settings_callback=None, on_distortion_callback=None, on_perspective_callback=None, on_offset_callback=None):
        super().__init__(parent)
        
        # Callbacks
        self.on_back_callback = on_back_callback
        self.on_settings_callback = on_settings_callback
        self.on_distortion_callback = on_distortion_callback
        self.on_perspective_callback = on_perspective_callback
        self.on_offset_callback = on_offset_callback
        
        # Setup UI
        self.ui = Ui_CalibrationSelectWindow()
        self.ui.setupUi(self)
        
        # Entferne alle Margins vom Widget und Layout
        self.setContentsMargins(0, 0, 0, 0)
        if self.layout():
            self.layout().setContentsMargins(0, 0, 0, 0)
        
        # Setup Connections
        self.setup_connections()
        
        # Update Kamera-Status in Checkboxen
        self.update_camera_status()
        
        # Fenster-Titel
        self.setWindowTitle("Calibration Select")
        
        print("[LOG] Calibration Select view loaded")
        
    def setup_connections(self):
        """Verbinde UI-Elemente mit Logik"""
        self.ui.bBack.clicked.connect(self.on_back_clicked)
        self.ui.bDevice.clicked.connect(self.on_device_clicked)
        self.ui.bCDistortion.clicked.connect(self.on_distortion_clicked)
        self.ui.bCPerspective.clicked.connect(self.on_perspective_clicked)
        self.ui.bCOffset.clicked.connect(self.on_offset_clicked)
        self.ui.bCTest.clicked.connect(self.on_test_clicked)
    
    def update_camera_status(self):
        """Update Checkboxen mit Kamera-Status und Kalibrierungs-Status"""
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
        
        # MCU Status (Dummy - noch nicht implementiert)
        mcu_detected = False
        mcu_calibrated = False  # Wird später implementiert
        
        # Kalibrierungs-Status Variablen
        has_geometric = False
        has_scale = False
        has_offset = False
        
        # Status-Update basierend auf Kamera-Status
        if not camera_found:
            # Fall 1: Keine Kamera gefunden - nur cbSettings sichtbar, rot
            self.ui.cbSettings.setVisible(True)
            self.ui.cbSettings.setChecked(False)
            self.ui.cbSettings.setText("No Camera")
            self.ui.cbSettings.setStyleSheet("QCheckBox { color: red; }")
            
            # Verstecke alle anderen Checkboxen
            self.ui.cbGeometric.setVisible(False)
            self.ui.cbSize.setVisible(False)
            self.ui.cbOffset.setVisible(False)
            
            print("[LOG] No camera found")
            
        elif camera_found and not camera_with_settings:
            # Fall 2: Unbekannte Kamera - nur cbSettings sichtbar, gelb
            self.ui.cbSettings.setVisible(True)
            self.ui.cbSettings.setChecked(False)
            self.ui.cbSettings.setText("Setup Camera")
            self.ui.cbSettings.setStyleSheet("QCheckBox { color: orange; }")
            
            # Verstecke alle anderen Checkboxen
            self.ui.cbGeometric.setVisible(False)
            self.ui.cbSize.setVisible(False)
            self.ui.cbOffset.setVisible(False)
            
            print("[LOG] Camera found but no settings")
            
        elif camera_with_settings:
            # Fall 3: Bekannte Kamera - alle Checkboxen sichtbar, grün
            camera_name = camera_id[:15]  # Max 15 Zeichen
            
            # cbSettings - grün, checked
            self.ui.cbSettings.setVisible(True)
            self.ui.cbSettings.setChecked(True)
            self.ui.cbSettings.setText(f"Camera: {camera_name}")
            self.ui.cbSettings.setStyleSheet("QCheckBox { color: green; }")
            
            # Zeige alle anderen Checkboxen
            self.ui.cbGeometric.setVisible(True)
            self.ui.cbSize.setVisible(True)
            self.ui.cbOffset.setVisible(True)
            
            # Lade Kalibrierungs-Daten
            camera_settings = saved_settings.get(camera_id, {})
            calibration_data = camera_settings.get("calibration", {})
            
            # Update cbGeometric
            if "geometric" in calibration_data and calibration_data["geometric"]:
                self.ui.cbGeometric.setChecked(True)
                self.ui.cbGeometric.setText("Geometric: OK")
                self.ui.cbGeometric.setStyleSheet("QCheckBox { color: green; }")
                has_geometric = True
            else:
                self.ui.cbGeometric.setChecked(False)
                self.ui.cbGeometric.setText("Calibrate Geometric")
                self.ui.cbGeometric.setStyleSheet("QCheckBox { color: orange; }")
            
            # Update cbSize (prüft auf perspective calibration)
            if "perspective" in calibration_data and calibration_data["perspective"]:
                self.ui.cbSize.setChecked(True)
                self.ui.cbSize.setText("Perspective: OK")
                self.ui.cbSize.setStyleSheet("QCheckBox { color: green; }")
                has_scale = True
            else:
                self.ui.cbSize.setChecked(False)
                self.ui.cbSize.setText("Calibrate Perspective")
                self.ui.cbSize.setStyleSheet("QCheckBox { color: orange; }")
            
            # Update cbOffset
            if "offset" in calibration_data and calibration_data["offset"]:
                self.ui.cbOffset.setChecked(True)
                self.ui.cbOffset.setText("Offset: OK")
                self.ui.cbOffset.setStyleSheet("QCheckBox { color: green; }")
                has_offset = True
            else:
                self.ui.cbOffset.setChecked(False)
                self.ui.cbOffset.setText("Calibrate Offset")
                self.ui.cbOffset.setStyleSheet("QCheckBox { color: orange; }")
            
            print(f"[LOG] Camera found with settings: {camera_name}")
        
        # Disable alle Checkboxen (nur Status-Anzeige)
        self.ui.cbSettings.setEnabled(False)
        self.ui.cbGeometric.setEnabled(False)
        self.ui.cbSize.setEnabled(False)
        self.ui.cbOffset.setEnabled(False)
        
        # Force Style-Update für alle sichtbaren Checkboxen
        for cb in [self.ui.cbSettings, self.ui.cbGeometric, 
                   self.ui.cbSize, self.ui.cbOffset]:
            if cb.isVisible():
                cb.style().unpolish(cb)
                cb.style().polish(cb)
        
        # ===== Button Aktivierung/Deaktivierung =====
        # bDevice und bBack sind immer aktiv
        self.ui.bDevice.setEnabled(True)
        self.ui.bBack.setEnabled(True)
        
        # bCDistortion: Aktiv wenn Kamera Profil gespeichert ist und Kamera angeschlossen ist (cbSettings checked)
        self.ui.bCDistortion.setEnabled(camera_with_settings and camera_found)
        
        # bCPerspective: Aktiv wenn Geometric-Daten vorhanden sind
        self.ui.bCPerspective.setEnabled(has_geometric)
        
        # bCOffset: Aktiv wenn MCU detected & calibrated, und alle vorherigen Punkte true
        # DEBUG: Auch ohne MCU aktivieren wenn Geometric und Scale vorhanden
        self.ui.bCOffset.setEnabled((mcu_detected and mcu_calibrated and has_geometric and has_scale) or (has_geometric and has_scale))
        
        # bCTest: Aktiv wenn alle Punkte außer MCU true sind
        self.ui.bCTest.setEnabled(camera_with_settings and has_geometric and has_scale)
        
    def on_back_clicked(self):
        """bBack: Zurück zum Main Window"""
        print("[LOG] Back button pressed - returning to main view")
        
        if self.on_back_callback:
            self.on_back_callback()
            
    def on_device_clicked(self):
        """bDevice: Öffne Device/Settings Window"""
        print("[LOG] Device button pressed - opening device settings")
        
        if self.on_settings_callback:
            self.on_settings_callback()
    
    def on_distortion_clicked(self):
        """bCDistortion: Öffne Distortion Calibration"""
        print("[LOG] Distortion Calibration button pressed")
        
        if self.on_distortion_callback:
            self.on_distortion_callback()
    
    def on_perspective_clicked(self):
        """bCPerspective: Öffne Perspective Calibration"""
        print("[LOG] Perspective Calibration button pressed")
        if self.on_perspective_callback:
            self.on_perspective_callback()
    
    def on_offset_clicked(self):
        """bCOffset: Öffne Offset Calibration"""
        print("[LOG] Offset Calibration button pressed")
        if self.on_offset_callback:
            self.on_offset_callback()
    
    def on_test_clicked(self):
        """bCTest: Öffne Test Mode"""
        print("[LOG] Test button pressed - no function yet")
