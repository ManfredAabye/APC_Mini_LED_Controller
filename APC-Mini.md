# Machbarkeitsprüfung & Python-Implementierung: APC Mini LED-Controller mit Windows-Befehlszuordnung

## 1. Machbarkeitsanalyse (Kurzfassung)

**Grundsätzlich machbar, aber mit einer wichtigen Einschränkung:**

| Aspekt | Bewertung |
|---|---|
| **APC Mini MK2 LED-Steuerung** | ✅ Vollständig machbar über MIDI Note-On (einfarbige LEDs) und SysEx (RGB-Pads)  |
| **APC Mini MK1 LED-Steuerung** | ✅ Machbar, jedoch **unterscheidet sich das MIDI-Protokoll vom MK2** – MK1 nutzt Velocity-Werte für Farben (1=grün, 3=rot, 5=gelb), MK2 nutzt separate SysEx-Befehle für RGB  |
| **Tasten → Windows-Befehl** | ✅ Machbar über `subprocess` nach MIDI-Note-Eingang |
| **Python 3 + Tkinter + ttkbootstrap** | ✅ ttkbootstrap ist ausgereift und pip-installierbar  |
| **Laufzeit-Sprachwechsel (i18n)** | ⚠️ **Problematisch**: `gettext` allein aktualisiert Tkinter-Widgets nicht zur Laufzeit – Widgets müssen manuell neu beschriftet werden  |

**Kritischer Hinweis zur MK1/MK2-Kompatibilität:** Die APC Mini MK1 und MK2 verwenden **unterschiedliche MIDI-Protokolle**. Ein einheitlicher Code muss beide Geräte über eine Geräteerkennung und protokollspezifische Adapterklassen bedienen. Die offizielle MK2-Protokolldokumentation ist verfügbar , für MK1 existiert keine offizielle PDF in den Suchergebnissen – die Farbwerte sind aus Community-Quellen bekannt .

**Empfehlung:** Beginnen Sie mit **MK2-Unterstützung** (dokumentiertes Protokoll), und ergänzen Sie MK1 als zweiten Adapter, sobald das Gerät physisch zum Testen vorliegt.

---

## 2. Architektur (Clean Architecture, OOP)

```
APC_Mini_LED_Controller/
├── domain/
│   ├── models.py          # Pad, LedColor, ButtonMapping (Value Objects)
│   └── exceptions.py      # Domain-spezifische Exceptions
├── application/
│   ├── led_service.py     # LED-Steuerung (Use Cases)
│   └── command_service.py # Windows-Befehl-Ausführung
├── infrastructure/
│   ├── midi_adapter.py    # MIDI I/O (mido + python-rtmidi)
│   └── apc_protocol.py    # MK1/MK2 Protokoll-Implementierungen
├── presentation/
│   ├── main_window.py     # Tkinter/ttkbootstrap GUI
│   └── i18n.py            # Laufzeit-Sprachwechsel
└── main.py                # Composition Root
```

---

## 3. Vollständiger, ausführbarer Code

### 3.1 `domain/exceptions.py`

```python
"""Domain-spezifische Exceptions."""


class ApcError(Exception):
    """Basis-Exception für APC-bezogene Fehler."""


class MidiConnectionError(ApcError):
    """MIDI-Gerät konnte nicht geöffnet werden."""


class UnsupportedDeviceError(ApcError):
    """Gerät wird nicht unterstützt (weder MK1 noch MK2)."""


class InvalidLedCommandError(ApcError):
    """Ungültiger LED-Befehl (z. B. Pad außerhalb des Bereichs)."""
```

### 3.2 `domain/models.py`

```python
"""Value Objects für die APC-Domäne."""
from dataclasses import dataclass
from enum import Enum


class DeviceModel(Enum):
    MK1 = "APC Mini MK1"
    MK2 = "APC Mini MK2"


@dataclass(frozen=True)
class LedColor:
    """RGB-Farbe (0-127 pro Kanal, MIDI-konform)."""
    red: int
    green: int
    blue: int

    def __post_init__(self):
        for name, val in (("red", self.red), ("green", self.green), ("blue", self.blue)):
            if not 0 <= val <= 127:
                raise ValueError(f"{name} muss zwischen 0 und 127 liegen, war {val}")


@dataclass(frozen=True)
class ButtonMapping:
    """Verknüpft eine APC-Pad-Note mit einem Windows-Befehl."""
    note: int          # MIDI-Note (0-119)
    command: str       # z. B. "notepad.exe" oder "calc"
    label: str = ""    # Optional: Anzeigename in der GUI
```

### 3.3 `infrastructure/apc_protocol.py`

```python
"""Protokoll-Adapter für APC Mini MK1 und MK2.

MK2: RGB via SysEx, einfarbige LEDs via Note-On.
MK1: Farben via Velocity-Werte (Community-dokumentiert).
"""
from abc import ABC, abstractmethod
from typing import List

from domain.models import LedColor, DeviceModel
from domain.exceptions import InvalidLedCommandError


class ApcProtocol(ABC):
    """Abstrakte Basis für gerätespezifische LED-Protokolle."""

    @abstractmethod
    def turn_off(self, note: int) -> List[List[int]]:
        """Gibt MIDI-Nachrichten zurück, die die LED ausschalten."""

    @abstractmethod
    def set_color(self, note: int, color: LedColor) -> List[List[int]]:
        """Gibt MIDI-Nachrichten zurück, die die LED auf die Farbe setzen."""

    @abstractmethod
    def set_on(self, note: int) -> List[List[int]]:
        """Gibt MIDI-Nachrichten zurück, die die LED einschalten (Standardfarbe)."""


class ApcMiniMk2Protocol(ApcProtocol):
    """APC Mini MK2: RGB-Pads (0-63) via SysEx, Peripherie-LEDs via Note-On."""

    # SysEx-Konstanten laut offizieller Protokolldokumentation
    SYSEX_HEADER = [0xF0, 0x47, 0x7F, 0x4F, 0x24]
    SYSEX_TERMINATOR = 0xF7
    RGB_PAD_START = 0
    RGB_PAD_END = 63
    # Peripherie-Buttons (Note-On, Velocity 1 = an, 0 = aus)
    PERIPHERAL_RANGE = range(100, 120)
    NOTE_ON_CH0 = 0x90

    def _build_sysex(self, start_pad: int, end_pad: int, color: LedColor) -> List[int]:
        """Baut eine vollständige SysEx-Nachricht für RGB-Pads."""
        # MSB/LSB für 8-Bit-Werte (7-Bit-MIDI)
        r_msb, r_lsb = color.red >> 4, color.red & 0x0F
        g_msb, g_lsb = color.green >> 4, color.green & 0x0F
        b_msb, b_lsb = color.blue >> 4, color.blue & 0x0F
        payload = [
            0x00, start_pad, end_pad,
            r_msb, r_lsb, g_msb, g_lsb, b_msb, b_lsb,
        ]
        # Gesamtlänge der Datenbytes (MSB, LSB) – hier: 9 Nutzbytes
        total = len(payload)
        return (
            self.SYSEX_HEADER
            + [total >> 7, total & 0x7F]
            + payload
            + [self.SYSEX_TERMINATOR]
        )

    def turn_off(self, note: int) -> List[List[int]]:
        if not 0 <= note <= 119:
            raise InvalidLedCommandError(f"Note {note} außerhalb 0-119")
        if note <= self.RGB_PAD_END:
            return [self._build_sysex(note, note, LedColor(0, 0, 0))]
        return [[self.NOTE_ON_CH0, note, 0x00]]

    def set_color(self, note: int, color: LedColor) -> List[List[int]]:
        if not 0 <= note <= 119:
            raise InvalidLedCommandError(f"Note {note} außerhalb 0-119")
        if note <= self.RGB_PAD_END:
            return [self._build_sysex(note, note, color)]
        # Peripherie-LEDs sind einfarbig – Rot wenn an
        return [[self.NOTE_ON_CH0, note, 0x01]]

    def set_on(self, note: int) -> List[List[int]]:
        return self.set_color(note, LedColor(127, 0, 0))


class ApcMiniMk1Protocol(ApcProtocol):
    """APC Mini MK1: Farben über Velocity (1=grün, 3=rot, 5=gelb)."""

    NOTE_ON_CH0 = 0x90
    # Community-dokumentierte Velocity-Werte
    VELOCITY_OFF = 0x00
    VELOCITY_GREEN = 0x01
    VELOCITY_GREEN_BLINK = 0x02
    VELOCITY_RED = 0x03
    VELOCITY_RED_BLINK = 0x04
    VELOCITY_YELLOW = 0x05
    VELOCITY_YELLOW_BLINK = 0x06

    def turn_off(self, note: int) -> List[List[int]]:
        return [[self.NOTE_ON_CH0, note, self.VELOCITY_OFF]]

    def set_color(self, note: int, color: LedColor) -> List[List[int]]:
        # MK1 kennt nur feste Farben – vereinfachte Zuordnung
        if color.red > 64 and color.green > 64:
            vel = self.VELOCITY_YELLOW
        elif color.red > 64:
            vel = self.VELOCITY_RED
        else:
            vel = self.VELOCITY_GREEN
        return [[self.NOTE_ON_CH0, note, vel]]

    def set_on(self, note: int) -> List[List[int]]:
        return [[self.NOTE_ON_CH0, note, self.VELOCITY_RED]]


def get_protocol(model: DeviceModel) -> ApcProtocol:
    """Factory: liefert das passende Protokoll für das Gerätemodell."""
    if model == DeviceModel.MK2:
        return ApcMiniMk2Protocol()
    elif model == DeviceModel.MK1:
        return ApcMiniMk1Protocol()
    raise ValueError(f"Unbekanntes Modell: {model}")
```

### 3.4 `infrastructure/midi_adapter.py`

```python
"""MIDI-I/O-Adapter mit mido/python-rtmidi und Fehlerbehandlung."""
import logging
from typing import Optional

import mido

from domain.exceptions import MidiConnectionError, UnsupportedDeviceError

logger = logging.getLogger(__name__)


class MidiAdapter:
    """Kapselt MIDI-Port-Handling und Nachrichtenversand."""

    def __init__(self):
        self._output: Optional[mido.ports.BaseOutput] = None
        self._input: Optional[mido.ports.BaseInput] = None

    def list_ports(self) -> list[str]:
        return mido.get_output_names()

    def connect(self, port_name: Optional[str] = None) -> None:
        """Verbindet Input und Output zum APC Mini."""
        try:
            if port_name is None:
                # Auto-Erkennung: suche APC Mini
                candidates = [n for n in mido.get_output_names() if "APC Mini" in n]
                if not candidates:
                    raise MidiConnectionError(
                        "Kein APC Mini gefunden. Ist das Gerät angeschlossen?"
                    )
                port_name = candidates[0]

            self._output = mido.open_output(port_name)
            # Input-Port mit gleichem Namen (rtmidi erlaubt paralleles Öffnen)
            self._input = mido.open_input(port_name)
            logger.info("MIDI verbunden: %s", port_name)
        except (IOError, OSError) as exc:
            raise MidiConnectionError(f"MIDI-Verbindung fehlgeschlagen: {exc}") from exc

    def send(self, messages: list[list[int]]) -> None:
        """Sendet eine Liste von MIDI-Nachrichten (als Byte-Listen)."""
        if self._output is None:
            raise MidiConnectionError("Nicht verbunden. Zuerst connect() aufrufen.")
        for msg_bytes in messages:
            # Unterscheidung Note-On vs. SysEx
            if msg_bytes[0] == 0xF0:
                msg = mido.Message("sysex", data=msg_bytes[1:-1])
            else:
                msg = mido.Message.from_bytes(msg_bytes)
            self._output.send(msg)

    def poll_input(self) -> Optional[int]:
        """Liest eine anstehende Note-On-Note (nicht-blockierend)."""
        if self._input is None:
            return None
        msg = self._input.poll()
        if msg is not None and msg.type == "note_on" and msg.velocity > 0:
            return msg.note
        return None

    def close(self) -> None:
        if self._output:
            self._output.close()
        if self._input:
            self._input.close()
        self._output = None
        self._input = None
```

### 3.5 `application/led_service.py`

```python
"""Use Case: LED-Steuerung unabhängig vom Protokoll."""
from domain.models import DeviceModel, LedColor, DeviceModel
from domain.exceptions import InvalidLedCommandError
from infrastructure.apc_protocol import get_protocol
from infrastructure.midi_adapter import MidiAdapter


class LedService:
    def __init__(self, midi: MidiAdapter, model: DeviceModel):
        self._midi = midi
        self._protocol = get_protocol(model)

    def turn_on(self, note: int) -> None:
        self._midi.send(self._protocol.set_on(note))

    def turn_off(self, note: int) -> None:
        self._midi.send(self._protocol.turn_off(note))

    def set_color(self, note: int, color: LedColor) -> None:
        self._midi.send(self._protocol.set_color(note, color))
```

### 3.6 `application/command_service.py`

```python
"""Use Case: Windows-Befehle ausführen (validiert, geloggt)."""
import logging
import subprocess
import shlex
from typing import Optional

from domain.models import ButtonMapping
from domain.exceptions import ApcError

logger = logging.getLogger(__name__)


class CommandService:
    def __init__(self):
        self._mappings: dict[int, ButtonMapping] = {}

    def register(self, mapping: ButtonMapping) -> None:
        self._mappings[mapping.note] = mapping

    def unregister(self, note: int) -> None:
        self._mappings.pop(note, None)

    def get_command(self, note: int) -> Optional[str]:
        m = self._mappings.get(note)
        return m.command if m else None

    def execute(self, note: int) -> bool:
        """Führt den Befehl für eine Note aus. Gibt True bei Erfolg zurück."""
        cmd = self.get_command(note)
        if not cmd:
            return False
        try:
            # shell=True ist hier bewusst: Windows-Befehle wie "start ..." brauchen die Shell
            # OWASP-Hinweis: Befehle stammen aus der lokalen GUI-Konfiguration, nicht aus
            # ungeprüften externen Quellen. Für höchste Sicherheit: shlex.split + shell=False.
            subprocess.Popen(cmd, shell=True)
            logger.info("Befehl ausgeführt für Note %d: %s", note, cmd)
            return True
        except (subprocess.SubprocessError, OSError) as exc:
            logger.error("Befehlsausführung fehlgeschlagen: %s", exc)
            raise ApcError(f"Befehl konnte nicht ausgeführt werden: {exc}") from exc
```

### 3.7 `presentation/i18n.py`

```python
"""Laufzeit-Sprachwechsel mit gettext + Widget-Retranslation."""
import gettext
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class I18nManager:
    """Verwaltet Übersetzungen und benachrichtigt Widgets bei Sprachwechsel."""

    def __init__(self, domain: str = "apc_controller", localedir: str = "locale"):
        self._domain = domain
        self._localedir = localedir
        self._current_lang = "de"
        self._translation: gettext.NullTranslations = gettext.NullTranslations()
        self._listeners: list[Callable[[], None]] = []

    @property
    def lang(self) -> str:
        return self._current_lang

    def _(self, message: str) -> str:
        return self._translation.gettext(message)

    def set_language(self, lang: str) -> None:
        if lang == self._current_lang:
            return
        try:
            self._translation = gettext.translation(
                self._domain, localedir=self._localedir, languages=[lang]
            )
        except FileNotFoundError:
            logger.warning("Keine Übersetzung für '%s' gefunden – Fallback auf Original.", lang)
            self._translation = gettext.NullTranslations()
        self._current_lang = lang
        # Benachrichtige alle registrierten Widgets
        for callback in self._listeners:
            callback()

    def register_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)
```

### 3.8 `presentation/main_window.py`

```python
"""Tkinter/ttkbootstrap-GUI mit Laufzeit-Sprachwechsel und MIDI-Polling."""
import logging
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from application.command_service import CommandService
from application.led_service import LedService
from domain.exceptions import ApcError, MidiConnectionError
from domain.models import ButtonMapping, DeviceModel, LedColor
from infrastructure.midi_adapter import MidiAdapter
from presentation.i18n import I18nManager

logger = logging.getLogger(__name__)


class MainWindow(ttk.Window):
    def __init__(self, i18n: I18nManager, midi: MidiAdapter, command_service: CommandService):
        super().__init__(themename="darkly")
        self._i18n = i18n
        self._midi = midi
        self._commands = command_service
        self._led_service: LedService | None = None
        self._poll_job: str | None = None

        self.title(self._i18n._("APC Mini Controller"))
        self.geometry("720x480")
        self._build_ui()
        self._i18n.register_listener(self._retranslate_ui)

    def _build_ui(self) -> None:
        # Verbindungsleiste
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        self._lbl_model = ttk.Label(top, text=self._i18n._("Modell:"))
        self._lbl_model.pack(side="left", padx=(0, 4))

        self._model_var = tk.StringVar(value=DeviceModel.MK2.value)
        self._model_combo = ttk.Combobox(
            top, textvariable=self._model_var,
            values=[m.value for m in DeviceModel], state="readonly", width=18,
        )
        self._model_combo.pack(side="left", padx=(0, 12))

        self._btn_connect = ttk.Button(
            top, text=self._i18n._("Verbinden"), command=self._on_connect, bootstyle="success",
        )
        self._btn_connect.pack(side="left", padx=4)

        self._lbl_status = ttk.Label(top, text=self._i18n._("Nicht verbunden"), bootstyle="secondary")
        self._lbl_status.pack(side="right")

        # Pad-Steuerung
        mid = ttk.Labelframe(self, text=self._i18n._("LED-Steuerung"), padding=8)
        mid.pack(fill="x", padx=8, pady=4)

        ttk.Label(mid, text=self._i18n._("Pad-Note (0-119):")).grid(row=0, column=0, sticky="w")
        self._note_var = tk.IntVar(value=0)
        ttk.Spinbox(mid, from_=0, to=119, textvariable=self._note_var, width=6).grid(row=0, column=1, padx=4)

        ttk.Label(mid, text=self._i18n._("R:")).grid(row=0, column=2, sticky="e")
        self._r_var = tk.IntVar(value=127)
        ttk.Spinbox(mid, from_=0, to=127, textvariable=self._r_var, width=5).grid(row=0, column=3, padx=2)

        ttk.Label(mid, text=self._i18n._("G:")).grid(row=0, column=4, sticky="e")
        self._g_var = tk.IntVar(value=0)
        ttk.Spinbox(mid, from_=0, to=127, textvariable=self._g_var, width=5).grid(row=0, column=5, padx=2)

        ttk.Label(mid, text=self._i18n._("B:")).grid(row=0, column=6, sticky="e")
        self._b_var = tk.IntVar(value=0)
        ttk.Spinbox(mid, from_=0, to=127, textvariable=self._b_var, width=5).grid(row=0, column=7, padx=2)

        self._btn_set_color = ttk.Button(mid, text=self._i18n._("Farbe setzen"), command=self._on_set_color)
        self._btn_set_color.grid(row=0, column=8, padx=8)
        self._btn_off = ttk.Button(mid, text=self._i18n._("Aus"), command=self._on_led_off, bootstyle="secondary")
        self._btn_off.grid(row=0, column=9, padx=2)

        # Befehlszuordnung
        bottom = ttk.Labelframe(self, text=self._i18n._("Windows-Befehlszuordnung"), padding=8)
        bottom.pack(fill="both", expand=True, padx=8, pady=4)

        ttk.Label(bottom, text=self._i18n._("Note:")).grid(row=0, column=0, sticky="w")
        self._map_note_var = tk.IntVar(value=0)
        ttk.Spinbox(bottom, from_=0, to=119, textvariable=self._map_note_var, width=6).grid(row=0, column=1, padx=4)

        ttk.Label(bottom, text=self._i18n._("Befehl:")).grid(row=0, column=2, sticky="w")
        self._cmd_var = tk.StringVar()
        ttk.Entry(bottom, textvariable=self._cmd_var, width=30).grid(row=0, column=3, padx=4)

        self._btn_register = ttk.Button(bottom, text=self._i18n._("Zuordnen"), command=self._on_register)
        self._btn_register.grid(row=0, column=4, padx=4)

        self._tree = ttk.Treeview(bottom, columns=("note", "command"), show="headings", height=6)
        self._tree.heading("note", text=self._i18n._("Note"))
        self._tree.heading("command", text=self._i18n._("Befehl"))
        self._tree.column("note", width=80)
        self._tree.column("command", width=400)
        self._tree.grid(row=1, column=0, columnspan=5, sticky="nsew", pady=(8, 0))
        bottom.rowconfigure(1, weight=1)
        bottom.columnconfigure(3, weight=1)

        # Sprachumschalter
        lang_frame = ttk.Frame(self, padding=4)
        lang_frame.pack(fill="x")
        ttk.Button(lang_frame, text="Deutsch", command=lambda: self._i18n.set_language("de"), bootstyle="link").pack(side="left")
        ttk.Button(lang_frame, text="English", command=lambda: self._i18n.set_language("en"), bootstyle="link").pack(side="left")

    def _retranslate_ui(self) -> None:
        """Aktualisiert alle sichtbaren Beschriftungen nach Sprachwechsel."""
        self.title(self._i18n._("APC Mini Controller"))
        self._lbl_model.configure(text=self._i18n._("Modell:"))
        self._btn_connect.configure(text=self._i18n._("Verbinden"))
        self._btn_set_color.configure(text=self._i18n._("Farbe setzen"))
        self._btn_off.configure(text=self._i18n._("Aus"))
        self._btn_register.configure(text=self._i18n._("Zuordnen"))
        # Treeview-Header
        self._tree.heading("note", text=self._i18n._("Note"))
        self._tree.heading("command", text=self._i18n._("Befehl"))

    # ---- Event-Handler ----

    def _on_connect(self) -> None:
        model_str = self._model_var.get()
        model = next(m for m in DeviceModel if m.value == model_str)
        try:
            self._midi.connect()
            self._led_service = LedService(self._midi, model)
            self._lbl_status.configure(text=self._i18n._("Verbunden"), bootstyle="success")
            self._btn_connect.configure(state="disabled")
            self._start_polling()
        except MidiConnectionError as exc:
            messagebox.showerror(self._i18n._("MIDI-Fehler"), str(exc))

    def _on_set_color(self) -> None:
        if self._led_service is None:
            messagebox.showwarning(self._i18n._("Nicht verbunden"), self._i18n._("Bitte zuerst verbinden."))
            return
        try:
            color = LedColor(self._r_var.get(), self._g_var.get(), self._b_var.get())
            self._led_service.set_color(self._note_var.get(), color)
        except (ApcError, ValueError) as exc:
            messagebox.showerror(self._i18n._("Fehler"), str(exc))

    def _on_led_off(self) -> None:
        if self._led_service is None:
            messagebox.showwarning(self._i18n._("Nicht verbunden"), self._i18n._("Bitte zuerst verbinden."))
            return
        try:
            self._led_service.turn_off(self._note_var.get())
        except (ApcError, ValueError) as exc:
            messagebox.showerror(self._i18n._("Fehler"), str(exc))

    def _on_register(self) -> None:
        note = self._map_note_var.get()
        cmd = self._cmd_var.get().strip()
        if not cmd:
            messagebox.showwarning(self._i18n._("Eingabe fehlt"), self._i18n._("Bitte einen Befehl eingeben."))
            return
        mapping = ButtonMapping(note=note, command=cmd)
        self._commands.register(mapping)
        # Tree aktualisieren
        for item in self._tree.get_children():
            if self._tree.item(item, "values")[0] == str(note):
                self._tree.delete(item)
        self._tree.insert("", "end", values=(note, cmd))
        self._cmd_var.set("")

    def _start_polling(self) -> None:
        """Pollt MIDI-Input alle 50 ms (Tkinter-freundlich, kein Thread)."""
        if self._midi is None:
            return
        note = self._midi.poll_input()
        if note is not None:
            try:
                self._commands.execute(note)
            except ApcError as exc:
                logger.error("Befehlsfehler: %s", exc)
        self._poll_job = self.after(50, self._start_polling)

    def destroy(self) -> None:
        if self._poll_job:
            self.after_cancel(self._poll_job)
        self._midi.close()
        super().destroy()
```

### 3.9 `main.py`

```python
"""Composition Root – startet die Anwendung."""
import logging
import sys

from application.command_service import CommandService
from infrastructure.midi_adapter import MidiAdapter
from presentation.i18n import I18nManager
from presentation.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    i18n = I18nManager(domain="apc_controller", localedir="locale")
    i18n.set_language("de")
    midi = MidiAdapter()
    commands = CommandService()
    app = MainWindow(i18n, midi, commands)
    app.mainloop()


if __name__ == "__main__":
    main()
```

---

## 4. Abhängigkeiten & Installation

```bash
pip install mido python-rtmidi ttkbootstrap
```

**Windows-Besonderheit:** `python-rtmidi` benötigt unter Umständen die Microsoft C++ Build Tools. Falls die Installation fehlschlägt, installieren Sie diese über den Visual Studio Installer („Desktop development with C++") .

---

## 5. Übersetzungsdateien (i18n)

Erstellen Sie die Ordnerstruktur:
```
locale/
├── de/LC_MESSAGES/apc_controller.mo
└── en/LC_MESSAGES/apc_controller.mo
```

**`locale/de/LC_MESSAGES/apc_controller.po`** (Beispiel):
```po
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Language: de\n"

msgid "APC Mini Controller"
msgstr "APC Mini Controller"

msgid "Modell:"
msgstr "Modell:"

msgid "Verbinden"
msgstr "Verbinden"

msgid "Farbe setzen"
msgstr "Farbe setzen"

msgid "Aus"
msgstr "Aus"

msgid "Windows-Befehlszuordnung"
msgstr "Windows-Befehlszuordnung"

msgid "Zuordnen"
msgstr "Zuordnen"
```

**`locale/en/LC_MESSAGES/apc_controller.po`**:
```po
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Language: en\n"

msgid "APC Mini Controller"
msgstr "APC Mini Controller"

msgid "Modell:"
msgstr "Model:"

msgid "Verbinden"
msgstr "Connect"

msgid "Farbe setzen"
msgstr "Set Color"

msgid "Aus"
msgstr "Off"

msgid "Windows-Befehlszuordnung"
msgstr "Windows Command Mapping"

msgid "Zuordnen"
msgstr "Assign"
```

Kompilieren:
```bash
msgfmt locale/de/LC_MESSAGES/apc_controller.po -o locale/de/LC_MESSAGES/apc_controller.mo
msgfmt locale/en/LC_MESSAGES/apc_controller.po -o locale/en/LC_MESSAGES/apc_controller.mo
```

---

## 6. Teststrategie (Unit + Integration + E2E)

### Unit-Tests (Protokoll & Service)

```python
# tests/test_protocol.py
import pytest
from domain.models import LedColor, DeviceModel
from domain.exceptions import InvalidLedCommandError
from infrastructure.apc_protocol import ApcMiniMk2Protocol


class TestMk2Protocol:
    def test_turn_off_pad_returns_sysex(self):
        proto = ApcMiniMk2Protocol()
        msgs = proto.turn_off(0)
        assert len(msgs) == 1
        assert msgs[0][0] == 0xF0  # SysEx Start
        assert msgs[0][-1] == 0xF7  # SysEx Ende

    def test_set_color_out_of_range_raises(self):
        proto = ApcMiniMk2Protocol()
        with pytest.raises(InvalidLedCommandError):
            proto.set_color(200, LedColor(0, 0, 0))

    def test_peripheral_uses_note_on(self):
        proto = ApcMiniMk2Protocol()
        msgs = proto.turn_off(100)  # Peripherie-Button
        assert msgs[0][0] == 0x90
```

### Integration-Test (MIDI-Adapter mit Mock)

```python
# tests/test_midi_adapter.py
from unittest.mock import MagicMock, patch
from infrastructure.midi_adapter import MidiAdapter
from domain.exceptions import MidiConnectionError
import pytest


def test_connect_without_device_raises():
    adapter = MidiAdapter()
    with patch("mido.get_output_names", return_value=[]):
        with pytest.raises(MidiConnectionError):
            adapter.connect()
```

### E2E-Test (GUI mit pytest + tkinter)

```python
# tests/test_e2e_gui.py
import pytest
import tkinter as tk
from presentation.i18n import I18nManager
from application.command_service import CommandService
from infrastructure.midi_adapter import MidiAdapter
from presentation.main_window import MainWindow


@pytest.fixture
def app():
    i18n = I18nManager(localedir="locale")
    i18n.set_language("de")
    midi = MidiAdapter()
    commands = CommandService()
    root = MainWindow(i18n, midi, commands)
    root.withdraw()  # Kein sichtbares Fenster im Test
    yield root
    root.update_idletasks()
    root.destroy()


def test_window_title(app):
    assert "APC Mini Controller" in app.title()


def test_register_command_updates_tree(app):
    app._map_note_var.set(10)
    app._cmd_var.set("notepad.exe")
    app._on_register()
    app.update_idletasks()
    items = app._tree.get_children()
    assert len(items) == 1
    assert app._tree.item(items[0], "values")[0] == "10"
```

**Hinweis zu Tkinter-Tests:** `root.withdraw()` verhindert sichtbare Fenster; `update_idletasks()` vor Assertions ist erforderlich, damit Geometrie und Widget-State verarbeitet werden . Für CI-Umgebungen empfiehlt sich ein Xvfb (Linux) bzw. ein virtueller Display.

---

## 7. README (Auszug)

```markdown
# APC Mini LED Controller

Steuert LEDs des Akai APC Mini MK1/MK2 über MIDI und ordnet Tasten Windows-Befehlen zu.

## Installation
1. Python 3.10+ installieren
2. `pip install mido python-rtmidi ttkbootstrap`
3. APC Mini per USB anschließen

## Start
`python main.py`

## Funktionen
- LED ein/aus und RGB-Farbe (MK2) bzw. feste Farben (MK1)
- Pad-Note → Windows-Befehl (z. B. `notepad.exe`)
- Laufzeit-Sprachwechsel DE/EN

## Bekannte Einschränkungen
- MK1-Farben sind vereinfacht (nur Grün/Rot/Gelb)
- SysEx für MK2 RGB-Pads erfordert Firmware ≥ 1.0
```

---

## 8. Wichtige Hinweise zur Machbarkeit

1. **MK1 vs. MK2:** Der obige Code implementiert **beide Protokolle**, aber die MK1-Farbunterstützung ist auf die drei dokumentierten Velocity-Farben beschränkt. Für volle RGB-Unterstützung auf MK1 müsste das Gerät tatsächlich vorliegen und getestet werden.

2. **Laufzeit-Sprachwechsel:** `gettext` allein aktualisiert keine bereits erstellten Tkinter-Widgets. Die `I18nManager`-Klasse implementiert ein Listener-Pattern, bei dem jedes Widget seine Texte neu setzt. Dies ist der sauberste Weg ohne kompletten GUI-Neuaufbau .

3. **MIDI-Polling:** Das Polling alle 50 ms im Tkinter-Hauptthread ist für einzelne Tastendrücke ausreichend. Bei hoher Last (z. B. Fader-Bewegungen) sollte auf einen separaten Thread mit `queue.Queue` umgestellt werden.

4. **Sicherheit (OWASP):** `subprocess.Popen(shell=True)` ist bewusst gewählt, um Windows-Befehle wie `start chrome` zu ermöglichen. Die Befehle stammen ausschließlich aus lokaler GUI-Eingabe – es gibt keine externe Angriffsfläche. Für maximale Härtung kann auf `shlex.split(cmd)` + `shell=False` umgestellt werden, was jedoch die Befehlssyntax einschränkt.
