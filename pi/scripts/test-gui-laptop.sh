#!/bin/bash
# Laptop Development Script
# Kompiliert UI-Dateien und startet die App im Debug-Modus (640x480 Fenster)

echo "====================================="
echo "PyQt5 GUI Laptop Development"
echo "====================================="

# Gehe zum pi-Verzeichnis (parent von scripts/)
cd "$(dirname "$0")/.."

# Kompiliere icons.qrc
if [ -f "icons/icons.qrc" ]; then
    echo "  Kompiliere icons/icons.qrc..."
    pyrcc5 icons/icons.qrc -o src/icons_rc.py
    if [ $? -ne 0 ]; then
        echo "ERROR: icons.qrc Kompilierung fehlgeschlagen!"
        exit 1
    fi
fi

# Kompiliere alle .ui Dateien zu .py
echo "  Kompiliere UI-Dateien..."
for ui_file in ui/*.ui; do
    if [ -f "$ui_file" ]; then
        # Erstelle Python-Dateinamen (z.B. mainwindow.ui -> mainWin.py)
        base_name=$(basename "$ui_file" .ui)
        
        # Spezielle Namenskonventionen
        case $base_name in
            mainwindow)
                py_file="mainWin.py"
                ;;
            settingswindow)
                py_file="settingsWin.py"
                ;;
            calibrationselectwindow)
                py_file="caliSelectWin.py"
                ;;
            calibrationdistortionwindow)
                py_file="caliDistortionWin.py"
                ;;
            calibrationperspectivewindow)
                py_file="caliPerspectiveWin.py"
                ;;
            caliOffsetWin)
                py_file="caliOffsetWin.py"
                ;;
            loadingwindow)
                py_file="loadingWin.py"
                ;;
            *)
                py_file="${base_name}.py"
                ;;
        esac
        
        echo "    $ui_file -> src/$py_file"
        pyuic5 "$ui_file" -o "src/$py_file"
        
        if [ $? -ne 0 ]; then
            echo "ERROR: Kompilierung von $ui_file fehlgeschlagen!"
            exit 1
        fi
    fi
done

echo ""
echo "====================================="
echo "Starte App im DEBUG-MODUS (640x480)"
echo "====================================="
echo ""

# Setze Debug-Flag und starte App
export DEBUG_MODE=1
cd src
python3 main.py

echo ""
echo "====================================="
echo "App beendet"
echo "====================================="
