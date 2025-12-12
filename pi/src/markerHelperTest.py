"""
Copy of markerHelper.py for isolated testing.
"""

# Copy from markerHelper.py below:

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

__all__ = ["euclid_transform_coord", "compute_world_axes_from_markers"]


def _intersect_line_rect(x0: float, y0: float, dx: float, dy: float, w: float, h: float):
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
    """
    Compute optimal origin and azimuth that minimize squared distance from all markers to their axes.
    
    Optimization variables: origin_x, origin_y, azimuth
    Cost function: sum of squared distances from:
      - xt, xb markers to X-axis (defined by origin and azimuth)
      - yl, yr markers to Y-axis (perpendicular to X-axis through origin)
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

    # Combine x markers and y markers
    x_markers = np.vstack([xt, xb])  # All markers that should be near X-axis
    y_markers = np.vstack([yl, yr])  # All markers that should be near Y-axis

    def cost_function(params):
        """
        params = [origin_x, origin_y, azimuth_rad]
        Returns sum of squared distances from markers to their respective axes.
        """
        ox, oy, az_rad = params
        
        # X-axis unit vector (direction)
        cos_az = math.cos(az_rad)
        sin_az = math.sin(az_rad)
        
        # Y-axis unit vector (perpendicular, 90° CCW from X)
        cos_az_perp = -sin_az
        sin_az_perp = cos_az
        
        # Distance from point (px, py) to X-axis through origin with direction (cos_az, sin_az)
        # is: |cross product| = |(px-ox, py-oy) × (cos_az, sin_az)|
        # = |(px-ox)*sin_az - (py-oy)*cos_az|
        error = 0.0
        for pt in x_markers:
            px, py = pt
            dx = px - ox
            dy = py - oy
            dist = abs(dx * sin_az - dy * cos_az)
            error += dist ** 2
        
        # Distance from point to Y-axis
        for pt in y_markers:
            px, py = pt
            dx = px - ox
            dy = py - oy
            dist = abs(dx * sin_az_perp - dy * cos_az_perp)
            error += dist ** 2
        
        return error
    
    # Initial guess: use simple heuristic
    # Origin: midpoint of yl/yr means
    mean_yl = np.mean(yl, axis=0)
    mean_yr = np.mean(yr, axis=0)
    mid = (mean_yl + mean_yr) / 2.0
    
    # Azimuth: fit to x markers
    def fit_line(points: np.ndarray):
        x = points[:, 0]
        y = points[:, 1]
        if x.size < 2:
            return 0.0
        A = np.vstack([x, np.ones_like(x)]).T
        m, b = np.linalg.lstsq(A, y, rcond=None)[0]
        return float(m)
    
    m_xt = fit_line(xt)
    m_xb = fit_line(xb)
    m_initial = (m_xt + m_xb) / 2.0
    az_initial = math.atan2(m_initial, 1.0)
    
    initial_guess = [mid[0], mid[1], az_initial]
    
    # Optimize using scipy
    from scipy.optimize import minimize
    result = minimize(cost_function, initial_guess, method='Nelder-Mead', 
                     options={'maxiter': 1000, 'xatol': 1e-8, 'fatol': 1e-8})
    
    ox_opt, oy_opt, az_rad_opt = result.x
    az_deg_opt = math.degrees(az_rad_opt)
    
    initial_cost = cost_function(initial_guess)
    print("[DEBUG markerHelperTest] Optimization results:")
    print(f"  Initial: origin=({mid[0]:.3f}, {mid[1]:.3f}), Az={math.degrees(az_initial):.3f}°, cost={initial_cost:.3f}")
    print(f"  Optimal: origin=({ox_opt:.3f}, {oy_opt:.3f}), Az={az_deg_opt:.3f}°, cost={result.fun:.3f}")
    print(f"  Improvement: {((initial_cost - result.fun) / initial_cost * 100):.1f}%, Success: {result.success}")
    
    return az_deg_opt, ox_opt, oy_opt
