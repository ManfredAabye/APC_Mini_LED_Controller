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