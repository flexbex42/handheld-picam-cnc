#!/bin/bash
# Rsync-Script zum Synchronisieren der Dateien auf den Raspberry Pi

PI_USER="flex"
#PI_HOST="10.193.65.210"
PI_HOST="192.168.1.194"
PI_PATH="/home/flex/uis/"
LOCAL_PATH="/home/flex/diy/handheld-picam-cnc/pi/"

# Prüfe ob --force-ui-gen Flag gesetzt ist
FORCE_UI_GEN=false
if [ "$1" == "--force-ui-gen" ]; then
    FORCE_UI_GEN=true
    echo "⚠ Force UI Generation Mode"
fi

echo "=== Sync zu Raspberry Pi ==="
echo "Ziel: ${PI_USER}@${PI_HOST}:${PI_PATH}"
echo ""

# Rsync mit folgenden Optionen:
# -a  = Archiv-Modus (erhält Permissions, Timestamps, etc.)
# -v  = Verbose (zeigt Details)
# -z  = Kompression während Transfer
# -h  = Human-readable Output
# --progress = Zeigt Fortschritt
# --delete = Löscht Dateien auf dem Pi, die lokal nicht mehr existieren
# --exclude = Schließt bestimmte Dateien/Ordner aus
# --itemize-changes = Zeigt welche Dateien geändert wurden

RSYNC_OUTPUT=$(rsync -avzh --itemize-changes \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude '*.autosave' \
    --exclude 'mainwindow.py' \
    --exclude 'settingswindow.py' \
    --exclude 'loadingwindow.py' \
    "${LOCAL_PATH}" \
    "${PI_USER}@${PI_HOST}:${PI_PATH}" 2>&1)

RSYNC_EXIT=$?

# Prüfe ob .ui Dateien übertragen wurden (rsync itemize format: >f++++++++ file.ui)
UI_FILES_CHANGED=$(echo "$RSYNC_OUTPUT" | grep '\.ui' | wc -l)

echo "$RSYNC_OUTPUT"
echo ""

if [ $RSYNC_EXIT -eq 0 ]; then
    echo "✓ Sync erfolgreich!"
    
    if [ $FORCE_UI_GEN == true ]; then
        echo "  → Force-Modus: UI wird neu generiert"
        UI_GEN_FLAG=""
    elif [ $UI_FILES_CHANGED -gt 0 ]; then
        echo "  → $UI_FILES_CHANGED .ui Datei(en) geändert - UI wird neu generiert"
        UI_GEN_FLAG=""
    else
        echo "  → Keine .ui Dateien geändert - UI-Generierung wird übersprungen"
        UI_GEN_FLAG="--skip-ui-gen"
    fi
    
    echo ""
    echo "Starte GUI auf dem Pi..."
    echo ""
    
    # SSH zum Pi, Script ausführen
    ssh ${PI_USER}@${PI_HOST} "cd ${PI_PATH} && ./test-gui.sh ${UI_GEN_FLAG}"
    
    echo ""
    echo "✓ Zurück auf dem Laptop"
else
    echo "✗ Sync fehlgeschlagen (Exit Code: $RSYNC_EXIT)"
    exit $RSYNC_EXIT
fi
