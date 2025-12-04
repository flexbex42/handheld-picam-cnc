#!/usr/bin/env python3
"""
Test-Script um Checkerboard-Erkennung zu debuggen
"""

import cv2
import numpy as np
import os

sample_dir = "/home/flex/uis/sample"
checkerboard_sizes = [
    (9, 6),   # 10x7 Quadrate
    (8, 5),   # 9x6 Quadrate
    (7, 4),   # 8x5 Quadrate
    (6, 5),   # 7x6 Quadrate
    (5, 4),   # 6x5 Quadrate
]

print("Testing checkerboard detection on sample images...")
print("=" * 60)

for i in range(1, 4):  # Teste nur erste 3 Bilder
    filename = f"sample_{i:02d}.jpg"
    filepath = os.path.join(sample_dir, filename)
    
    print(f"\n[{filename}]")
    
    if not os.path.exists(filepath):
        print(f"  ERROR: File not found")
        continue
    
    img = cv2.imread(filepath)
    if img is None:
        print(f"  ERROR: Could not load image")
        continue
    
    print(f"  Image shape: {img.shape}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"  Gray range: min={gray.min()}, max={gray.max()}, mean={gray.mean():.1f}")
    
    # Teste verschiedene Checkerboard-Größen
    for size in checkerboard_sizes:
        # Test 1: Mit allen Flags
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        ret1, corners1 = cv2.findChessboardCorners(gray, size, flags)
        
        # Test 2: Nur NORMALIZE
        ret2, corners2 = cv2.findChessboardCorners(gray, size, cv2.CALIB_CB_NORMALIZE_IMAGE)
        
        # Test 3: Keine Flags
        ret3, corners3 = cv2.findChessboardCorners(gray, size, None)
        
        if ret1 or ret2 or ret3:
            print(f"  ✓ Pattern {size[0]}x{size[1]}: FOUND!", end="")
            if ret1:
                print(" (with flags)", end="")
            if ret2:
                print(" (normalize only)", end="")
            if ret3:
                print(" (no flags)", end="")
            print()
        else:
            print(f"  ✗ Pattern {size[0]}x{size[1]}: not found")

print("\n" + "=" * 60)
print("Test complete!")
