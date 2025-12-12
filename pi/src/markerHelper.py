"""markerHelper

Light-weight helpers for computing image-space X/Y axes from a Euclidean
transform and for deriving the world axes from marker groups.

Public API:
- `euclid_transform_coord(xd, yd, Az, width, height)` -> endpoints of X/Y axes
- `compute_world_axes_from_markers(markers)` -> (Az_deg, xd, yd) from markers

Only minimal helpers are exposed here; legacy, more complex axis routines
were removed in favor of `euclid_transform_coord`.
"""

from typing import Optional, Tuple, Dict
import math
import numpy as np
import appSettings

# Public API exported by `from markerHelper import *`
__all__ = ["euclid_transform_coord", "compute_world_axes_from_markers"]


def _intersect_line_rect(x0: float, y0: float, dx: float, dy: float, w: float, h: float):
    """Return up to two intersection points (x,y) of the parametric line
    (x0+t*dx, y0+t*dy) with the rectangle [0..w] x [0..h]. If no intersections
    are found a long projected segment is returned as two points.
    """
    eps = 1e-12
    pts = []
    if abs(dx) > eps:
        t = (0.0 - x0) / dx
        y = y0 + t * dy
        if -eps <= y <= h + eps:
            pts.append((t, 0.0, y))
        t = (w - x0) / dx
        y = y0 + t * dy
        if -eps <= y <= h + eps:
            pts.append((t, float(w), y))
    if abs(dy) > eps:
        t = (0.0 - y0) / dy
        x = x0 + t * dx
        if -eps <= x <= w + eps:
            pts.append((t, x, 0.0))
        t = (h - y0) / dy
        x = x0 + t * dx
        if -eps <= x <= w + eps:
            pts.append((t, x, float(h)))
    if not pts:
        diag = math.hypot(w, h) * 1.5
        return [(x0 - dx * diag, y0 - dy * diag), (x0 + dx * diag, y0 + dy * diag)]
    # deduplicate and sort by t
    seen = set()
    uniq = []
    for t, x, y in pts:
        key = (round(float(x), 6), round(float(y), 6))
        if key not in seen:
            seen.add(key)
            uniq.append((t, float(x), float(y)))
    uniq.sort(key=lambda v: v[0])
    if len(uniq) == 1:
        return [(uniq[0][1], uniq[0][2])]
    return [(uniq[0][1], uniq[0][2]), (uniq[-1][1], uniq[-1][2])]


def _clamp_point(x: float, y: float, width: int, height: int) -> Tuple[int, int]:
    ix = int(round(x))
    iy = int(round(y))
    ix = max(0, min(width - 1, ix))
    iy = max(0, min(height - 1, iy))
    return ix, iy


def euclid_transform_coord(xd: float, yd: float, Az: float, width: int, height: int) -> Dict[str, Tuple[int, int]]:
    """Compute axis endpoints at image borders for a Euclidean transform.

    xd, yd are origin offsets in pixels relative to image center (centered
    coordinates). Az is degrees (0 => X to the right, positive CCW).
    """
    # image center
    cx = float(width) / 2.0
    cy = float(height) / 2.0
    ox = cx + float(xd)
    oy = cy + float(yd)

    theta = math.radians(float(Az))
    vx = math.cos(theta)
    vy = math.sin(theta)
    px = -vy
    py = vx

    x_pts = _intersect_line_rect(ox, oy, vx, vy, float(width), float(height))
    y_pts = _intersect_line_rect(ox, oy, px, py, float(width), float(height))

    # guarantee two points
    if len(x_pts) < 2:
        diag = math.hypot(width, height) * 1.5
        x_pts = [(ox - vx * diag, oy - vy * diag), (ox + vx * diag, oy + vy * diag)]
    if len(y_pts) < 2:
        diag = math.hypot(width, height) * 1.5
        y_pts = [(ox - px * diag, oy - py * diag), (ox + px * diag, oy + py * diag)]

    x_start = _clamp_point(x_pts[0][0], x_pts[0][1], width, height)
    x_end = _clamp_point(x_pts[1][0], x_pts[1][1], width, height)
    y_start = _clamp_point(y_pts[0][0], y_pts[0][1], width, height)
    y_end = _clamp_point(y_pts[1][0], y_pts[1][1], width, height)

    return {"x_start": x_start, "x_end": x_end, "y_start": y_start, "y_end": y_end}


def compute_world_axes_from_markers(markers: Dict[str, list]) -> Tuple[float, float, float]:
    """Given marker groups 'xt','xb','yl','yr' (centered coords) compute Az, xd, yd.

    Returns (Az_deg, xd, yd) where xd, yd are in the same centered coordinate
    system (pixels).
    """
    try:
        xt = np.array(markers['xt'], dtype=np.float64)
        xb = np.array(markers['xb'], dtype=np.float64)
        yl = np.array(markers['yl'], dtype=np.float64)
        yr = np.array(markers['yr'], dtype=np.float64)
    except Exception:
        raise ValueError("Markers must be a dict with keys 'xt','xb','yl','yr' mapping to lists of (x,y) points")

    if xt.size == 0 or xb.size == 0 or yl.size == 0 or yr.size == 0:
        raise ValueError("Each marker group ('xt','xb','yl','yr') must contain at least one point")

    def fit_line(points: np.ndarray):
        x = points[:, 0]
        y = points[:, 1]
        if x.size < 2:
            return 0.0, float(y[0])
        A = np.vstack([x, np.ones_like(x)]).T
        m, b = np.linalg.lstsq(A, y, rcond=None)[0]
        return float(m), float(b)

    m_xt, b_xt = fit_line(xt)
    m_xb, b_xb = fit_line(xb)
    m_xw = (m_xt + m_xb) / 2.0
    b_xw = (b_xt + b_xb) / 2.0

    yw_x = (float(np.mean(yl[:, 0])) + float(np.mean(yr[:, 0]))) / 2.0
    origin_x = yw_x
    origin_y = m_xw * yw_x + b_xw

    Az_rad = math.atan2(m_xw, 1.0)
    Az = float(math.degrees(Az_rad))
    xd = float(origin_x)
    yd = float(origin_y)
    return Az, xd, yd
# Duplicate legacy implementation removed; use typed `compute_world_axes_from_markers` above.
