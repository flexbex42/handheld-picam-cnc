#!/usr/bin/env python3
"""
Loader - zeigt Loading-Fenster während cv2 importiert wird
Dann startet es die eigentliche Main App
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from loadingwindow import Ui_Form


class LoadingWorker(QThread):
    """Worker Thread der die schweren Imports lädt"""
    finished_signal = pyqtSignal()
    
    def run(self):
        """Importiere cv2 und main"""
        # Import cv2 (dauert lange)
        import cv2
        
        # Importiere main (enthält jetzt kein cv2 mehr am Modulanfang)
        import main
        
        # Speichere Referenz für später
        self.main_module = main
        
        self.finished_signal.emit()


class LoadingWindow(QWidget):
    """Loading Screen"""
    
    def __init__(self):
        super().__init__()
        
        # Setup UI
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Fenster-Eigenschaften
        self.setWindowTitle("Loading...")
        
        # Starte Worker nach kurzem Delay (damit GUI sichtbar wird)
        QTimer.singleShot(1000, self.start_loading)
        
    def start_loading(self):
        """Starte Loading Worker"""
        self.worker = LoadingWorker()
        self.worker.finished_signal.connect(self.on_loading_finished)
        self.worker.start()
        
    def on_loading_finished(self):
        """Loading fertig - starte Main App"""
        # Hole main Modul vom Worker
        main = self.worker.main_module
        
        # Erstelle und zeige Main Window
        self.main_window = main.MainApp()
        self.main_window.show()
        
        # Schließe Loading Window
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Zeige Loading Window
    loading = LoadingWindow()
    loading.show()
    
    sys.exit(app.exec_())
