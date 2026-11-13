"""Domain-spezifische Exceptions."""


class ApcError(Exception):
    """Basis-Exception für APC-bezogene Fehler."""


class MidiConnectionError(ApcError):
    """MIDI-Gerät konnte nicht geöffnet werden."""


class UnsupportedDeviceError(ApcError):
    """Gerät wird nicht unterstützt (weder MK1 noch MK2)."""


class InvalidLedCommandError(ApcError):
    """Ungültiger LED-Befehl (z. B. Pad außerhalb des Bereichs)."""