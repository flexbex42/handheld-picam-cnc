#!/usr/bin/env python3
"""
Settings Window Logik
- Verwaltet die Settings-View
- Trennung von UI (settingswindow.py) und Logik
"""

import cv2
from PyQt5.QtWidgets import QMainWindow, QGraphicsScene, QGraphicsPixmapItem, QTreeWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from caliDeviceWin import Ui_MainWindow as Ui_SettingsWindow

import appSettings
import camera



# Use appSettings for camera selection and persistence (call directly via appSettings)





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

        # Get screen size from hardware settings
        hardware_settings = appSettings.get_hardware_settings()
        screen_size = hardware_settings.get("screen_size", {"width": 640, "height": 480})
        screen_width = screen_size.get("width", 640)
        screen_height = screen_size.get("height", 480)

        # Set TreeView width to 200, gvCamera width to (screen_width - 200)
        treeview_width = 250
        camera_width = max(100, screen_width - treeview_width)
        camera_height = screen_height
        self.ui.tvSettings.setMaximumWidth(treeview_width)
        self.ui.tvSettings.setMinimumWidth(treeview_width)
        self.ui.gvCamera.setMaximumWidth(camera_width)
        self.ui.gvCamera.setMinimumWidth(camera_width)
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
        
        # Aktuelle Kamera-Einstellungen (temporär für dieses Fenster)
        self.current_camera_index = None
        self.current_camera_id = None
        self.current_resolution = "640x480"
        self.current_fps = "30"
        self.current_format = "MJPEG"
        
        # Speichere die vorher ausgewählte Kamera (zum Wiederherstellen bei Cancel)
        self.previous_selected_index, self.previous_selected_id = appSettings.get_active_camera()
        
        # Lade gespeicherte Settings
        self.saved_settings = appSettings.load_app_settings()
        
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
        # Prüfe ob es eine gespeicherte "active_camera" gibt
        selected_cam_id = self.saved_settings.get("active_camera", {}).get("id")
        devices = camera.list_video_devices()
        if selected_cam_id:
            print(f"[LOG] Trying to load previously selected camera: {selected_cam_id}")
            for i in devices:
                camera_id = camera.get_camera_id(i)
                if camera_id == selected_cam_id and camera_id in self.saved_settings:
                    print(f"[LOG] Found previously selected camera {i}")
                    self.load_camera(i, camera_id)
                    return
            print(f"[LOG] Previously selected camera not found, searching for alternatives...")
        # Fallback: Suche nach irgendeiner angeschlossener Kamera mit Settings
        for i in devices:
            camera_id = camera.get_camera_id(i)
            if camera_id in self.saved_settings:
                print(f"[LOG] Auto-loading camera {i} with saved settings")
                self.load_camera(i, camera_id)
                break
    
    def load_camera(self, camera_index, camera_id):
        """Lade eine Kamera mit ihren Settings"""
        # Setze Kamera-Index und ID (temporär)
        self.current_camera_index = camera_index
        self.current_camera_id = camera_id
        
        # NICHT global setzen beim Auto-Load - nur temporär!
        
        # Lese Capabilities
        capabilities = camera.get_camera_capabilities(camera_index)
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
        self.select_camera_in_tree(camera_index)
        
        # Starte Kamera
        self.start_camera_with_settings()
    
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
                    self.current_camera_id = camera.get_camera_id(camera_index)
                    print(f"[LOG] Camera {camera_index} selected temporarily (ID: {self.current_camera_id})")
                    
                    # NICHT global setzen - nur temporär in diesem Fenster!
                    # Wird erst bei OK übernommen
                    
                    # Schließe alle anderen Äste (Resolution, FPS, Format)
                    self.resolution_item.setExpanded(False)
                    self.fps_item.setExpanded(False)
                    self.format_item.setExpanded(False)
                    print("[LOG] Collapsed all tree items (Resolution, FPS, Format)")
                    
                    # Lese Kamera-Capabilities mit v4l2-ctl
                    capabilities = camera.get_camera_capabilities(camera_index)
                    self.camera_capabilities = capabilities
                    
                    # Aktiviere und fülle andere Tree Items mit tatsächlichen Werten
                    self.populate_format_options(capabilities)
                    self.resolution_item.setDisabled(False)
                    self.fps_item.setDisabled(False)
                    self.format_item.setDisabled(False)
                    print("[LOG] Updated tree items with camera capabilities")
                    
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
    
    
        
    def setup_connections(self):
        """Verbinde UI-Elemente mit Logik"""
        self.ui.bCancel.clicked.connect(self.on_cancel_clicked)
        self.ui.bOk.clicked.connect(self.on_ok_clicked)
        self.ui.tvSettings.itemClicked.connect(self.on_tree_item_clicked)
    
    def set_item_height(self, item):
        """Setze feste Höhe für TreeWidget Item"""
        from PyQt5.QtCore import QSize
        item.setSizeHint(0, QSize(0, 44))

    def get_human_readable_cameras(self):
        devices = camera.list_video_devices()
        available = [f"Camera {i} (/dev/video{i})" for i in devices]
        if not available:
            available.append("No cameras detected")
        return available

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
        cameras = self.get_human_readable_cameras()
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
        
    
    
    def get_default_capabilities(self):
        """Throw error and prompt user to install v4l2-ctl if not available."""
        raise RuntimeError(
            "Camera capabilities could not be determined. Please install 'v4l2-ctl' (sudo apt install v4l-utils) and ensure your camera is connected."
        )
        
    # load_cameras() removed: ComboBox-based UI is deprecated in favor of TreeView.
        
    # populate_default_settings() removed: UI uses TreeView; ComboBox defaults are unused.
        
    # get_current_camera_settings() removed: callers should use camera.get_camera_info()
    
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
        self.video_thread = camera.VideoThread(self.current_camera_index, width, height, fps, format_fourcc)
        self.video_thread.change_pixmap_signal.connect(self.update_image)
        self.video_thread.start()
    
    def stop_camera(self):
        """Stoppe Kamera-Stream"""
        if self.video_thread is not None:
            self.video_thread.stop()
            devices = camera.list_video_devices()
            print("[LOG] Camera stopped")
            
    def update_image(self, qt_image):
        pixmap = QPixmap.fromImage(qt_image)
        self.pixmap_item.setPixmap(pixmap)
        # Fit in View beim ersten Frame
        if self.scene.sceneRect().isEmpty():
            self.ui.gvCamera.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def on_cancel_clicked(self):
        """bCancel: Verwerfe temporäre Auswahl, stelle vorherige wieder her"""
        print("[LOG] Cancel button pressed - discarding changes")
        # Stelle vorherige Auswahl wieder her
        if self.previous_selected_index is not None and self.previous_selected_id is not None:
            appSettings.set_active_camera(self.previous_selected_index, self.previous_selected_id)
            print(f"[LOG] Restored previous camera selection: index={self.previous_selected_index}, id={self.previous_selected_id}")
        # Stoppe Kamera vor dem Verlassen
        self.stop_camera()
        if self.on_back_callback:
            self.on_back_callback()

    def on_ok_clicked(self):
        """bOk: Übernimm temporäre Auswahl global und speichere in JSON"""
        print("[LOG] OK button pressed - applying changes")
        # Übernimm die aktuelle Auswahl global
        if self.current_camera_index is not None and self.current_camera_id is not None:
            appSettings.set_active_camera(self.current_camera_index, self.current_camera_id)
            print(f"[LOG] Applied camera selection globally: index={self.current_camera_index}, id={self.current_camera_id}")
            # Speichere Kamera-Settings (inkl. ausgewählte Kamera)
            self.save_current_camera_settings()
            # active_camera is now persisted via set_selected_camera; no legacy selected_camera entry
        # Stoppe Kamera vor dem Verlassen
        self.stop_camera()
        if self.on_back_callback:
            self.on_back_callback()

    def save_current_camera_settings(self):
        """Delegate camera settings save to appSettings.save_current_camera_settings."""
        appSettings.save_current_camera_settings(
            self.saved_settings,
            self.current_camera_id,
            self.current_camera_index,
            self.current_format,
            self.current_resolution,
            self.current_fps
        )
