#!/usr/bin/env python3
"""Simple test script for markerHelper functions.

This script creates a placeholder set of four marker groups (each with one point
at (0,0) by default) and calls `compute_world_axes_from_markers` and
`compute_axis_coords`, printing the results. Modify the marker coordinates in
this file to test different inputs.
"""

from markerHelperTest import (
    compute_world_axes_from_markers,
    euclid_transform_coord,
)


def generate_markers_from_params(xc: float, yc: float, Ac_deg: float, spacing: float = 5.0, span: float = 300.0, n_per=4):
    """Generate marker groups around a custom origin (xc,yc) with rotation Ac_deg.

    - `xc, yc`: coordinates of the new origin in the centered coordinate system
      (i.e. relative to image center).
    - `Ac_deg`: rotation of the X axis in degrees (0 = right, positive CCW).
    - `spacing`: offset in pixels from the axis (5 means 5px above/below/left/right).
    - `span`: total span (length) of the sampled points along each axis (pixels).
    - `n_per`: number of points per group (e.g. 4).

    Returns marker dict with keys 'xt','xb','yl','yr' containing absolute
    coordinates in the centered coordinate system (origin at image center).
    """
    import math
    a = math.radians(Ac_deg)
    # unit vector along X axis (rotated)
    ux = math.cos(a)
    uy = math.sin(a)
    # unit vector along Y axis (perpendicular, 90deg CCW)
    vx = -uy
    vy = ux

    # half-length along axes for sampling
    half = float(span) / 2.0
    if n_per == 1:
        t_x = [0.0]
        t_y = [0.0]
    else:
        t_x = [(-half + 2*half*i/(n_per-1)) for i in range(n_per)]
        t_y = [(-half + 2*half*i/(n_per-1)) for i in range(n_per)]

    xt = []
    xb = []
    yl = []
    yr = []

    # xt: points along X axis, offset +spacing along perpendicular (above X)
    for t in t_x:
        x = xc + ux * t + vx * spacing
        y = yc + uy * t + vy * spacing
        xt.append((x, y))

    # xb: points along X axis, offset -spacing along perpendicular (below X)
    for t in t_x:
        x = xc + ux * t - vx * spacing
        y = yc + uy * t - vy * spacing
        xb.append((x, y))

    # yl: points along Y axis, offset -spacing along X (left of Y axis)
    for t in t_y:
        x = xc + vx * t - ux * spacing
        y = yc + vy * t - uy * spacing
        yl.append((x, y))

    # yr: points along Y axis, offset +spacing along X (right of Y axis)
    for t in t_y:
        x = xc + vx * t + ux * spacing
        y = yc + vy * t + uy * spacing
        yr.append((x, y))

    return {'xt': xt, 'xb': xb, 'yl': yl, 'yr': yr}



def main():
    # Use only the provided marker coordinates for testing
    markers = {
        'xt': [(-275.0, 73.0), (-108.0, 25.0), (122.0, -36.0), (29.0, -12.0)],
        'xb': [(-266.0, 89.0), (-156.0, 58.0), (6.0, 14.0), (114.0, -17.0)],
        'yl': [(-35.0, 153.0), (-92.0, -57.0), (-126.0, -182.0), (-50.0, 101.0)],
        'yr': [(-114.0, -196.0), (-14.0, 175.0), (-90.0, -107.0), (-42.0, 70.0)],
    }

    width = 640
    height = 480

    print("Input markers:")
    for k, v in markers.items():
        print(f"  {k}: {v}")

    Az, xd_ret, yd_ret = compute_world_axes_from_markers(markers)
    print(f"compute_world_axes_from_markers -> Az={Az}, xd={xd_ret}, yd={yd_ret}")

    coords_euclid = euclid_transform_coord(xd_ret, yd_ret, Az, width, height)

    print("Axis coordinates (euclid_transform_coord):")
    for name, pt in coords_euclid.items():
        print(f"  {name}: {pt}")

    # Optional: plot result
    try:
        import matplotlib.pyplot as plt
        cx = width / 2.0
        cy = height / 2.0

        def to_tl(pt):
            return (pt[0] + cx, pt[1] + cy)

        fig, ax = plt.subplots(figsize=(8, 6))
        for k, pts in markers.items():
            t_pts = [to_tl(p) for p in pts]
            xs = [p[0] for p in t_pts]
            ys = [p[1] for p in t_pts]
            if k == 'xt':
                ax.scatter(xs, ys, c='red', marker='o', label='xt')
            elif k == 'xb':
                ax.scatter(xs, ys, c='blue', marker='o', label='xb')
            elif k == 'yl':
                ax.scatter(xs, ys, c='green', marker='x', label='yl')
            elif k == 'yr':
                ax.scatter(xs, ys, c='magenta', marker='x', label='yr')

        # Visualize marker means, midpoint, and origin
        import numpy as np
        yl = np.array(markers['yl'], dtype=np.float64)
        yr = np.array(markers['yr'], dtype=np.float64)
        mean_yl = np.mean(yl, axis=0)
        mean_yr = np.mean(yr, axis=0)
        mid = (mean_yl + mean_yr) / 2.0
        # Project midpoint onto X axis (origin)
        m_xt, b_xt = np.linalg.lstsq(np.vstack([np.array(markers['xt'])[:,0], np.ones(4)]).T, np.array(markers['xt'])[:,1], rcond=None)[0]
        m_xb, b_xb = np.linalg.lstsq(np.vstack([np.array(markers['xb'])[:,0], np.ones(4)]).T, np.array(markers['xb'])[:,1], rcond=None)[0]
        m_xw = (m_xt + m_xb) / 2.0
        b_xw = (b_xt + b_xb) / 2.0
        origin_x = mid[0]
        origin_y = m_xw * origin_x + b_xw
        # Draw means
        ax.scatter([mean_yl[0]+cx], [mean_yl[1]+cy], c='green', marker='s', s=80, label='mean yl')
        ax.scatter([mean_yr[0]+cx], [mean_yr[1]+cy], c='magenta', marker='s', s=80, label='mean yr')
        ax.scatter([mid[0]+cx], [mid[1]+cy], c='orange', marker='*', s=120, label='midpoint yl/yr')
        ax.scatter([origin_x+cx], [origin_y+cy], c='black', marker='*', s=120, label='origin (proj)')

        # plot only euclid_transform_coord axes (black/gray)
        exs = [coords_euclid['x_start'], coords_euclid['x_end']]
        eys = [coords_euclid['y_start'], coords_euclid['y_end']]

        ax.plot([exs[0][0], exs[1][0]], [exs[0][1], exs[1][1]], c='black', linewidth=2, label='euclid X axis')
        ax.plot([eys[0][0], eys[1][0]], [eys[0][1], eys[1][1]], c='gray', linewidth=2, label='euclid Y axis')

        ax.set_xlim(0, width)
        ax.set_ylim(0, height)
        ax.invert_yaxis()
        ax.set_aspect('equal', adjustable='box')
        ax.legend()
        out_path = f'pi/src/testMarker_plot_case_fixed.png'
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Saved marker/axis plot to: {out_path}")
    except Exception as e:
        print(f"[WARN] matplotlib plot failed: {e}")


if __name__ == '__main__':
    main()
