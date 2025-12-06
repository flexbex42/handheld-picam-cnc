#!/bin/bash
# Installation script für PyQt5 GUI Autostart

echo "=== PyQt5 GUI Autostart Installation ==="
echo ""

# 1. SystemD Service-Datei kopieren
echo "[1/4] Kopiere Service-Datei..."
sudo cp /home/flex/uis/scripts/pyqt5-gui.service /etc/systemd/system/
echo "✓ Service-Datei kopiert nach /etc/systemd/system/"
echo ""

# 2. SystemD neu laden
echo "[2/4] Lade SystemD-Daemon neu..."
sudo systemctl daemon-reload
echo "✓ SystemD-Daemon neu geladen"
echo ""

# 3. Service aktivieren (Autostart)
echo "[3/4] Aktiviere Autostart..."
sudo systemctl enable pyqt5-gui.service
echo "✓ Autostart aktiviert"
echo ""

# 4. Service starten (für Test)
echo "[4/4] Starte Service..."
sudo systemctl start pyqt5-gui.service
echo "✓ Service gestartet"
echo ""

echo "=== Installation abgeschlossen! ==="
echo ""
echo "Nützliche Befehle:"
echo "  Status prüfen:    sudo systemctl status pyqt5-gui.service"
echo "  Logs anzeigen:    sudo journalctl -u pyqt5-gui.service -f"
echo "  Service stoppen:  sudo systemctl stop pyqt5-gui.service"
echo "  Service starten:  sudo systemctl start pyqt5-gui.service"
echo "  Autostart aus:    sudo systemctl disable pyqt5-gui.service"
echo ""
