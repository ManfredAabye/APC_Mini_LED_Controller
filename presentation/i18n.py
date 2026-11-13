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