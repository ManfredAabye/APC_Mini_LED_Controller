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