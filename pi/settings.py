#!/usr/bin/env python3
"""
Settings Window Logik
- Verwaltet die Settings-View
- Trennung von UI (settingswindow.py) und Logik
"""

import os
import cv2
import subprocess
import re
import json
from PyQt5.QtWidgets import QMainWindow, QGraphicsScene, QGraphicsPixmapItem, QTreeWidgetItem
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap
from settingswindow import Ui_MainWindow as Ui_SettingsWindow


# Settings File Path
SETTINGS_FILE = "/home/flex/uis/camera_settings.json"


def get_camera_id(camera_index):
    """Ermittle eindeutige Kamera-ID (Serial Number oder USB Path)"""
    try:
        video_device = f"/dev/video{camera_index}"
        
        # Versuche Serial Number zu lesen
        result = subprocess.run(
            ['udevadm', 'info', '--query=property', '--name', video_device],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0:
            # Parse für ID_SERIAL oder ID_PATH
            serial = None
            path = None
            
            for line in result.stdout.split('\n'):
                if line.startswith('ID_SERIAL='):
                    serial = line.split('=', 1)[1]
                elif line.startswith('ID_PATH='):
                    path = line.split('=', 1)[1]
            
            # Bevorzuge Serial, sonst USB Path
            camera_id = serial or path or f"video{camera_index}"
            print(f"[LOG] Camera {camera_index} ID: {camera_id}")
            return camera_id
            
    except Exception as e:
        print(f"[ERROR] Could not get camera ID: {e}")
    
    # Fallback: Nutze video Index
    return f"video{camera_index}"


def load_camera_settings():
    """Lade gespeicherte Kamera-Einstellungen aus JSON"""
    if not os.path.exists(SETTINGS_FILE):
        print("[LOG] No settings file found, using defaults")
        return {}
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            print(f"[LOG] Loaded settings for {len(settings)} camera(s)")
            
            # Füge Standard calibration_settings hinzu falls nicht vorhanden
            if "calibration_settings" not in settings:
                settings["calibration_settings"] = get_default_calibration_settings()
                save_camera_settings(settings)
                print("[LOG] Added default calibration_settings to config")
            
            return settings
    except Exception as e:
        print(f"[ERROR] Could not load settings: {e}")
        return {}


def get_default_calibration_settings():
    """Gibt Standard-Kalibrierungs-Einstellungen zurück"""
    return {
        "checkerboard_boxes": {
            "x": 11,
            "y": 8
        },
        "checkerboard_dim": {
            "size_mm": 5
        }
    }


def get_calibration_settings():
    """Hole Kalibrierungs-Einstellungen aus Config"""
    settings = load_camera_settings()
    if "calibration_settings" in settings:
        return settings["calibration_settings"]
    return get_default_calibration_settings()


def save_camera_settings(settings):
    """Speichere Kamera-Einstellungen in JSON"""
    try:
        # Erstelle Verzeichnis falls nicht vorhanden
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"[LOG] Settings saved to {SETTINGS_FILE}")
        return True
    except Exception as e:
        print(f"[ERROR] Could not save settings: {e}")
        return False


class VideoThread(QThread):
    """Thread für Kamera-Capture (non-blocking)"""
    
    change_pixmap_signal = pyqtSignal(QImage)
    
    def __init__(self, camera_index=0, width=640, height=480, fps=30, fourcc=None):
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.fourcc = fourcc
        self._run_flag = True
        
    def run(self):
        """Haupt-Loop: Liest Frames und emitted Signals"""
        # Öffne Kamera mit V4L2 Backend (vermeidet GStreamer Warnungen)
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
        
        if not cap.isOpened():
            print(f"[ERROR] Could not open camera {self.camera_index}")
            return
        
        # Setze Format falls angegeben
        if self.fourcc is not None:
            cap.set(cv2.CAP_PROP_FOURCC, self.fourcc)
        
        # Setze Kamera-Eigenschaften
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Lese tatsächliche Werte zurück (kann von gewünschten abweichen)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(cap.get(cv2.CAP_PROP_FPS))
        
        print(f"[LOG] Camera {self.camera_index} opened: {actual_width}x{actual_height} @ {actual_fps}fps")
        
        while self._run_flag:
            ret, frame = cap.read()
            if ret:
                # Konvertiere BGR (OpenCV) zu RGB (Qt)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                # Erstelle QImage
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # Emitte Signal für GUI-Update
                self.change_pixmap_signal.emit(qt_image)
            else:
                print("[ERROR] Failed to read frame")
                break
                
        # Cleanup
        cap.release()
        print(f"[LOG] Camera {self.camera_index} released")
        
    def stop(self):
        """Stoppe den Thread sauber"""
        print("[LOG] Stopping video thread...")
        self._run_flag = False
        self.wait()  # Warte bis Thread beendet ist


class SettingsWindow(QMainWindow):
    """Settings Window mit Logik"""
    
    def __init__(self, parent=None, on_back_callback=None):
        super().__init__(parent)
        
        # Callback für Zurück-Button
        self.on_back_callback = on_back_callback
        
        # Setup UI
        self.ui = Ui_SettingsWindow()
        self.ui.setupUi(self)
        
        # Entferne alle Margins vom CentralWidget und Layout
        if self.centralWidget():
            self.centralWidget().setContentsMargins(0, 0, 0, 0)
            if self.centralWidget().layout():
                self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        
        # Graphics View Setup
        self.scene = QGraphicsScene()
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self.ui.gvCamera.setScene(self.scene)
        
        # Konfiguriere GraphicsView für Vollbildanzeige ohne Scrollbars
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        
        # Setze feste Höhe basierend auf Bildschirmgröße (minus etwas Platz für TreeView)
        # Für 480px Display: 480 - 200 (TreeView+Buttons) = 280px
        camera_height = screen.height() - 200
        self.ui.gvCamera.setMaximumHeight(camera_height)
        self.ui.gvCamera.setMinimumHeight(camera_height)
        
        # Deaktiviere Scrollbars
        from PyQt5.QtCore import Qt
        self.ui.gvCamera.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.gvCamera.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Bild soll abgeschnitten werden, nicht skaliert
        self.ui.gvCamera.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        # Entferne StatusBar (grauer Strich unten)
        self.setStatusBar(None)
        
        # Entferne MenuBar (falls vorhanden)
        self.setMenuBar(None)
        
        # Video Thread
        self.video_thread = None
        
        # Aktuelle Kamera-Einstellungen
        self.current_camera_index = None
        self.current_camera_id = None
        self.current_resolution = "640x480"
        self.current_fps = "30"
        self.current_format = "MJPEG"
        
        # Lade gespeicherte Settings
        self.saved_settings = load_camera_settings()
        
        # TreeWidget Items (Referenzen speichern)
        self.device_item = None
        self.resolution_item = None
        self.fps_item = None
        self.format_item = None
        
        # Initialisierung
        self.setup_connections()
        self.setup_tree_view()
        
        # Auto-load Kamera wenn Settings vorhanden
        self.auto_load_camera_with_settings()
        
        # Fenster-Titel
        self.setWindowTitle("Settings")
        
        print("[LOG] Settings view loaded")
    
    def auto_load_camera_with_settings(self):
        """Lade automatisch Kamera wenn Settings vorhanden sind"""
        # Suche nach angeschlossener Kamera mit Settings
        for i in range(10):
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                camera_id = get_camera_id(i)
                
                # Prüfe ob Settings für diese Kamera existieren
                if camera_id in self.saved_settings:
                    print(f"[LOG] Auto-loading camera {i} with saved settings")
                    
                    # Setze Kamera-Index und ID
                    self.current_camera_index = i
                    self.current_camera_id = camera_id
                    
                    # Lese Capabilities
                    capabilities = self.get_camera_capabilities(i)
                    self.camera_capabilities = capabilities
                    
                    # Aktiviere und fülle TreeView
                    self.populate_format_options(capabilities)
                    self.resolution_item.setDisabled(False)
                    self.fps_item.setDisabled(False)
                    self.format_item.setDisabled(False)
                    
                    # Lade gespeicherte Settings
                    saved = self.saved_settings[camera_id]
                    self.current_format = saved.get('format', list(capabilities.keys())[0])
                    self.current_resolution = saved.get('resolution', list(capabilities[self.current_format].keys())[0])
                    self.current_fps = str(saved.get('fps', capabilities[self.current_format][self.current_resolution][0]))
                    
                    # Update TreeView
                    self.update_resolution_fps_for_format(self.current_format)
                    
                    # Markiere ausgewählte Kamera im TreeView
                    self.select_camera_in_tree(i)
                    
                    # Starte Kamera
                    self.start_camera_with_settings()
                    
                    # Nur erste Kamera mit Settings laden
                    break
    
    def select_camera_in_tree(self, camera_index):
        """Markiere Kamera im TreeView als ausgewählt"""
        # Suche nach dem entsprechenden Item
        for i in range(self.device_item.childCount()):
            child = self.device_item.child(i)
            if f"Camera {camera_index}" in child.text(0):
                # Setze als current item (markiert)
                self.ui.tvSettings.setCurrentItem(child)
                break
        
    def on_tree_item_clicked(self, item, column):
        """Callback wenn TreeView Item geklickt wird"""
        item_type = item.data(0, Qt.UserRole)
        item_text = item.text(0)
        
        # Wenn Parent-Item geklickt wird (Device, Resolution, FPS, Format)
        # dann toggle expand/collapse
        if item_type is None:  # Parent items haben kein UserRole
            if item.isExpanded():
                item.setExpanded(False)
            else:
                item.setExpanded(True)
            return  # Nicht weiter verarbeiten
        
        # Ab hier: nur Child-Items
        if item_type == "device":
            # Kamera wurde ausgewählt
            # Extrahiere Camera Index (z.B. "Camera 0 (/dev/video0)" -> 0)
            if "Camera" in item_text and "No cameras" not in item_text:
                try:
                    camera_index = int(item_text.split()[1])
                    self.current_camera_index = camera_index
                    
                    # Ermittle Kamera-ID
                    self.current_camera_id = get_camera_id(camera_index)
                    print(f"[LOG] Camera {camera_index} selected (ID: {self.current_camera_id})")
                    
                    # Lese Kamera-Capabilities mit v4l2-ctl
                    capabilities = self.get_camera_capabilities(camera_index)
                    self.camera_capabilities = capabilities
                    
                    # Aktiviere und fülle andere Tree Items mit tatsächlichen Werten
                    self.populate_format_options(capabilities)
                    self.resolution_item.setDisabled(False)
                    self.fps_item.setDisabled(False)
                    self.format_item.setDisabled(False)
                    
                    # Prüfe ob gespeicherte Settings für diese Kamera existieren
                    if self.current_camera_id in self.saved_settings:
                        saved = self.saved_settings[self.current_camera_id]
                        print(f"[LOG] Loading saved settings for camera: {saved}")
                        
                        # Restore gespeicherte Werte
                        self.current_format = saved.get('format', list(capabilities.keys())[0])
                        self.current_resolution = saved.get('resolution', list(capabilities[self.current_format].keys())[0])
                        self.current_fps = str(saved.get('fps', capabilities[self.current_format][self.current_resolution][0]))
                        
                        # Update TreeView mit gespeicherten Werten
                        self.update_resolution_fps_for_format(self.current_format)
                    else:
                        # Wähle erstes verfügbares Format als Default
                        if capabilities:
                            first_format = list(capabilities.keys())[0]
                            self.current_format = first_format
                            
                            # Wähle erste verfügbare Auflösung
                            if capabilities[first_format]:
                                first_resolution = list(capabilities[first_format].keys())[0]
                                self.current_resolution = first_resolution
                                
                                # Wähle erste verfügbare FPS
                                if capabilities[first_format][first_resolution]:
                                    first_fps = str(capabilities[first_format][first_resolution][0])
                                    self.current_fps = first_fps
                    
                    # Starte Kamera
                    self.start_camera_with_settings()
                    
                except (IndexError, ValueError) as e:
                    print(f"[ERROR] Could not parse camera index: {e}")
                    
        elif item_type == "resolution":
            # Resolution wurde ausgewählt
            self.current_resolution = item_text
            print(f"[LOG] Resolution changed to {item_text}")
            
            # Update FPS Optionen basierend auf Format und Resolution
            if self.current_camera_index is not None and hasattr(self, 'camera_capabilities'):
                self.update_fps_for_resolution(self.current_format, item_text)
            
            if self.current_camera_index is not None:
                self.start_camera_with_settings()
                
        elif item_type == "fps":
            # FPS wurde ausgewählt
            self.current_fps = item_text
            print(f"[LOG] FPS changed to {item_text}")
            if self.current_camera_index is not None:
                self.start_camera_with_settings()
                
        elif item_type == "format":
            # Format wurde ausgewählt
            self.current_format = item_text
            print(f"[LOG] Format changed to {item_text}")
            
            # Update Resolution und FPS Optionen basierend auf gewähltem Format
            if self.current_camera_index is not None and hasattr(self, 'camera_capabilities'):
                self.update_resolution_fps_for_format(item_text)
            
            if self.current_camera_index is not None:
                self.start_camera_with_settings()
    
    def populate_format_options(self, capabilities):
        """Fülle TreeView mit tatsächlich unterstützten Optionen"""
        # Lösche alte Format-Children
        self.format_item.takeChildren()
        
        # Füge unterstützte Formate hinzu
        for fmt in capabilities.keys():
            fmt_child = QTreeWidgetItem(self.format_item, [fmt])
            fmt_child.setData(0, Qt.UserRole, "format")
            self.set_item_height(fmt_child)
        
        # Fülle Resolution und FPS für erstes Format
        if capabilities:
            first_format = list(capabilities.keys())[0]
            self.update_resolution_fps_for_format(first_format)
    
    def update_resolution_fps_for_format(self, selected_format):
        """Update Resolution und FPS basierend auf gewähltem Format"""
        if not hasattr(self, 'camera_capabilities'):
            return
        
        capabilities = self.camera_capabilities
        if selected_format not in capabilities:
            return
        
        # Lösche alte Resolution-Children
        self.resolution_item.takeChildren()
        
        # Füge unterstützte Resolutions für dieses Format hinzu
        resolutions = capabilities[selected_format]
        for res in resolutions.keys():
            res_child = QTreeWidgetItem(self.resolution_item, [res])
            res_child.setData(0, Qt.UserRole, "resolution")
            self.set_item_height(res_child)
        
        # Update FPS für erste Resolution
        if resolutions:
            first_resolution = list(resolutions.keys())[0]
            self.update_fps_for_resolution(selected_format, first_resolution)
            
            # Setze current_resolution falls noch nicht gesetzt
            if not hasattr(self, 'current_resolution') or self.current_resolution not in resolutions:
                self.current_resolution = first_resolution
    
    def update_fps_for_resolution(self, selected_format, selected_resolution):
        """Update FPS basierend auf Format und Resolution"""
        if not hasattr(self, 'camera_capabilities'):
            return
        
        capabilities = self.camera_capabilities
        if selected_format not in capabilities:
            return
        if selected_resolution not in capabilities[selected_format]:
            return
        
        # Lösche alte FPS-Children
        self.fps_item.takeChildren()
        
        # Füge unterstützte FPS für diese Kombination hinzu
        fps_list = capabilities[selected_format][selected_resolution]
        for fps in fps_list:
            fps_child = QTreeWidgetItem(self.fps_item, [str(fps)])
            fps_child.setData(0, Qt.UserRole, "fps")
            self.set_item_height(fps_child)
        
        # Setze current_fps falls noch nicht gesetzt
        if fps_list and (not hasattr(self, 'current_fps') or int(self.current_fps) not in fps_list):
            self.current_fps = str(fps_list[0])
    
    def setup_touchscreen_friendly_ui(self):
        """Passe UI für Touchscreen an (größere Elemente)"""
        # Styles werden jetzt über styles.qss gesteuert
        print("[LOG] Touchscreen-friendly UI configured (via stylesheet)")
        
    def setup_connections(self):
        """Verbinde UI-Elemente mit Logik"""
        self.ui.bCancel.clicked.connect(self.on_back_clicked)
        self.ui.bOk.clicked.connect(self.on_back_clicked)
        self.ui.tvSettings.itemClicked.connect(self.on_tree_item_clicked)
    
    def set_item_height(self, item):
        """Setze feste Höhe für TreeWidget Item"""
        from PyQt5.QtCore import QSize
        item.setSizeHint(0, QSize(0, 44))
        
    def setup_tree_view(self):
        """Erstelle TreeView Struktur"""
        # Clear existing items
        self.ui.tvSettings.clear()
        
        # Styling wird jetzt über styles.qss gesteuert
        
        # Setze Item-Höhe einheitlich
        self.ui.tvSettings.setUniformRowHeights(True)
        
        # Aktiviere Expand on Click für Parent-Items
        self.ui.tvSettings.setExpandsOnDoubleClick(False)  # Nicht bei Doppelklick
        
        # Device (Camera) - am Anfang expanded
        self.device_item = QTreeWidgetItem(self.ui.tvSettings, ["📷 Device"])
        self.device_item.setExpanded(True)
        self.set_item_height(self.device_item)
        
        # Lade verfügbare Kameras
        cameras = self.get_available_cameras()
        for camera_name in cameras:
            camera_child = QTreeWidgetItem(self.device_item, [camera_name])
            camera_child.setData(0, Qt.UserRole, "device")  # Tag für Identifikation
            self.set_item_height(camera_child)
        
        # Resolution - am Anfang collapsed und disabled
        self.resolution_item = QTreeWidgetItem(self.ui.tvSettings, ["📐 Resolution"])
        self.resolution_item.setExpanded(False)
        self.resolution_item.setDisabled(True)
        self.set_item_height(self.resolution_item)
        resolutions = ["640x480", "800x600", "1280x720", "1920x1080"]
        for res in resolutions:
            res_child = QTreeWidgetItem(self.resolution_item, [res])
            res_child.setData(0, Qt.UserRole, "resolution")
            self.set_item_height(res_child)
        
        # FPS - am Anfang collapsed und disabled
        self.fps_item = QTreeWidgetItem(self.ui.tvSettings, ["🎬 FPS"])
        self.fps_item.setExpanded(False)
        self.fps_item.setDisabled(True)
        self.set_item_height(self.fps_item)
        fps_options = ["15", "30", "60"]
        for fps in fps_options:
            fps_child = QTreeWidgetItem(self.fps_item, [fps])
            fps_child.setData(0, Qt.UserRole, "fps")
            self.set_item_height(fps_child)
        
        # Format - am Anfang collapsed und disabled
        self.format_item = QTreeWidgetItem(self.ui.tvSettings, ["🎨 Format"])
        self.format_item.setExpanded(False)
        self.format_item.setDisabled(True)
        self.set_item_height(self.format_item)
        formats = ["MJPEG", "YUYV", "H264"]
        for fmt in formats:
            fmt_child = QTreeWidgetItem(self.format_item, [fmt])
            fmt_child.setData(0, Qt.UserRole, "format")
            self.set_item_height(fmt_child)
        
        print("[LOG] TreeView setup complete")
        
    def get_available_cameras(self):
        """Findet alle verfügbaren Kameras"""
        available_cameras = []
        
        # Prüfe /dev/video* Geräte - nur Existenz, kein Test
        # Test beim ersten Start wäre zu langsam
        for i in range(10):  # Prüfe video0 bis video9
            video_path = f"/dev/video{i}"
            if os.path.exists(video_path):
                available_cameras.append(f"Camera {i} ({video_path})")
                print(f"[LOG] Found video device: {video_path}")
        
        # Falls keine Kameras gefunden, füge Platzhalter hinzu
        if not available_cameras:
            available_cameras.append("No cameras detected")
            
        return available_cameras
    
    def get_camera_capabilities(self, camera_index):
        """Lese unterstützte Formate, Auflösungen und FPS mit v4l2-ctl"""
        try:
            video_device = f"/dev/video{camera_index}"
            
            # Führe v4l2-ctl aus
            result = subprocess.run(
                ['v4l2-ctl', '--device', video_device, '--list-formats-ext'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print(f"[ERROR] v4l2-ctl failed: {result.stderr}")
                return self.get_default_capabilities()
            
            # Parse die Ausgabe
            output = result.stdout
            formats = {}
            current_format = None
            current_resolution = None
            
            for line in output.split('\n'):
                # Format-Zeile: "[0]: 'MJPG' (Motion-JPEG, compressed)"
                format_match = re.search(r"\[(\d+)\]:\s+'([^']+)'", line)
                if format_match:
                    current_format = format_match.group(2)
                    formats[current_format] = {}
                    continue
                
                # Auflösungs-Zeile: "Size: Discrete 640x480"
                size_match = re.search(r"Size:\s+Discrete\s+(\d+)x(\d+)", line)
                if size_match and current_format:
                    width = size_match.group(1)
                    height = size_match.group(2)
                    current_resolution = f"{width}x{height}"
                    formats[current_format][current_resolution] = []
                    continue
                
                # FPS-Zeile: "Interval: Discrete 0.033s (30.000 fps)"
                fps_match = re.search(r"Interval:.*?\((\d+(?:\.\d+)?)\s+fps\)", line)
                if fps_match and current_format and current_resolution:
                    fps = int(float(fps_match.group(1)))
                    if fps not in formats[current_format][current_resolution]:
                        formats[current_format][current_resolution].append(fps)
            
            print(f"[LOG] Camera {camera_index} capabilities: {formats}")
            return formats
            
        except subprocess.TimeoutExpired:
            print(f"[ERROR] v4l2-ctl timeout")
            return self.get_default_capabilities()
        except FileNotFoundError:
            print(f"[ERROR] v4l2-ctl not found - install with: sudo apt install v4l-utils")
            return self.get_default_capabilities()
        except Exception as e:
            print(f"[ERROR] Could not read camera capabilities: {e}")
            return self.get_default_capabilities()
    
    def get_default_capabilities(self):
        """Fallback: Standard-Capabilities wenn v4l2-ctl nicht verfügbar"""
        return {
            'MJPG': {
                '640x480': [15, 30],
                '1280x720': [15, 30],
                '1920x1080': [15, 30]
            },
            'YUYV': {
                '640x480': [15, 30],
                '1280x720': [15, 30]
            }
        }
        
    def load_cameras(self):
        """Lade verfügbare Kameras in ComboBox"""
        cameras = self.get_available_cameras()
        self.ui.cCamera.clear()
        self.ui.cCamera.addItems(cameras)
        print(f"[LOG] Loaded {len(cameras)} camera(s)")
        
    def populate_default_settings(self):
        """Fülle FPS, Resolution und Format ComboBoxen mit Standard-Werten"""
        # Standard Resolutionen
        resolutions = ["320x240", "640x480", "800x600", "1280x720", "1920x1080"]
        self.ui.cResolution.clear()
        self.ui.cResolution.addItems(resolutions)
        self.ui.cResolution.setCurrentText("640x480")  # Default
        
        # Standard FPS
        fps_options = ["15", "30", "60"]
        self.ui.cFps.clear()
        self.ui.cFps.addItems(fps_options)
        self.ui.cFps.setCurrentText("30")  # Default
        
        # Standard Formate (für später, aktuell nur Info)
        formats = ["MJPEG", "YUYV", "H264"]
        self.ui.cFormat.clear()
        self.ui.cFormat.addItems(formats)
        self.ui.cFormat.setCurrentText("MJPEG")  # Default
        
    def get_current_camera_settings(self, camera_index):
        """Lese aktuelle Kamera-Einstellungen"""
        try:
            # Nutze V4L2 Backend direkt
            cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                cap.release()
                
                print(f"[LOG] Current settings: {width}x{height} @ {fps}fps")
                return width, height, fps
        except Exception as e:
            print(f"[ERROR] Could not read camera settings: {e}")
        
        return 640, 480, 30  # Fallback
    
    def start_camera_with_settings(self):
        """Starte Kamera mit aktuellen Einstellungen"""
        if self.current_camera_index is None:
            return
            
        # Parse Resolution (z.B. "640x480" -> 640, 480)
        try:
            width, height = map(int, self.current_resolution.split('x'))
        except ValueError:
            width, height = 640, 480
            print(f"[ERROR] Invalid resolution: {self.current_resolution}, using default")
        
        # Parse FPS
        try:
            fps = int(self.current_fps)
        except ValueError:
            fps = 30
            print(f"[ERROR] Invalid FPS, using default")
        
        # Format zu FOURCC Code
        format_fourcc = None
        if self.current_format == 'MJPG':
            format_fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        elif self.current_format == 'YUYV':
            format_fourcc = cv2.VideoWriter_fourcc(*'YUYV')
        elif self.current_format == 'H264':
            format_fourcc = cv2.VideoWriter_fourcc(*'H264')
        
        print(f"[LOG] Starting camera {self.current_camera_index} with {width}x{height} @ {fps}fps ({self.current_format})")
        
        # Stoppe vorherige Kamera falls aktiv
        self.stop_camera()
        
        # Erstelle und starte Video Thread mit Einstellungen
        self.video_thread = VideoThread(self.current_camera_index, width, height, fps, format_fourcc)
        self.video_thread.change_pixmap_signal.connect(self.update_image)
        self.video_thread.start()
    
    def stop_camera(self):
        """Stoppe Kamera-Stream"""
        if self.video_thread is not None:
            self.video_thread.stop()
            self.video_thread = None
            print("[LOG] Camera stopped")
            
    def update_image(self, qt_image):
        """Update das QGraphicsView mit neuem Frame"""
        pixmap = QPixmap.fromImage(qt_image)
        self.pixmap_item.setPixmap(pixmap)
        
        # Fit in View beim ersten Frame
        if self.scene.sceneRect().isEmpty():
            self.ui.gvCamera.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def on_back_clicked(self):
        """bCancel/bOk: Zurück zur Main-View"""
        sender = self.sender()
        
        # Wenn OK geklickt wurde, speichere Settings
        if sender == self.ui.bOk and self.current_camera_id:
            self.save_current_camera_settings()
        
        print("[LOG] Cancel/OK button pressed - returning to main view")
        
        # Stoppe Kamera vor dem Verlassen
        self.stop_camera()
        
        if self.on_back_callback:
            self.on_back_callback()
    
    def save_current_camera_settings(self):
        """Speichere aktuelle Kamera-Einstellungen"""
        if not self.current_camera_id:
            return
        
        # Aktualisiere Settings Dictionary
        self.saved_settings[self.current_camera_id] = {
            'device': self.current_camera_index,
            'format': self.current_format,
            'resolution': self.current_resolution,
            'fps': int(self.current_fps),
            'calibration': {}  # Platzhalter für später
        }
        
        # Speichere in Datei
        if save_camera_settings(self.saved_settings):
            print(f"[LOG] Saved settings for camera {self.current_camera_id}")
        else:
            print(f"[ERROR] Failed to save settings")
