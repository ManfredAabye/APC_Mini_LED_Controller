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