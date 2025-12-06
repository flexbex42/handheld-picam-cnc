"""
Test window for circular buttons - simplified version
"""

from PyQt5.QtWidgets import QWidget, QPushButton
from PyQt5.QtCore import Qt, QSize, QRectF
from PyQt5.QtGui import QIcon, QRegion, QPainterPath
from caliOffsetTestWin import Ui_CalibrationOffsetTestWindow


class RoundedButton(QPushButton):
    """Round button with circular click area - distance based"""
    def __init__(self, icon_path=None, diameter=56, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self._radius = diameter / 2.0
        
        # Set size constraints BEFORE stylesheet
        self.setMinimumSize(diameter, diameter)
        self.setMaximumSize(diameter, diameter)
        self.setFixedSize(diameter, diameter)
        
        if icon_path:
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(diameter, diameter))
        
        # Transparent background with visual border-radius, explicit size in stylesheet too
        self.setStyleSheet(f"""
            QPushButton {{
                border: none; 
                background: transparent; 
                border-radius: {diameter//2}px;
                min-width: {diameter}px;
                max-width: {diameter}px;
                min-height: {diameter}px;
                max-height: {diameter}px;
            }}
        """)

    def mousePressEvent(self, event):
        """Only accept clicks inside a circular radius"""
        # Calculate distance from center
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        
        dx = event.pos().x() - center_x
        dy = event.pos().y() - center_y
        distance = (dx * dx + dy * dy) ** 0.5
        
        # Absolute position on screen
        abs_pos = self.mapToGlobal(event.pos())
        
        # Only accept if inside radius (with small margin for better UX)
        if distance <= self._radius * 0.9:  # 90% of radius for tighter click area
            print(f"Click inside circle: abs=({abs_pos.x()},{abs_pos.y()}), local=({event.pos().x()},{event.pos().y()}), distance={distance:.1f}, radius={self._radius:.1f}")
            super().mousePressEvent(event)
        else:
            print(f"Click OUTSIDE circle: abs=({abs_pos.x()},{abs_pos.y()}), local=({event.pos().x()},{event.pos().y()}), distance={distance:.1f}, radius={self._radius:.1f}")
            event.ignore()


class CalibrationOffsetTestWindow(QWidget):
    """Simple test window with three circular buttons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_CalibrationOffsetTestWindow()
        self.ui.setupUi(self)
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Replace UI buttons with RoundedButton instances"""
        # Hide original UI buttons first
        self.ui.bDecline.hide()
        self.ui.bAccept.hide()
        self.ui.bExit.hide()
        
        # Replace bDecline
        self.bDecline = RoundedButton(
            icon_path=":/icons/undo.png",
            diameter=56,
            parent=self
        )
        self.bDecline.move(250, 200)  # Näher zur Mitte
        self.bDecline.show()
        self.bDecline.raise_()
        
        # Replace bAccept
        self.bAccept = RoundedButton(
            icon_path=":/icons/ok.png",
            diameter=56,
            parent=self
        )
        self.bAccept.move(334, 200)  # Näher zur Mitte (Abstand: 28px statt 108px)
        self.bAccept.show()
        self.bAccept.raise_()
        
        # Replace bExit
        self.bExit = RoundedButton(
            icon_path=":/icons/close.png",
            diameter=50,
            parent=self
        )
        self.bExit.move(32, 32)  # Links oben
        self.bExit.show()
        self.bExit.raise_()
        
        print("RoundedButtons erstellt:")
        print(f"  bDecline: Position ({self.bDecline.x()}, {self.bDecline.y()}), Größe {self.bDecline.width()}x{self.bDecline.height()}")
        print(f"  bAccept:  Position ({self.bAccept.x()}, {self.bAccept.y()}), Größe {self.bAccept.width()}x{self.bAccept.height()}")
        print(f"  bExit:    Position ({self.bExit.x()}, {self.bExit.y()}), Größe {self.bExit.width()}x{self.bExit.height()}")
    
    def setup_connections(self):
        """Connect button signals"""
        self.bExit.clicked.connect(self.on_exit_clicked)
        self.bDecline.clicked.connect(self.on_decline_clicked)
        self.bAccept.clicked.connect(self.on_accept_clicked)
    
    def on_exit_clicked(self):
        """Close window"""
        print("Exit geklickt - Fenster wird geschlossen")
        self.close()
    
    def on_decline_clicked(self):
        """Debug output for decline"""
        print("DEBUG: Decline Button geklickt!")
    
    def on_accept_clicked(self):
        """Debug output for accept"""
        print("DEBUG: Accept Button geklickt!")
