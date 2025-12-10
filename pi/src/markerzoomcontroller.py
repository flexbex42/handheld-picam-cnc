from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTransform

class MarkerZoomController:
    """
    Controller for marker placement and zooming in a QGraphicsView.
    Usage:
        controller = MarkerZoomController(graphics_view, scene)
        controller.set_marker(x, y)
        controller.zoom_out()
        pos = controller.get_marker_position()
    """
    def __init__(self, graphics_view, scene, marker_color=Qt.red):
        self.view = graphics_view
        self.scene = scene
        self.marker_color = marker_color
        self.marker_items = None
        self.marker_pos = None
        self.zoom_level = 1.0

    def set_marker(self, x, y, zoom=4.0):
        """Set marker at (x, y) and zoom in."""
        self.marker_pos = (x, y)
        self._draw_marker(x, y)
        self.zoom_level = zoom
        self._zoom_to(x, y)

    def get_marker_position(self):
        """Return current marker position as (x, y) or None."""
        return self.marker_pos

    def zoom_out(self):
        """Reset zoom to 1x and show full image."""
        self.zoom_level = 1.0
        transform = QTransform()
        self.view.setTransform(transform)
        self.view.centerOn(self.scene.sceneRect().center())

    def _draw_marker(self, x, y):
        """Draw crosshair marker at (x, y). Removes previous marker."""
        # Remove old marker
        if self.marker_items:
            for item in self.marker_items:
                self.scene.removeItem(item)
        radius = 8
        h_line = self.scene.addLine(x-radius, y, x+radius, y, pen=self.marker_color)
        v_line = self.scene.addLine(x, y-radius, x, y+radius, pen=self.marker_color)
        dot = self.scene.addEllipse(x-2, y-2, 4, 4, pen=self.marker_color, brush=self.marker_color)
        self.marker_items = (h_line, v_line, dot)

    def _zoom_to(self, x, y):
        self.view.centerOn(x, y)
        transform = QTransform()
        transform.scale(self.zoom_level, self.zoom_level)
        self.view.setTransform(transform)
