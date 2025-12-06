#!/usr/bin/env python3
"""
RoundedButton - Custom round button with circular click area
- Distance-based click detection (only inside radius)
- Configurable diameter
- Icon support
- Transparent background with visual border-radius
"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon


class RoundedButton(QPushButton):
    """Round button with circular click area - distance based"""
    
    def __init__(self, icon_path=None, diameter=56, parent=None, old_button=None, active_icon_path=None):
        """
        Initialize round button
        
        Args:
            icon_path (str): Path to icon file (optional)
            diameter (int): Button diameter in pixels (default: 56)
            parent (QWidget): Parent widget (optional)
            old_button (QPushButton): Original button to replace (optional)
                                     If provided, position and checkable state will be copied
            active_icon_path (str): Path to active/checked icon (optional)
                                   If provided, button will switch to this icon when checked
        """
        super().__init__(parent)
        self._diameter = diameter
        self._radius = diameter / 2.0
        self._icon_path = icon_path  # Speichere Basis-Icon-Pfad
        self._active_icon_path = active_icon_path  # Speichere aktives Icon (optional)
        
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
        
        # Wenn alter Button übergeben wurde, übernehme Position und Checkable-Status
        if old_button:
            # Copy position from old UI button and preserve its checkable state.
            # We intentionally do NOT attempt to extract icon pixmaps from the
            # old button here: icons are provided via the constructor parameters
            # (icon_path / active_icon_path) and mixing both approaches caused
            # confusing behavior. Keep the replacement simple and predictable.
            self.move(old_button.pos())
            if old_button.isCheckable():
                self.setCheckable(True)
            old_button.hide()

        # Wenn ein aktives Icon übergeben wurde (als Pfad oder als QIcon), mache den Button checkable
        if (self._active_icon_path or getattr(self, '_active_icon_qicon', None)) and not self.isCheckable():
            self.setCheckable(True)

        # Verbinde toggled-Signal mit Icon-Update (falls checkable)
        self.toggled.connect(self._on_toggled)

        # Stelle initialen Icon-Status passend zum Checked-State sicher
        # (z.B. falls der alte Button bereits checked war)
        if self.isCheckable():
            # set initial icon according to current checked state
            try:
                self._on_toggled(self.isChecked())
            except Exception:
                # Safety: don't crash during init if something's off
                pass

    def _on_toggled(self, checked):
        """
        Automatischer Icon-Wechsel bei Toggle (für checkable buttons)
        Wechselt zwischen icon_path und active_icon_path (falls vorhanden)
        
        Args:
            checked (bool): Button checked status
        """
        # Prefer QIcon variants extracted from old_button if available
        if checked:
            if getattr(self, '_active_icon_qicon', None):
                self.setIcon(self._active_icon_qicon)
                return
            if self._active_icon_path:
                self.setIcon(QIcon(self._active_icon_path))
                return
            # No active icon available - keep existing icon
        else:
            # Normal state: prefer extracted qicon then path
            if getattr(self, '_icon_qicon', None):
                self.setIcon(self._icon_qicon)
                return
            if self._icon_path:
                self.setIcon(QIcon(self._icon_path))
                return

    def mousePressEvent(self, event):
        """
        Only accept clicks inside a circular radius
        
        Args:
            event (QMouseEvent): Mouse press event
        """
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
            super().mousePressEvent(event)
        else:
            event.ignore()
    
    def get_diameter(self):
        """Get button diameter"""
        return self._diameter
    
    def get_radius(self):
        """Get button radius"""
        return self._radius
