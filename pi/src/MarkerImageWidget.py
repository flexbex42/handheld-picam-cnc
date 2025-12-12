from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QPixmap, QImage
from PyQt5.QtCore import Qt, QRect

import numpy as np
import appSettings
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QImage
from PyQt5.QtCore import Qt, QRect

class MarkerImageWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        # Initialize image size from hardware settings if available so
        # get_markers_for_axes can center coordinates before an image is set.
        try:
            hw = appSettings.get_hardware_settings()
            screen = hw.get('screen_size', {}) if isinstance(hw, dict) else {}
            self.img_width = int(screen.get('width', 640))
            self.img_height = int(screen.get('height', 480))
        except Exception:
            self.img_width = 640
            self.img_height = 480
        self.zoom = 1.0
        self.zoom_center = None  # (x, y)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        # Marker logic
        self.marker_groups = {}

    def set_image(self, qimage_or_pixmap):
        if isinstance(qimage_or_pixmap, QImage):
            self._image = QPixmap.fromImage(qimage_or_pixmap)
        else:
            self._image = qimage_or_pixmap
        if self._image:
            self.img_width = self._image.width()
            self.img_height = self._image.height()
        self.update()

    def current_src_rect(self):
        # Return the QRect of the image that is currently mapped to the widget rect
        if not self._image or self.img_width == 0 or self.img_height == 0:
            return QRect(0, 0, 1, 1)
        if self.zoom != 1.0 and self.zoom_center:
            cx, cy = self.zoom_center
            src_w = max(1, int(self.img_width / self.zoom))
            src_h = max(1, int(self.img_height / self.zoom))
            left = int(cx - src_w // 2)
            top = int(cy - src_h // 2)
            # clamp
            if left < 0:
                left = 0
            if top < 0:
                top = 0
            if left + src_w > self.img_width:
                left = self.img_width - src_w
            if top + src_h > self.img_height:
                top = self.img_height - src_h
            return QRect(left, top, src_w, src_h)
        else:
            return QRect(0, 0, self.img_width, self.img_height)

    def widget_to_image(self, wx, wy):
        # Map widget coordinates to image pixel coordinates based on current src_rect
        if not self._image:
            return (wx, wy)
        src = self.current_src_rect()
        if src.width() <= 0 or src.height() <= 0:
            return (wx, wy)
        sx = float(wx) * (src.width() / max(1, self.width())) + src.left()
        sy = float(wy) * (src.height() / max(1, self.height())) + src.top()
        return (int(sx), int(sy))

    def image_to_widget(self, ix, iy):
        # Map image pixel coords to widget coords based on current src_rect
        if not self._image:
            return (ix, iy)
        src = self.current_src_rect()
        if src.width() <= 0 or src.height() <= 0:
            return (ix, iy)
        wx = (ix - src.left()) * (self.width() / src.width())
        wy = (iy - src.top()) * (self.height() / src.height())
        return (int(wx), int(wy))

    def draw_line_on_image(self, start: tuple, end: tuple, color, width: int = 3) -> bool:
        """Draw a line directly onto the underlying image (image coordinates).

        Parameters:
        - start: (x, y) tuple in image pixel coordinates.
        - end: (x, y) tuple in image pixel coordinates.
        - color: QColor or (r,g,b) tuple or hex string.
        - width: line width in pixels.

        Returns True on success, False otherwise.
        """
        if self._image is None:
            return False

        # normalize color
        if isinstance(color, tuple) or isinstance(color, list):
            qcolor = QColor(*color)
        elif isinstance(color, QColor):
            qcolor = color
        else:
            try:
                qcolor = QColor(color)
            except Exception:
                qcolor = QColor(255, 0, 0)

        try:
            painter = QPainter(self._image)
            pen = QPen(qcolor, width)
            painter.setPen(pen)
            x1, y1 = int(start[0]), int(start[1])
            x2, y2 = int(end[0]), int(end[1])
            painter.drawLine(x1, y1, x2, y2)
            painter.end()
            # update widget
            self.update()
            return True
        except Exception:
            return False

    def add_marker_group(self, group_id, color):
        if isinstance(color, tuple):
            color = QColor(*color)
        self.marker_groups[group_id] = {'color': color, 'markers': {}}

    def set_marker(self, group_id, marker_id, xpos, ypos):
        if group_id not in self.marker_groups:
            raise ValueError(f"Group {group_id} not found")
        self.marker_groups[group_id]['markers'][marker_id] = (xpos, ypos)

    def get_marker_position(self, group_id, marker_id):
        return self.marker_groups.get(group_id, {}).get('markers', {}).get(marker_id, None)

    def unset_marker(self, group_id, marker_id):
        if group_id in self.marker_groups:
            self.marker_groups[group_id]['markers'].pop(marker_id, None)

    def zoom_on_marker(self, group_id, marker_id, zoom_level):
        pos = self.get_marker_position(group_id, marker_id)
        if pos:
            self.zoom = zoom_level
            self.zoom_center = pos
            self.update()

    def reset_zoom(self):
        self.zoom = 1.0
        self.zoom_center = None
        self.update()

    def draw_markers(self, painter):
        for group in self.marker_groups.values():
            color = group['color']
            pen = QPen(color, 3)
            painter.setPen(pen)
            for (ix, iy) in group['markers'].values():
                wx, wy = self.image_to_widget(ix, iy)
                painter.drawEllipse(int(wx)-6, int(wy)-6, 12, 12)
                painter.drawLine(int(wx)-12, int(wy), int(wx)+12, int(wy))
                painter.drawLine(int(wx), int(wy)-12, int(wx), int(wy)+12)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._image:
            if self.zoom != 1.0 and self.zoom_center:
                src_rect = self.current_src_rect()
                painter.drawPixmap(self.rect(), self._image, src_rect)
            else:
                painter.drawPixmap(self.rect(), self._image)
        self.draw_markers(painter)

    def mousePressEvent(self, event):
        wx, wy = event.x(), event.y()
        # convert widget coordinates to image pixel coordinates
        ix, iy = self.widget_to_image(wx, wy)
        # Example: place marker in group 1, id 0
        self.set_marker(1, 0, ix, iy)
        self.update()

    def get_markers_for_axes(self):
        """Return marker groups as lists suitable for axis computation.

        Returns a dict with keys 'xt','xb','yl','yr' each mapping to a list of
        (x,y) tuples in image pixel coordinates.
        """
        out = {'xt': [], 'xb': [], 'yl': [], 'yr': []}
        # center for conversion from top-left origin to image-center origin
        cx = float(self.img_width) / 2.0
        cy = float(self.img_height) / 2.0
        for gid, key in ((0, 'xt'), (1, 'xb'), (2, 'yl'), (3, 'yr')):
            grp = self.marker_groups.get(gid, {})
            markers = grp.get('markers', {}) if isinstance(grp, dict) else {}
            # markers may be dict of id:(x,y) pairs
            pts = []
            if isinstance(markers, dict):
                for v in markers.values():
                    # stored coordinates are image pixels with (0,0) at top-left
                    # convert to centered coordinates (origin at image center)
                    pts.append((float(v[0]) - cx, float(v[1]) - cy))
            elif isinstance(markers, (list, tuple)):
                for v in markers:
                    pts.append((float(v[0]) - cx, float(v[1]) - cy))
            out[key] = pts
        return out
