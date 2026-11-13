# APC Mini LED Controller

Steuert die LEDs des Akai APC Mini **MK1** und **MK2** über MIDI, zeigt die
Pad-Anordnung als interaktives 8×8-Raster im UI an und ordnet Tasten
Windows-Befehlen zu.

---

## Inhaltsverzeichnis

1. [Features](#features)
2. [Screenshots / UI-Aufbau](#ui-aufbau)
3. [Voraussetzungen](#voraussetzungen)
4. [Installation](#installation)
5. [Start](#start)
6. [Bedienung](#bedienung)
7. [Tasten- und Noten-Zuordnung](#tasten--und-noten-zuordnung)
8. [Architektur](#architektur)
9. [Sprachwechsel (i18n)](#sprachwechsel-i18n)
10. [Logging](#logging)
11. [Tests](#tests)
12. [Bekannte Einschränkungen](#bekannte-einschränkungen)
13. [Fehlerbehebung](#fehlerbehebung)
14. [Lizenz](#lizenz)

---

## Features

- **LED-Steuerung**
  - Ein/Aus pro Pad
  - Farbauswahl über Rechtsklick-Kontextmenü
  - RGB-Farben auf MK2 (SysEx), feste Farben auf MK1 (Velocity)
  - Visuelles Feedback im UI: Jedes Pad zeigt seine aktuelle Farbe
- **Raster-UI wie das physische Gerät**
  - 8×8-Matrix (Noten 0–63)
  - Rechte Spalte (Noten 64–71)
  - Untere Reihe (Noten 82–89)
- **Windows-Befehlszuordnung**
  - Beliebig viele Pads mit Windows-Befehlen belegbar
  - Ausführung beim Drücken der physischen Taste
  - Befehle über Kontextmenü oder Tabelle verwalten
- **Laufzeit-Sprachwechsel** Deutsch ⇄ Englisch ohne Neustart
- **Saubere Fehlerbehandlung** mit klaren Meldungen und Logging
- **Sichere Befehlsausführung** (siehe [Sicherheit](#sicherheit))

---

## UI-Aufbau

```
┌──────────────────────────────────────────────────────────────┐
│ Modell: [APC Mini MK1 ▾]  [Verbinden]        Status: ...     │
├───────────────────────────────────┬──────────────────────────┤
│                                   │  Befehle                 │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┐│  ┌──────┬─────────────┐ │
│  │56 │57 │58 │59 │60 │61 │62 │63 ││  │ Note │ Befehl      │ │
│  ├───┼───┼───┼───┼───┼───┼───┼───┤│  ├──────┼─────────────┤ │
│  │48 │49 │50 │51 │52 │53 │54 │55 ││  │ 0    │ notepad.exe │ │
│  ...                              ││  │ 8    │ calc        │ │
│  ├───┼───┼───┼───┼───┼───┼───┼───┤│  └──────┴─────────────┘ │
│  │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 ││  [Befehl entfernen]      │
│  └───┴───┴───┴───┴───┴───┴───┴───┘│                          │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┐│                          │
│  │82 │83 │84 │85 │86 │87 │88 │89 ││                          │
│  └───┴───┴───┴───┴───┴───┴───┴───┘│                          │
│  Linksklick: Farbe setzen          │                          │
│  Rechtsklick: Menü                 │                          │
└───────────────────────────────────┴──────────────────────────┘
```

- **Linksklick** auf ein Pad → setzt die LED auf **Rot** und färbt den Button.
- **Rechtsklick** auf ein Pad → Kontextmenü mit:
  - Farbe (Aus, Rot, Grün, Blau, Gelb, Cyan, Magenta, Weiß)
  - Befehl zuordnen…
  - Befehl entfernen (nur wenn belegt)
- **Physische Taste** drücken → zugeordneter Befehl wird ausgeführt,
  Pad blinkt im UI kurz weiß auf.

---

## Voraussetzungen

| Komponente | Version |
|---|---|
| Python | 3.10 oder neuer |
| Betriebssystem | Windows 10/11 (getestet), Linux/macOS möglich |
| Hardware | Akai APC Mini MK1 oder MK2 |
| MIDI-Backend | `python-rtmidi` (wird via pip installiert) |

**Windows-Hinweis:** `python-rtmidi` benötigt ggf. die
*Microsoft C++ Build Tools* (Visual Studio Installer →
„Desktop development with C++"). Falls die Installation fehlschlägt,
installiere diese zuerst.

---

## Installation

```bash
# 1. Repository klonen oder Dateien kopieren
cd APC_Mini_LED_Controller

# 2. Virtuelle Umgebung (empfohlen)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 3. Abhängigkeiten installieren
pip install mido python-rtmidi ttkbootstrap

# 4. (Optional) Übersetzungen kompilieren
#    Nur nötig, wenn du die .po-Dateien bearbeitest.
#    Die .mo-Dateien sind bereits enthalten.
msgfmt locale/de/LC_MESSAGES/apc_controller.po -o locale/de/LC_MESSAGES/apc_controller.mo
msgfmt locale/en/LC_MESSAGES/apc_controller.po -o locale/en/LC_MESSAGES/apc_controller.mo
```

---

## Start

```bash
python main.py
```

Ablauf:

1. **APC Mini per USB anschließen** (vor dem Start).
2. Modell in der Combobox wählen (`APC Mini MK1` ist Standard).
3. **Verbinden** klicken.
4. Bei Erfolg:
   - Status wechselt auf „Verbunden"
   - Pad 0 leuchtet rot (Gerät + UI)
   - Log-Zeile `MIDI-Output geöffnet: APC MINI …` erscheint in der Konsole
5. Bei Fehler: klare Fehlermeldung mit Hinweis auf Portnamen.

---

## Bedienung

### LED setzen

- **Linksklick** auf ein Pad → Rot.
- **Rechtsklick → Farbe** → gewünschte Farbe.
- Die LED am Gerät und der Button im UI wechseln synchron.

### Befehl zuordnen

1. **Rechtsklick** auf das gewünschte Pad.
2. **Befehl zuordnen…** wählen.
3. Windows-Befehl eingeben, z. B.:
   - `notepad.exe`
   - `calc`
   - `start chrome`
   - `start "" "C:\Pfad\zu\programm.exe"`
4. **OK** → Befehl erscheint in der Tabelle rechts.

### Befehl entfernen

- Über die Tabelle: Zeile markieren → **Befehl entfernen**, oder
- Rechtsklick auf das Pad → **Befehl entfernen**.

### Befehl ausführen

- Physische Taste am APC Mini drücken.
- Befehl wird ausgeführt, Pad blinkt im UI.

---

## Tasten- und Noten-Zuordnung

Basierend auf der offiziellen APC-Mini-Belegung (bestätigt durch
den `APCMiniTester`):

| Bereich | Noten | Beschreibung |
|---|---|---|
| Matrix | 0–63 | 8×8-Raster, Note 0 = unten links |
| Rechte Spalte | 64–71 | 8 Buttons, Note 64 = unten |
| Untere Reihe | 82–89 | 8 Buttons, Note 82 = links |

Farbwerte (MK1, Velocity):

| Wert | Farbe |
|---|---|
| 0 | Aus |
| 1 | Grün |
| 2 | Grün blinkend |
| 3 | Rot |
| 4 | Rot blinkend |
| 5 | Gelb |
| 6 | Gelb blinkend |

MK2 nutzt SysEx für RGB-Pads (Noten 0–63) und Note-On für Peripherie.
Die RGB-Werte werden intern von 0–127 auf 8-Bit MSB/LSB aufgeteilt.

---

## Architektur

Clean Architecture mit strikter Schichtentrennung:

```
APC_Mini_LED_Controller/
├── domain/                     # Geschäftslogik, frameworkfrei
│   ├── models.py               # LedColor, ButtonMapping, DeviceModel
│   └── exceptions.py           # ApcError, MidiConnectionError, ...
├── application/                # Use Cases
│   ├── led_service.py          # LED-Steuerung
│   └── command_service.py      # Windows-Befehle ausführen
├── infrastructure/             # Adapter zur Außenwelt
│   ├── midi_adapter.py         # mido / python-rtmidi
│   └── apc_protocol.py         # MK1- und MK2-Protokoll
├── presentation/               # UI-Schicht
│   ├── main_window.py          # Tkinter + ttkbootstrap
│   └── i18n.py                 # gettext + Laufzeit-Sprachwechsel
├── locale/                     # Übersetzungen
│   ├── de/LC_MESSAGES/apc_controller.{po,mo}
│   └── en/LC_MESSAGES/apc_controller.{po,mo}
├── tests/                      # Unit-, Integrations-, E2E-Tests
│   ├── test_protocol.py
│   ├── test_midi_adapter.py
│   └── test_e2e_gui.py
├── main.py                     # Composition Root
└── README.md
```

**Abhängigkeitsrichtung:** `presentation` → `application` → `domain`.
`infrastructure` implementiert die Ports, die `application` benötigt.
`domain` kennt keine äußeren Schichten.

---

## Sprachwechsel (i18n)

- Übersetzungen liegen unter `locale/<lang>/LC_MESSAGES/apc_controller.mo`.
- Beim Start wird `de` geladen; fehlt die Datei, wird auf die
  Originalstrings zurückgefallen (kein Crash).
- Der Wechsel zur Laufzeit erfolgt über die Links `Deutsch` / `English`
  unten im Fenster.
- `I18nManager` benachrichtigt alle registrierten Listener, die ihre
  Widget-Texte neu setzen.

### Neue Sprache hinzufügen

1. Ordner `locale/<lang>/LC_MESSAGES/` anlegen.
2. `apc_controller.po` aus einer bestehenden Sprache kopieren und
   übersetzen.
3. `msgfmt` ausführen (siehe [Installation](#installation)).
4. Sprachcode in `presentation/main_window.py` als Link ergänzen.

---

## Logging

- Ausgabe auf `stdout` mit Zeitstempel, Level und Logger-Name.
- Level: `INFO` (Standard). Für mehr Details in `main.py` auf
  `DEBUG` ändern:

  ```python
  logging.basicConfig(level=logging.DEBUG, ...)
  ```

- Wichtige Log-Meldungen:
  - `MIDI-Output geöffnet: <name>`
  - `MIDI-Input geöffnet: <name>` (oder Warnung, falls nicht vorhanden)
  - `Befehl ausgeführt für Note <n>: <cmd>`
  - `MIDI-Nachricht fehlgeschlagen (...): <details>`
  - `Polling-Fehler: <details>`

---

## Tests

Die Test-Suite deckt drei Ebenen ab:

### Unit-Tests (Protokoll, Value Objects)

```bash
pytest tests/test_protocol.py -v
```

Prüft:
- MK1- und MK2-Protokoll erzeugen korrekte MIDI-Bytes
- Ungültige Noten werfen `InvalidLedCommandError`
- MK2-SysEx enthält das `<type>`-Byte und korrekte Längen

### Integration-Tests (MIDI-Adapter)

```bash
pytest tests/test_midi_adapter.py -v
```

Prüft:
- `connect()` ohne Gerät wirft `MidiConnectionError`
- Fehlerhafte MIDI-Nachrichten werden geloggt und weitergeworfen
- `poll_input()` liefert nur Note-On mit Velocity > 0

### E2E-Tests (GUI)

```bash
pytest tests/test_e2e_gui.py -v
```

Prüft:
- Fenstertitel
- Befehlszuordnung über die Tabelle
- Raster-Buttons existieren für alle 80 gültigen Noten

**CI-Hinweis:** Tkinter-Tests benötigen ein Display. Unter Linux
`xvfb-run pytest tests/` verwenden.

---

## Bekannte Einschränkungen

- **MK1-Farben sind vereinfacht**: nur Grün/Rot/Gelb (plus Blink-
  Varianten). RGB ist auf dem MK1 hardwareseitig nicht möglich.
- **MK2-SysEx erfordert Firmware ≥ 1.0** und ein korrekt arbeitendes
  MIDI-Backend. Bei sehr alten Firmware-Versionen kann die
  RGB-Steuerung fehlschlagen.
- **Portnamen unter Windows** können je nach System variieren
  (`APC MINI 0`, `APC MINI 1`, `APC MINI`). Der Adapter sucht
  automatisch nach `apc` im Namen und wählt Output/Input getrennt.
  Bei Sonderfällen Portnamen in `midi_adapter.py` anpassen.
- **Ein MIDI-Port, ein Programm**: Unter Windows kann nur ein Programm
  gleichzeitig auf den APC Mini zugreifen. Schließe DAWs und andere
  MIDI-Tools vor dem Start.
- **Befehlsausführung mit `shell=True`**: siehe [Sicherheit](#sicherheit).

### Sicherheit

`command_service.py` verwendet `subprocess.Popen(cmd, shell=True)`, um
Windows-Befehle wie `start chrome` oder Pfade mit Leerzeichen zu
unterstützen. Die Befehle stammen ausschließlich aus der lokalen
GUI-Eingabe des Benutzers – es gibt keine externe Angriffsfläche.

Für maximale Härtung:

- Befehle aus einer **Allowlist** akzeptieren.
- `shlex.split(cmd)` + `shell=False` verwenden (schränkt die Syntax ein).

---

## Fehlerbehebung

| Symptom | Ursache | Lösung |
|---|---|---|
| `MIDI-Fehler: Kein APC Mini unter Outputs gefunden` | Gerät nicht angeschlossen, Treiber fehlt, oder Port belegt | USB prüfen, andere MIDI-Software schließen, `mido.get_output_names()` prüfen |
| LEDs reagieren nicht, aber Verbindung steht | Falsches Modell gewählt (MK2 statt MK1) | Combobox auf korrektes Modell stellen |
| `ModuleNotFoundError: rtmidi` | `python-rtmidi` fehlt | `pip install python-rtmidi` |
| `RuntimeError: main thread is not in main loop` | GUI aus Worker-Thread angesprochen | Tritt in dieser Version nicht mehr auf (Polling im Main-Thread) |
| Pad blinkt im UI, aber Befehl wird nicht ausgeführt | Befehl fehlerhaft oder Pfad ungültig | Konsole auf `Befehl konnte nicht ausgeführt werden` prüfen |
| Sprachwechsel zeigt Originalstrings | `.mo`-Datei fehlt | `msgfmt` ausführen (siehe Installation) |

### Diagnose-Befehle

```python
# Alle MIDI-Ports anzeigen
import mido
print("Outputs:", mido.get_output_names())
print("Inputs :", mido.get_input_names())

# Einzelnen Port testen (LED 0 rot auf MK1)
import mido, time
with mido.open_output("APC MINI 1") as out:
    out.send(mido.Message("note_on", note=0, velocity=3))
    time.sleep(1)
    out.send(mido.Message("note_on", note=0, velocity=0))
```

---

## Danksagung

- [mido](https://mido.readthedocs.io/) – MIDI-Bibliothek
- [python-rtmidi](https://pypi.org/project/python-rtmidi/) – MIDI-Backend
- [ttkbootstrap](https://ttkbootstrap.readthedocs.io/) – moderne Tk-Themes
- AKAI – für die APC-Mini-Protokolldokumentation

---
