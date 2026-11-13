"""MIDI-I/O-Adapter mit mido/python-rtmidi und Fehlerbehandlung.

Wichtig: Input und Output werden getrennt gesucht, weil der APC Mini unter
Windows als zwei separate Ports erscheint (z. B. 'APC MINI 0' = Output,
'APC MINI 1' = Input – oder umgekehrt, je nach System).
"""
import logging
from typing import Optional

import mido

from domain.exceptions import MidiConnectionError

logger = logging.getLogger(__name__)


def _suffix_num(name: str) -> int:
    """Extrahiert die abschließende Port-Nummer ('APC MINI 1' -> 1)."""
    try:
        return int(name.rsplit(" ", 1)[-1])
    except ValueError:
        return -1


class MidiAdapter:
    """Kapselt MIDI-Port-Handling und Nachrichtenversand."""

    def __init__(self):
        self._output: Optional[mido.ports.BaseOutput] = None
        self._input: Optional[mido.ports.BaseInput] = None

    def list_ports(self) -> list[str]:
        return mido.get_output_names()

    def connect(self, port_name: Optional[str] = None) -> None:
        """Verbindet Output und – falls verfügbar – Input zum APC Mini."""
        try:
            out_names = mido.get_output_names()
            in_names = mido.get_input_names()

            # Output-Port bestimmen
            if port_name is None:
                apc_outs = [n for n in out_names if "apc" in n.lower()]
                if not apc_outs:
                    raise MidiConnectionError(
                        f"Kein APC Mini unter Outputs gefunden. Verfügbar: {out_names}"
                    )
                apc_outs.sort(key=_suffix_num)
                port_name = apc_outs[-1]

            self._output = mido.open_output(port_name)
            logger.info("MIDI-Output geöffnet: %s", port_name)

            # Input-Port separat suchen
            apc_ins = [n for n in in_names if "apc" in n.lower()]
            if apc_ins:
                apc_ins.sort(key=_suffix_num)
                input_name = apc_ins[0]
                self._input = mido.open_input(input_name)
                logger.info("MIDI-Input geöffnet: %s", input_name)
            else:
                logger.warning("Kein APC-Input gefunden – Tasten werden nicht ausgewertet.")

        except (IOError, OSError) as exc:
            raise MidiConnectionError(f"MIDI-Verbindung fehlgeschlagen: {exc}") from exc

    def send(self, messages: list[list[int]]) -> None:
        """Sendet eine Liste von MIDI-Nachrichten (als Byte-Listen)."""
        if self._output is None:
            raise MidiConnectionError("Nicht verbunden. Zuerst connect() aufrufen.")
        for msg_bytes in messages:
            try:
                if msg_bytes[0] == 0xF0:
                    # SysEx: F0 und F7 entfernen, data erwartet Nutzlast
                    msg = mido.Message("sysex", data=msg_bytes[1:-1])
                else:
                    # mido.Message.from_bytes erwartet bytes, nicht List[int]
                    msg = mido.Message.from_bytes(bytes(msg_bytes))
                self._output.send(msg)
            except (ValueError, OSError) as exc:
                logger.error("MIDI-Nachricht fehlgeschlagen (%s): %s", msg_bytes, exc)
                raise

    def poll_input(self) -> Optional[int]:
        """Liest eine anstehende Note-On-Note (nicht-blockierend)."""
        if self._input is None:
            return None
        try:
            msg = self._input.poll()
        except (IOError, OSError) as exc:
            logger.error("MIDI-Input-Fehler: %s", exc)
            return None
        if msg is not None and msg.type == "note_on" and msg.velocity > 0:
            return msg.note
        return None

    def close(self) -> None:
        if self._output:
            try:
                self._output.close()
            except Exception:
                pass
        if self._input:
            try:
                self._input.close()
            except Exception:
                pass
        self._output = None
        self._input = None