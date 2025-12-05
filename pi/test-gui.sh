#!/bin/bash
# Test script für PyQt5 GUI (manueller Start ohne snap-Umgebung)

echo "=== PyQt5 GUI Test-Start ==="

# Prüfe ob UI-Generierung übersprungen werden soll
if [ "$1" != "--skip-ui-gen" ]; then
    echo "[1/3] Generiere UI-Dateien..."
    
    # Generiere icons_rc.py aus icons.qrc
    if [ -f "/home/flex/uis/icons.qrc" ]; then
        echo "  Kompiliere icons.qrc..."
        pyrcc5 /home/flex/uis/icons.qrc -o /home/flex/uis/icons_rc.py
    fi
    
    # Generiere alle .ui Dateien in einer Schleife
    for ui_file in /home/flex/uis/*.ui; do
        if [ -f "$ui_file" ]; then
            # Extrahiere Dateinamen ohne Pfad und Erweiterung
            base_name=$(basename "$ui_file" .ui)
            output_file="/home/flex/uis/${base_name}.py"
            
            echo "  Generiere ${base_name}.py..."
            pyuic5 -x "$ui_file" -o "$output_file"
        fi
    done
    
    echo "✓ UI-Dateien generiert"
else
    echo "[1/3] UI-Generierung übersprungen (keine .ui Änderungen)"
fi

echo ""
echo "[2/3] Starte Anwendung..."
cd /home/flex/uis
DISPLAY=:0 XAUTHORITY=/home/flex/.Xauthority XDG_RUNTIME_DIR=/run/user/1000 /usr/bin/python3 /home/flex/uis/main.py
