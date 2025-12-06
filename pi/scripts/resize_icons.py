#!/usr/bin/env python3
"""
Resize all PNG icons in a folder to 56x56 pixels
Preserves transparency and creates backups
"""

import os
import sys
from PIL import Image
import shutil

def resize_icons(folder_path, target_size=56, backup=True):
    """
    Resize all PNG files in folder to target_size x target_size
    
    Args:
        folder_path: Path to folder with PNG files
        target_size: Target width/height in pixels (default 56)
        backup: Create .bak backup files (default True)
    """
    
    if not os.path.isdir(folder_path):
        print(f"❌ Fehler: Ordner '{folder_path}' existiert nicht!")
        return
    
    # Finde alle PNG-Dateien
    png_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.png')]
    
    if not png_files:
        print(f"❌ Keine PNG-Dateien in '{folder_path}' gefunden!")
        return
    
    print(f"📁 Verarbeite {len(png_files)} PNG-Dateien in '{folder_path}'")
    print(f"🎯 Zielgröße: {target_size}x{target_size} Pixel")
    print()
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for filename in sorted(png_files):
        filepath = os.path.join(folder_path, filename)
        
        try:
            # Öffne Bild
            img = Image.open(filepath)
            original_size = img.size
            
            # Überspringe wenn bereits richtige Größe
            if img.size == (target_size, target_size):
                print(f"⏭️  {filename:30s} - bereits {target_size}x{target_size}, übersprungen")
                skip_count += 1
                continue
            
            # Erstelle Backup
            if backup:
                backup_path = filepath + '.bak'
                if not os.path.exists(backup_path):
                    shutil.copy2(filepath, backup_path)
            
            # Resize mit hoher Qualität (LANCZOS für Downscaling)
            img_resized = img.resize((target_size, target_size), Image.LANCZOS)
            
            # Speichere (überschreibe Original)
            img_resized.save(filepath, 'PNG', optimize=True)
            
            print(f"✅ {filename:30s} - {original_size[0]}x{original_size[1]} → {target_size}x{target_size}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ {filename:30s} - Fehler: {e}")
            error_count += 1
    
    print()
    print("=" * 60)
    print(f"✅ Erfolgreich: {success_count}")
    print(f"⏭️  Übersprungen: {skip_count}")
    print(f"❌ Fehler: {error_count}")
    print(f"📊 Gesamt: {len(png_files)}")
    
    if backup and success_count > 0:
        print()
        print(f"💾 Backups erstellt: *.png.bak")
        print(f"   Zum Wiederherstellen: rm *.png && rename 's/.png.bak/.png/' *.png.bak")


if __name__ == "__main__":
    # Standardmäßig icons/ Ordner relativ zum Skript
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_icons_dir = os.path.join(os.path.dirname(script_dir), 'icons')
    
    # Parse Argumente
    if len(sys.argv) > 1:
        icons_dir = sys.argv[1]
    else:
        icons_dir = default_icons_dir
    
    target_size = 56
    if len(sys.argv) > 2:
        try:
            target_size = int(sys.argv[2])
        except ValueError:
            print(f"❌ Ungültige Größe: {sys.argv[2]}")
            sys.exit(1)
    
    print("🖼️  PNG Icon Resizer")
    print("=" * 60)
    
    resize_icons(icons_dir, target_size, backup=True)
