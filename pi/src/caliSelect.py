#!/usr/bin/env python3
"""
Calibration Select Window Logik
- Auswahl verschiedener Kalibrierungs-Optionen
- Zugriff auf Settings
"""

import os
from PyQt5.QtWidgets import QWidget
from caliSelectWin import Ui_Form as Ui_CalibrationSelectWindow
import appSettings
import camera
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
        
        saved_settings = appSettings.load_app_settings()
        result = camera.update_active_camera_info()
        mcu_detected = False
        mcu_calibrated = False  # Wird später implementiert
        has_geometric = False
        has_scale = False
        has_offset = False
        if result is None:
            # Fall 1: Keine Kamera gefunden - nur cbSettings sichtbar, rot
            self.ui.cbSettings.setVisible(True)
            self.ui.cbSettings.setChecked(False)
            self.ui.cbSettings.setText("No Camera")
            self.ui.cbSettings.setStyleSheet("QCheckBox { color: red; }")
            self.ui.cbGeometric.setVisible(False)
            self.ui.cbSize.setVisible(False)
            self.ui.cbOffset.setVisible(False)
            print("[LOG] No camera found")
            camera_with_settings = False
        else:
            camera_id, device_number = result
            display_name = camera_id.split('_')[0] if '_' in camera_id else camera_id[:15]
            camera_settings = saved_settings.get(camera_id, {})
            calibration_data = camera_settings.get("calibration", {})
            camera_with_settings = camera_id in saved_settings
            # Fall 2/3: Kamera gefunden
            if not camera_with_settings:
                # Unbekannte Kamera - nur cbSettings sichtbar, gelb
                self.ui.cbSettings.setVisible(True)
                self.ui.cbSettings.setChecked(False)
                self.ui.cbSettings.setText("Setup Camera")
                self.ui.cbSettings.setStyleSheet("QCheckBox { color: orange; }")
                self.ui.cbGeometric.setVisible(False)
                self.ui.cbSize.setVisible(False)
                self.ui.cbOffset.setVisible(False)
                print("[LOG] Camera found but no settings")
            else:
                # Bekannte Kamera - alle Checkboxen sichtbar, grün
                self.ui.cbSettings.setVisible(True)
                self.ui.cbSettings.setChecked(True)
                self.ui.cbSettings.setText(f"{display_name}")
                self.ui.cbSettings.setStyleSheet("QCheckBox { color: green; }")
                self.ui.cbGeometric.setVisible(True)
                self.ui.cbSize.setVisible(True)
                self.ui.cbOffset.setVisible(True)
                # Geometric
                if "geometric" in calibration_data and calibration_data["geometric"]:
                    self.ui.cbGeometric.setChecked(True)
                    self.ui.cbGeometric.setText("Geometric: OK")
                    self.ui.cbGeometric.setStyleSheet("QCheckBox { color: green; }")
                    has_geometric = True
                else:
                    self.ui.cbGeometric.setChecked(False)
                    self.ui.cbGeometric.setText("Calibrate Geometric")
                    self.ui.cbGeometric.setStyleSheet("QCheckBox { color: orange; }")
                # Perspective
                perspective = calibration_data.get("perspective", None)
                if perspective:
                    self.ui.cbSize.setChecked(True)
                    self.ui.cbSize.setText("Perspective: OK")
                    self.ui.cbSize.setStyleSheet("QCheckBox { color: green; }")
                    has_scale = True
                else:
                    self.ui.cbSize.setChecked(False)
                    self.ui.cbSize.setText("Calibrate Perspective")
                    self.ui.cbSize.setStyleSheet("QCheckBox { color: orange; }")
                # Offset
                if "offset" in calibration_data and calibration_data["offset"]:
                    self.ui.cbOffset.setChecked(True)
                    self.ui.cbOffset.setText("Offset: OK")
                    self.ui.cbOffset.setStyleSheet("QCheckBox { color: green; }")
                    has_offset = True
                else:
                    self.ui.cbOffset.setChecked(False)
                    self.ui.cbOffset.setText("Calibrate Offset")
                    self.ui.cbOffset.setStyleSheet("QCheckBox { color: orange; }")
                print(f"[LOG] Camera found with settings: {display_name}")
        # Disable alle Checkboxen (nur Status-Anzeige)
        self.ui.cbSettings.setEnabled(False)
        self.ui.cbGeometric.setEnabled(False)
        self.ui.cbSize.setEnabled(False)
        self.ui.cbOffset.setEnabled(False)
        # Force Style-Update für alle sichtbaren Checkboxen
        for cb in [self.ui.cbSettings, self.ui.cbGeometric, self.ui.cbSize, self.ui.cbOffset]:
            if cb.isVisible():
                cb.style().unpolish(cb)
                cb.style().polish(cb)
        # ===== Button Aktivierung/Deaktivierung =====
        self.ui.bDevice.setEnabled(True)
        self.ui.bBack.setEnabled(True)
        self.ui.bCDistortion.setEnabled(camera_with_settings and result is not None)
        self.ui.bCPerspective.setEnabled(has_geometric)
        self.ui.bCOffset.setEnabled((mcu_detected and mcu_calibrated and has_geometric and has_scale) or (has_geometric and has_scale))
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
