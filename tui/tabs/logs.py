"""
tui/tabs/logs.py

Tab de logs internos de la sesión TUI.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog


class LogsTab(Vertical):
    """Tab que muestra el log interno de la sesión."""

    def __init__(self) -> None:
        super().__init__(id="logs-content")

    def compose(self) -> ComposeResult:
        yield RichLog(id="log-widget", auto_scroll=True, markup=True)

    def write(self, msg: str) -> None:
        """Escribe un mensaje en el log. Seguro llamarlo desde el app."""
        try:
            self.query_one("#log-widget", RichLog).write(msg)
        except Exception:
            pass