"""
tui/screens/sync_modal.py

Modal de sincronización. Delega toda la lógica a services.sync.sync_institucion
y solo se ocupa de actualizar la UI desde el thread de trabajo.
"""

from __future__ import annotations

from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ProgressBar, RichLog

from tui.state import build_sync_managers


class SyncModal(ModalScreen):
    """
    Sincroniza normas de una institución en un thread separado.
    Al terminar habilita el botón Cerrar y notifica a la app
    para que refresque la tabla de normas.
    """

    BINDINGS = [Binding("escape", "cancel_sync", "Cancelar")]

    def __init__(
        self,
        inst_id: int,
        inst_nombre: str,
        limit: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.inst_id = inst_id
        self.inst_nombre = inst_nombre
        self.limit = limit
        self._cancelled = False

    def compose(self) -> ComposeResult:
        with Vertical(id="sync-dialog"):
            yield Label(f"Sincronizando: {self.inst_nombre}", id="sync-title")
            yield Label("Consultando BCN...", id="sync-sub")
            yield ProgressBar(total=100, id="sync-progress", show_eta=True)
            yield RichLog(id="sync-log", auto_scroll=True, markup=True)
            with Horizontal():
                yield Button("Cancelar  [Esc]", id="sync-cancel", classes="ghost")

    def on_mount(self) -> None:
        self._run_sync()

    @work(exclusive=True, thread=True)
    def _run_sync(self) -> None:
        from services.sync import sync_institucion

        log_widget = self.query_one(RichLog)
        prog = self.query_one(ProgressBar)

        def on_log(msg: str) -> None:
            self.app.call_from_thread(log_widget.write, msg)
            self.app._logs_tab.write(msg)

        def on_progress(
            procesadas: int, total: int, id_norma: int, resultado: str
        ) -> None:
            if procesadas == 1:
                self.app.call_from_thread(prog.__setattr__, "total", total)
            self.app.call_from_thread(prog.advance, 1)
            self.app.call_from_thread(
                self.query_one("#sync-sub", Label).update,
                f"{procesadas}/{total} normas procesadas",
            )

        try:
            mgrs = build_sync_managers()

            stats = sync_institucion(
                inst_id=self.inst_id,
                managers=mgrs,
                limit=self.limit,
                on_progress=on_progress,
                on_log=on_log,
                cancelado=lambda: self._cancelled,
            )

            severity = "information" if stats.errores == 0 else "warning"
            self.app.call_from_thread(
                self.app.notify, stats.resumen(), severity=severity
            )
            self.app.call_from_thread(self.app.refresh_norms_table)
            self.app.call_from_thread(self._set_sync_done)

            mgrs["conn"].close()

        except Exception as e:
            on_log(f"[red]Error fatal: {e}[/red]")
            self.app.call_from_thread(self.app.notify, f"Error: {e}", severity="error")
            self.app.call_from_thread(self._set_sync_done)

    def _set_sync_done(self) -> None:
        """Cambia el botón Cancelar por Cerrar al terminar el sync."""
        self._cancelled = True
        btn = self.query_one("#sync-cancel", Button)
        btn.label = "Cerrar  [Esc]"
        btn.add_class("primary")
        btn.remove_class("ghost")

    def action_cancel_sync(self) -> None:
        self._cancelled = True
        self.app.refresh_norms_table()
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sync-cancel":
            event.stop()
            self.action_cancel_sync()