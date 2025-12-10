import numpy as np
import matplotlib.pyplot as plt

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from rectifyHelper import compute_world_axes_from_markers

import matplotlib.pyplot as plt
import numpy as np


# Example marker data: each is a list of (x, y) points, origin at image center
# xt and xb: horizontal lines, yl and yr: vertical lines
markers = {
    'xt': [(-100, 4), (0, 7), (100, 4)],
    'xb': [(-100, -2), (0, -2), (100, -2)],
    'yl': [(-28, 100), (-5, 10), (-5, -100)],
    'yr': [(-10, 100), (1, 10), (1, -100)]
}

Az, xo, yo = compute_world_axes_from_markers(markers)
print(f"Azimuth (deg): {Az:.2f}, Offset X (mm): {xo:.2f}, Offset Y (mm): {yo:.2f}")

fig, ax = plt.subplots()

# Plot marker points
for key, pts in markers.items():
    pts = np.array(pts)
    ax.scatter(pts[:,0], pts[:,1], label=key)


# Plot fitted lines for xt, xb
def plot_fit_line(points, color, label=None):
    points = np.array(points)
    x = points[:,0]
    y = points[:,1]
    m, b = np.linalg.lstsq(np.vstack([x, np.ones_like(x)]).T, y, rcond=None)[0]
    xfit = np.linspace(x.min(), x.max(), 100)
    yfit = m * xfit + b
    ax.plot(xfit, yfit, color=color, linestyle='--', label=label)

plot_fit_line(markers['xt'], 'red', 'xt fit')
plot_fit_line(markers['xb'], 'blue', 'xb fit')

# Plot fitted vertical lines for yl, yr
def plot_vertical_line(points, color, label=None):
    points = np.array(points)
    x_mean = np.mean(points[:,0])
    y_min = points[:,1].min()
    y_max = points[:,1].max()
    ax.plot([x_mean, x_mean], [y_min, y_max], color=color, linestyle='--', label=label)

plot_vertical_line(markers['yl'], 'green', 'yl fit')
plot_vertical_line(markers['yr'], 'orange', 'yr fit')



# Use compute_world_axes_from_markers to get Xw and Yw axes
scale_mm_per_pixel = 1.0  # Use 1.0 for pixel units in visualization
Az, xo, yo = compute_world_axes_from_markers(markers, scale_mm_per_pixel)

# Xw direction vector
Az_rad = np.radians(Az)
Xw_vec = np.array([np.cos(Az_rad), np.sin(Az_rad)])
# Yw direction vector (perpendicular)
Yw_vec = np.array([-np.sin(Az_rad), np.cos(Az_rad)])

# Plot Xw axis (magenta) and Yw axis (cyan) centered at origin
origin = np.array([xo, yo])
length = 100
ax.plot([origin[0] - length*Xw_vec[0], origin[0] + length*Xw_vec[0]],
    [origin[1] - length*Xw_vec[1], origin[1] + length*Xw_vec[1]],
    color='magenta', linewidth=2, label='Xw axis (computed)')
ax.plot([origin[0] - length*Yw_vec[0], origin[0] + length*Yw_vec[0]],
    [origin[1] - length*Yw_vec[1], origin[1] + length*Yw_vec[1]],
    color='cyan', linewidth=2, label='Yw axis (computed)')

# Plot origin
origin_x = xo
origin_y = yo
ax.scatter([origin_x], [origin_y], color='black', marker='x', s=100, label='Origin')

ax.set_xlabel('X (pixels, origin=center)')
ax.set_ylabel('Y (pixels, origin=center)')
ax.set_title('Marker Axes and Fitted Lines')
ax.legend()
ax.axis('equal')
plt.show()

