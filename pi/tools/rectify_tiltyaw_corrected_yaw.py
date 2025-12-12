#!/usr/bin/env python3
"""Rectify a sample image using tilt/yaw perspective reconstruction.

This script reads camera settings and a sample image, then builds a rotation
matrix from tilt/yaw and computes a homography to warp the image. It now
accepts manual `--tilt` and `--yaw` values or prompts the user interactively.
"""

import argparse
import json
import os
import cv2
import numpy as np


ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_SETTINGS = os.path.join(ROOT, 'res', 'camera_settings.json')
DEFAULT_SAMPLE = os.path.join(ROOT, 'sample', 'testimage.png')
DEFAULT_OUT = os.path.join(ROOT, 'sample', 'testimage_rectified_yaw_corrected_manual.png')


def canonicalize_yaw(yaw_deg: float) -> float:
    # normalize into [-180,180)
    return ((yaw_deg + 180) % 360) - 180


def choose_corrected_yaw(yaw_deg: float) -> float:
    yaw_norm = canonicalize_yaw(yaw_deg)
    if abs(yaw_norm) > 90:
        yaw_corrected = yaw_deg + 180
    else:
        yaw_corrected = yaw_deg
    return canonicalize_yaw(yaw_corrected)


def prompt_float(prompt_text: str, default: float) -> float:
    raw = input(f"{prompt_text} [{default}]: ").strip()
    if raw == "":
        return default
    return float(raw)


def build_rotation_from_tilt_yaw(tilt_deg: float, yaw_deg: float):
    tilt_rad = np.deg2rad(tilt_deg)
    yaw_rad = np.deg2rad(yaw_deg)
    ct = np.cos(tilt_rad)
    st = np.sin(tilt_rad)
    cy = np.cos(yaw_rad)
    sy = np.sin(yaw_rad)
    col0 = np.array([ct * cy, ct * sy, -st], dtype=np.float64)

    cand_col1_a = np.array([-sy, cy, 0.0], dtype=np.float64)
    cand_col1_b = np.array([sy, -cy, 0.0], dtype=np.float64)

    def build_R(col1):
        col1n = col1 / (np.linalg.norm(col1) + 1e-12)
        col2 = np.cross(col0, col1n)
        R = np.column_stack((col0, col1n, col2))
        U, _, Vt = np.linalg.svd(R)
        return U @ Vt

    R_a = build_R(cand_col1_a)
    R_b = build_R(cand_col1_b)
    z_a = np.arctan2(R_a[1, 0], R_a[0, 0])
    z_b = np.arctan2(R_b[1, 0], R_b[0, 0])
    chosen = 'a' if abs(z_a) <= abs(z_b) else 'b'
    R_recon = R_a if chosen == 'a' else R_b
    return R_recon, chosen, (z_a, z_b)


def rectify_image(img_path: str, out_path: str, camera_matrix: np.ndarray, tilt_deg: float, yaw_deg: float,
                  expand_canvas: bool = True, pad: int = 20, shift_x: int = 0, shift_y: int = 0):
    img = cv2.imread(img_path)
    if img is None:
        raise RuntimeError(f'Failed to open sample image at {img_path}')

    R_recon, chosen, (z_a, z_b) = build_rotation_from_tilt_yaw(tilt_deg, yaw_deg)

    h, w = img.shape[:2]
    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2]
    cy = camera_matrix[1, 2]

    src_corners = np.array([[0.0, 0.0], [w - 1.0, 0.0], [w - 1.0, h - 1.0], [0.0, h - 1.0]], dtype=np.float32)
    dst_corners = []
    R_inv = R_recon.T
    for (u, v) in src_corners:
        x = (u - cx) / fx
        y = (v - cy) / fy
        vec = np.array([x, y, 1.0], dtype=np.float64)
        vec_rot = R_inv @ vec
        if abs(vec_rot[2]) < 1e-9:
            u2 = cx
            v2 = cy
        else:
            u2 = fx * (vec_rot[0] / vec_rot[2]) + cx
            v2 = fy * (vec_rot[1] / vec_rot[2]) + cy
        dst_corners.append([u2, v2])

    dst_corners = np.array(dst_corners, dtype=np.float32)
    H = cv2.getPerspectiveTransform(src_corners, dst_corners)

    # Determine output canvas size. If expand_canvas is True and the projected
    # dst_corners fall outside the original [0,w)x[0,h) region, expand the
    # canvas and apply a translation so the whole projected quad is visible.
    if expand_canvas:
        min_xy = dst_corners.min(axis=0)
        max_xy = dst_corners.max(axis=0)
        min_x, min_y = min_xy
        max_x, max_y = max_xy

        # compute required offsets to make all dst_corners positive within new canvas
        off_x = int(max(0, -np.floor(min_x)) + pad + shift_x)
        off_y = int(max(0, -np.floor(min_y)) + pad + shift_y)

        new_w = int(np.ceil(max(w, max_x + off_x + pad)))
        new_h = int(np.ceil(max(h, max_y + off_y + pad)))

        # build translation matrix to shift projected coords into positive canvas
        T = np.array([[1.0, 0.0, off_x], [0.0, 1.0, off_y], [0.0, 0.0, 1.0]], dtype=np.float64)
        H_t = T @ H
        res = cv2.warpPerspective(img, H_t, (new_w, new_h), flags=cv2.INTER_LINEAR)
    else:
        res = cv2.warpPerspective(img, H, (w, h), flags=cv2.INTER_LINEAR)

    cv2.imwrite(out_path, res)

    return dict(
        src_corners=src_corners,
        dst_corners=dst_corners,
        chosen=chosen,
        z_a=z_a,
        z_b=z_b,
        out_path=out_path,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--settings', '-s', default=DEFAULT_SETTINGS)
    p.add_argument('--sample', default=DEFAULT_SAMPLE)
    p.add_argument('--out', default=DEFAULT_OUT)
    p.add_argument('--tilt', type=float, help='Tilt in degrees (overrides settings)')
    p.add_argument('--yaw', type=float, help='Yaw in degrees (overrides settings)')
    p.add_argument('--correct-yaw', action='store_true', help='If yaw looks like near +/-180, add 180 deg to get small angle')
    p.add_argument('--no-prompt', action='store_true', help='Do not prompt interactively; require --tilt/--yaw or use settings')
    p.add_argument('--expand', action='store_true', help='Expand output canvas to include projected corners (default: off)')
    p.add_argument('--pad', type=int, default=20, help='Padding (pixels) when expanding canvas')
    p.add_argument('--shift-x', type=int, default=0, help='Additional horizontal shift (pixels) when expanding; positive moves content right')
    p.add_argument('--shift-y', type=int, default=0, help='Additional vertical shift (pixels) when expanding; positive moves content down')
    args = p.parse_args()

    with open(args.settings, 'r') as f:
        data = json.load(f)

    selected = data.get('selected_camera')
    cam = data.get(selected, {})
    pers = cam.get('intrinsic', {}).get('perspective', {})
    geom = cam.get('intrinsic', {}).get('geometric', {})

    tilt_default = pers.get('tilt_deg')
    yaw_default = pers.get('yaw_deg')

    if args.tilt is None and not args.no_prompt:
        if tilt_default is None:
            raise SystemExit('Tilt not in settings and not provided')
        args.tilt = prompt_float('Tilt (deg)', float(tilt_default))
    if args.yaw is None and not args.no_prompt:
        if yaw_default is None:
            raise SystemExit('Yaw not in settings and not provided')
        args.yaw = prompt_float('Yaw (deg)', float(yaw_default))

    # Fall back to settings if still None
    tilt_use = args.tilt if args.tilt is not None else float(tilt_default)
    yaw_use = args.yaw if args.yaw is not None else float(yaw_default)

    # Optionally correct yaw automatically
    if args.correct_yaw:
        yaw_use = choose_corrected_yaw(yaw_use)

    if 'camera_matrix' not in geom:
        raise SystemExit('No camera_matrix found; abort')

    camera_matrix = np.array(geom['camera_matrix'], dtype=np.float64)

    # If camera settings include translate_x/translate_y and the user did not
    # provide explicit --shift-x/--shift-y, prefer the stored translations when
    # expanding the canvas.
    shift_x = args.shift_x
    shift_y = args.shift_y
    if args.expand:
        tx = pers.get('translate_x') if pers else None
        ty = pers.get('translate_y') if pers else None
        if tx is not None and ty is not None and args.shift_x == 0 and args.shift_y == 0:
            shift_x = int(tx)
            shift_y = int(ty)

    info = rectify_image(args.sample, args.out, camera_matrix, tilt_use, yaw_use,
                         expand_canvas=args.expand, pad=args.pad, shift_x=shift_x, shift_y=shift_y)

    print(f"Used tilt={tilt_use}, yaw={yaw_use}")
    print('src_corners:', info['src_corners'])
    print('dst_corners:', info['dst_corners'])
    print('chosen candidate:', info['chosen'], 'z_a,z_b:', info['z_a'], info['z_b'])
    print('Wrote rectified image to', info['out_path'])


if __name__ == '__main__':
    main()
