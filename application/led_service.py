"""Use Case: LED-Steuerung unabhängig vom Protokoll."""
from domain.models import DeviceModel, LedColor
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