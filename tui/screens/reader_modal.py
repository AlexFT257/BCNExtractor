"""
tui/screens/reader_modal.py

Modal que muestra el contenido Markdown de una norma usando su md_path de la DB.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown


class ReaderModal(ModalScreen):
    """Muestra el Markdown de una norma usando su md_path de la DB."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cerrar"),
        Binding("q", "dismiss", "Cerrar"),
    ]

    def __init__(self, norm_id: int, titulo: str, md_path: Optional[str]) -> None:
        super().__init__()
        self.norm_id = norm_id
        self.titulo = titulo
        self.md_path = md_path

    def compose(self) -> ComposeResult:
        with Vertical(id="reader-dialog"):
            yield Label(f"#{self.norm_id}  {self.titulo[:72]}", id="reader-title")
            with ScrollableContainer(id="reader-scroll"):
                yield Markdown(self._load_content())
            with Horizontal(id="reader-btns"):
                yield Button("Cerrar  [Esc]", id="reader-close", classes="ghost")

    def _load_content(self) -> str:
        if self.md_path and Path(self.md_path).exists():
            return Path(self.md_path).read_text(encoding="utf-8")
        return (
            f"# #{self.norm_id}\n\n"
            "*El archivo Markdown no esta disponible.*\n\n"
            "Ejecuta `sync` con la institucion correspondiente para descargarlo."
        )

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.dismiss()