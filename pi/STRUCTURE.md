# Ordnerstruktur

## Übersicht

```
pi/
├── src/              # Python Source-Code
│   ├── main.py      # Hauptanwendung
│   ├── settings.py  # Settings-Fenster
│   ├── caliSelect.py     # Kalibrierungs-Auswahl
│   ├── caliDistortion.py # Linsenverzerrung
│   ├── caliPerspective.py # Perspektiv-Kalibrierung
│   ├── caliOffset.py     # Offset-Kalibrierung
│   ├── loader.py         # Ladeanimation
│   └── *Win.py           # Generierte UI-Dateien (nicht committen!)
│
├── ui/               # Qt Designer UI-Definitionen
│   ├── mainWin.ui
│   ├── settingsWin.ui
│   ├── caliSelectWin.ui
│   ├── caliDistortionWin.ui
│   ├── caliPerspectiveWin.ui
│   ├── caliOffsetWin.ui
│   ├── loadingWin.ui
│   ├── caliDialog.ui
│   └── icons.qrc          # Icon-Ressourcen
│
├── icons/            # Icon-Grafiken (PNG)
│   ├── close.png
│   ├── ok.png
│   ├── undo.png
│   ├── plus.png
│   ├── minus.png
│   ├── foto.png
│   └── offset*.png
│
├── res/              # Ressourcen
│   └── styles.qss   # Qt Stylesheet
│
├── test/             # Test-Dateien
│   └── checkerboard*.svg
│
└── scripts/          # Build- und Deploy-Skripte
    ├── test-gui-laptop.sh   # Laptop-Entwicklung (640x480 Fenster)
    ├── test-gui.sh          # Pi Test-Start
    ├── sync-to-pi.sh        # Rsync zum Pi
    ├── install-service.sh   # Systemd Service Installation
    └── pyqt5-gui.service    # Systemd Service-Definition
```

## Verwendung

### Entwicklung auf dem Laptop
```bash
cd /home/flex/diy/handheld-picam-cnc/pi
./scripts/test-gui-laptop.sh
```
Kompiliert alle UI-Dateien und startet die App im Debug-Modus (640x480 Fenster).

### Sync zum Raspberry Pi
```bash
cd /home/flex/diy/handheld-picam-cnc/pi
./scripts/sync-to-pi.sh
```
Synchronisiert alle Dateien zum Pi und startet optional die App.

### Test auf dem Pi
```bash
./scripts/test-gui.sh
```
Kompiliert UI-Dateien und startet die App im Vollbildmodus.

### Service Installation (Autostart beim Boot)
```bash
./scripts/install-service.sh
```
Installiert die App als systemd Service, damit sie automatisch beim Booten startet.

**Service-Befehle:**
```bash
sudo systemctl status pyqt5-gui.service   # Status prüfen
sudo journalctl -u pyqt5-gui.service -f   # Logs anzeigen
sudo systemctl stop pyqt5-gui.service     # Service stoppen
sudo systemctl start pyqt5-gui.service    # Service starten
sudo systemctl disable pyqt5-gui.service  # Autostart deaktivieren
```

## Generierte Dateien

Folgende Dateien werden automatisch generiert und sollten **nicht** ins Git committed werden:
- `src/*Win.py` - Alle UI-Klassen (generiert aus `ui/*.ui`)
- `src/icons_rc.py` - Icon-Ressourcen (generiert aus `ui/icons.qrc`)
- `src/__pycache__/` - Python Bytecode Cache
