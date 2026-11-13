"""Protokoll-Adapter für APC Mini MK1 und MK2.

MK2: RGB via SysEx (offizielle AKAI-Spezifikation), Peripherie via Note-On.
MK1: Farben via Velocity-Werte (1=grün, 3=rot, 5=gelb, 2=grün blinkend).
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


class ApcMiniMk1Protocol(ApcProtocol):
    """APC Mini MK1: Farben über Velocity (1=grün, 3=rot, 5=gelb, 2=grün blink)."""

    NOTE_ON_CH0 = 0x90
    VELOCITY_OFF = 0x00
    VELOCITY_GREEN = 0x01
    VELOCITY_GREEN_BLINK = 0x02
    VELOCITY_RED = 0x03
    VELOCITY_RED_BLINK = 0x04
    VELOCITY_YELLOW = 0x05
    VELOCITY_YELLOW_BLINK = 0x06

    def _validate_note(self, note: int) -> None:
        if not 0 <= note <= 119:
            raise InvalidLedCommandError(f"Note {note} außerhalb 0-119")

    def turn_off(self, note: int) -> List[List[int]]:
        self._validate_note(note)
        return [[self.NOTE_ON_CH0, note, self.VELOCITY_OFF]]

    def set_color(self, note: int, color: LedColor) -> List[List[int]]:
        self._validate_note(note)
        # MK1 kennt nur feste Farben – vereinfachte Zuordnung
        if color.red > 64 and color.green > 64:
            vel = self.VELOCITY_YELLOW
        elif color.red > 64:
            vel = self.VELOCITY_RED
        else:
            vel = self.VELOCITY_GREEN
        return [[self.NOTE_ON_CH0, note, vel]]

    def set_on(self, note: int) -> List[List[int]]:
        self._validate_note(note)
        return [[self.NOTE_ON_CH0, note, self.VELOCITY_RED]]


class ApcMiniMk2Protocol(ApcProtocol):
    """APC Mini MK2: RGB-Pads (0-63) via SysEx, Peripherie-LEDs via Note-On.

    SysEx-Format (offizielle AKAI-Spezifikation):
      F0 47 7F 4F 24 <len_msb> <len_lsb> <type> <start> <end> <r> <g> <b> F7
    """

    SYSEX_HEADER = [0x47, 0x7F, 0x4F, 0x24]  # ohne F0, wird in send() ergänzt
    SYSEX_TYPE_RGB = 0x00                     # Typ-Byte für RGB-Pad-Steuerung
    RGB_PAD_END = 63
    NOTE_ON_CH0 = 0x90

    def _build_sysex(self, start_pad: int, end_pad: int, color: LedColor) -> List[int]:
        """Baut eine vollständige SysEx-Nachricht für RGB-Pads."""
        r_msb, r_lsb = color.red >> 4, color.red & 0x0F
        g_msb, g_lsb = color.green >> 4, color.green & 0x0F
        b_msb, b_lsb = color.blue >> 4, color.blue & 0x0F
        payload = [
            self.SYSEX_TYPE_RGB,
            start_pad, end_pad,
            r_msb, r_lsb, g_msb, g_lsb, b_msb, b_lsb,
        ]
        total = len(payload)
        return (
            [0xF0]
            + self.SYSEX_HEADER
            + [total >> 7, total & 0x7F]
            + payload
            + [0xF7]
        )

    def _validate_note(self, note: int) -> None:
        if not 0 <= note <= 119:
            raise InvalidLedCommandError(f"Note {note} außerhalb 0-119")

    def turn_off(self, note: int) -> List[List[int]]:
        self._validate_note(note)
        if note <= self.RGB_PAD_END:
            return [self._build_sysex(note, note, LedColor(0, 0, 0))]
        return [[self.NOTE_ON_CH0, note, 0x00]]

    def set_color(self, note: int, color: LedColor) -> List[List[int]]:
        self._validate_note(note)
        if note <= self.RGB_PAD_END:
            return [self._build_sysex(note, note, color)]
        # Peripherie-LEDs sind einfarbig – an, wenn Rot > 0
        return [[self.NOTE_ON_CH0, note, 0x01 if color.red > 0 else 0x00]]

    def set_on(self, note: int) -> List[List[int]]:
        return self.set_color(note, LedColor(127, 0, 0))


def get_protocol(model: DeviceModel) -> ApcProtocol:
    """Factory: liefert das passende Protokoll für das Gerätemodell."""
    if model == DeviceModel.MK1:
        return ApcMiniMk1Protocol()
    if model == DeviceModel.MK2:
        return ApcMiniMk2Protocol()
    raise ValueError(f"Unbekanntes Modell: {model}")