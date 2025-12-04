# PyQt5 GUI Projekt - Raspberry Pi

## 📁 Projektstruktur

```
/home/flex/diy/uis/
├── mainwindow.ui           # Qt Designer UI-Datei (MASTER)
├── mainwindow.py           # Generierte UI-Datei (NICHT EDITIEREN!)
├── main.py                 # Hauptanwendung mit Logik
├── pyqt5-gui.service       # SystemD Service-Datei
├── install-service.sh      # Installations-Script für Autostart
├── test-gui.sh             # Test-Script für manuellen Start
└── README.md               # Diese Datei
```

## 🎯 Funktionen

### Aktuell implementiert:
- **Button A**: Zeigt "Button A" im Display-Label
- **Button B**: Zeigt "Button B" im Display-Label  
- **Exit Button**: Beendet die Anwendung
- **Trennung UI/Logik**: UI in `mainwindow.py`, Logik in `main.py`

## 🚀 Verwendung

### Manuelle Tests

**Option 1: Test-Script verwenden** (empfohlen)
```bash
cd /home/flex/diy/uis
./test-gui.sh
```

**Option 2: Direkter Start**
```bash
cd /home/flex/diy/uis
DISPLAY=:0 /usr/bin/python3 main.py
```

### Autostart installieren

```bash
cd /home/flex/diy/uis
./install-service.sh
```

### Service-Verwaltung

```bash
# Status prüfen
sudo systemctl status pyqt5-gui.service

# Logs in Echtzeit anzeigen
sudo journalctl -u pyqt5-gui.service -f

# Service stoppen
sudo systemctl stop pyqt5-gui.service

# Service starten
sudo systemctl start pyqt5-gui.service

# Service neustarten
sudo systemctl restart pyqt5-gui.service

# Autostart deaktivieren
sudo systemctl disable pyqt5-gui.service

# Autostart aktivieren
sudo systemctl enable pyqt5-gui.service
```

## 🔧 UI Änderungen

### UI mit Qt Designer bearbeiten:

1. **UI-Datei öffnen:**
   ```bash
   designer mainwindow.ui
   # oder
   qtcreator mainwindow.ui
   ```

2. **Änderungen im Designer durchführen**

3. **UI-Datei neu generieren:**
   ```bash
   cd /home/flex/diy/uis
   pyuic5 -x mainwindow.ui -o mainwindow.py
   ```

4. **Service neustarten (falls aktiv):**
   ```bash
   sudo systemctl restart pyqt5-gui.service
   ```

⚠️ **WICHTIG**: `mainwindow.py` wird bei jedem `pyuic5`-Lauf überschrieben!  
Alle Änderungen an der Logik gehören in `main.py`!

## 📝 Code-Struktur

### main.py - Logik

```python
class MainApp(QMainWindow):
    def __init__(self):
        # UI laden
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Buttons verbinden
        self.ui.ButtonA.clicked.connect(self.on_button_a_clicked)
        self.ui.ButtonB.clicked.connect(self.on_button_b_clicked)
        self.ui.ButtonExit.clicked.connect(self.on_exit_clicked)
    
    def on_button_a_clicked(self):
        # Button A Logik
        self.ui.label.setText("Button A")
```

### Object Names in UI

- **ButtonA**: Erster Button (links oben)
- **ButtonB**: Zweiter Button (links mitte)
- **ButtonExit**: Exit-Button (links unten)
- **label**: Display-Label (rechts)

## 🔍 Troubleshooting

### GUI startet nicht

1. **X-Server prüfen:**
   ```bash
   echo $DISPLAY
   # Sollte ":0" sein
   ```

2. **PyQt5 installiert?**
   ```bash
   python3 -c "from PyQt5 import QtCore; print('PyQt5:', QtCore.PYQT_VERSION_STR)"
   ```

3. **Service-Logs prüfen:**
   ```bash
   sudo journalctl -u pyqt5-gui.service -n 50
   ```

### Snap-Konflikt im VS Code Terminal

Das VS Code Terminal hat Snap-Library-Konflikte. Verwenden Sie:
- Das `test-gui.sh` Script
- Ein normales Terminal (nicht VS Code integriert)
- Den SystemD Service

### Button funktioniert nicht

1. **Object Name in UI prüfen** (Qt Designer)
2. **Signal-Slot-Verbindung prüfen** (`main.py`)
3. **Logs prüfen:**
   ```bash
   sudo journalctl -u pyqt5-gui.service -f
   ```

## 📦 Abhängigkeiten

```bash
sudo apt-get update
sudo apt-get install -y python3-pyqt5 pyqt5-dev-tools
```

**Optional (für später):**
```bash
sudo apt-get install -y python3-opencv
```

## 🎯 Nächste Schritte

1. ✅ **Button-Logik** - Implementiert!
2. ⏳ **Autostart** - Service-Dateien erstellt, Installation mit `./install-service.sh`
3. ⏳ **Video-Integration** - OpenCV + QThread + QImage
4. ⏳ **Erweiterte UI-Elemente**

## 📚 Best Practices

### Trennung UI/Logik

✅ **RICHTIG:**
- UI-Design in `mainwindow.ui` (Qt Designer)
- Generierung mit `pyuic5` → `mainwindow.py`
- Logik in `main.py`

❌ **FALSCH:**
- `mainwindow.py` direkt editieren
- UI-Code in `main.py` schreiben

### Threading für blocking Operations

```python
from PyQt5.QtCore import QThread

class VideoThread(QThread):
    # Für später: OpenCV Video-Capture
    pass
```

### Signal/Slot Pattern

```python
# Button verbinden
self.ui.ButtonA.clicked.connect(self.on_button_a_clicked)

# Handler
def on_button_a_clicked(self):
    self.ui.label.setText("Button A")
```

## 🖥️ SSH-Verbindung

```bash
ssh flex@10.23.57.210
# Passwort: asdf
```

**Von remote starten:**
```bash
ssh flex@10.23.57.210 'DISPLAY=:0 /home/flex/diy/uis/test-gui.sh'
```

## 📄 Dateien erklärt

| Datei | Zweck | Editieren? |
|-------|-------|-----------|
| `mainwindow.ui` | Qt Designer UI-Definit | ✅ Ja (mit Designer) |
| `mainwindow.py` | Generierte UI-Klasse | ❌ Nein (auto-generiert) |
| `main.py` | Anwendungslogik | ✅ Ja |
| `pyqt5-gui.service` | SystemD Service | ⚠️ Bei Bedarf |
| `install-service.sh` | Service-Installer | ⚠️ Bei Bedarf |
| `test-gui.sh` | Test-Script | ⚠️ Bei Bedarf |

---

**Projekt-Status:** ✅ Button-Logik implementiert, Service-Dateien vorbereitet  
**Erstellt:** November 30, 2025  
**Plattform:** Raspberry Pi Zero 2 + PyQt5
