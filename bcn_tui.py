"""
tui/app.py

BCNApp — clase principal de la TUI.
Responsabilidades: compose, bindings, on_mount y enrutar acciones globales.
Toda la lógica de negocio vive en los tabs y screens.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabPane, TabbedContent

from tui.screens.reader_modal import ReaderModal
from tui.screens.sync_modal import SyncModal
from tui.state import AppState
from tui.tabs.dashboard import DashboardTab
from tui.tabs.logs import LogsTab
from tui.tabs.metadata import MetadataTab
from tui.tabs.nlp import NLPTab
from tui.tabs.normas import NormasTab
from tui.tabs.schedules import SchedulesTab


class BCNApp(App):
    """BCN Extractor TUI."""

    TITLE = "BCN Extractor"
    CSS_PATH = "tui/tui.css"
    DARK = True

    BINDINGS = [
        Binding("1", "show_tab('normas')", "Normas", show=True),
        Binding("2", "show_tab('metadata')", "Metadata", show=True),
        Binding("3", "show_tab('nlp')", "NLP", show=True),
        Binding("4", "show_tab('schedules')", "Schedules", show=True),
        Binding("5", "show_tab('dashboard')", "Dashboard", show=True),
        Binding("6", "show_tab('logs')", "Logs", show=True),
        Binding("s", "sync", "Sync", show=True),
        Binding("slash", "focus_search", "Buscar", show=True),
        Binding("r", "read_norm", "Leer", show=True),
        Binding("q", "quit", "Salir", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._state = AppState()

    # ── COMPOSE ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent(id="tabs"):
            with TabPane("1 Normas", id="tab-normas"):
                yield NormasTab(self._state)
            with TabPane("2 Metadata", id="tab-metadata"):
                yield MetadataTab(self._state)
            with TabPane("3 NLP", id="tab-nlp"):
                yield NLPTab(self._state)
            with TabPane("4 Schedules", id="tab-schedules"):
                yield SchedulesTab(self._state)
            with TabPane("5 Dashboard", id="tab-dashboard"):
                yield DashboardTab(self._state)
            with TabPane("6 Logs", id="tab-logs"):
                yield LogsTab()

        yield Footer()

    # ── MOUNT ─────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._dashboard_tab.load()

    # ── PROPIEDADES INTERNAS ──────────────────────────────────────────────────

    @property
    def _normas_tab(self) -> NormasTab:
        return self.query_one(NormasTab)

    @property
    def _dashboard_tab(self) -> DashboardTab:
        return self.query_one(DashboardTab)

    @property
    def _logs_tab(self) -> LogsTab:
        return self.query_one(LogsTab)

    # ── ACCIONES ──────────────────────────────────────────────────────────────

    def action_sync(self) -> None:
        selected = self._normas_tab.selected_inst
        if not selected:
            self.notify("Selecciona una institución primero", severity="warning")
            return
        inst_id, inst_nombre, _ = selected
        self.push_screen(SyncModal(inst_id, inst_nombre))

    def action_read_norm(self) -> None:
        norm = self._normas_tab.selected_norm
        if not norm:
            self.notify("Selecciona una norma primero", severity="warning")
            return
        self.push_screen(
            ReaderModal(norm["id"], norm["titulo"], norm.get("md_path"))
        )

    def action_focus_search(self) -> None:
        self.query_one("#inst-search").focus()

    def action_show_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = f"tab-{tab}"

    # ── EVENTOS DE TAB ────────────────────────────────────────────────────────

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if not event.pane:
            return
        if event.pane.id == "tab-dashboard":
            self._dashboard_tab.load()
        elif event.pane.id == "tab-schedules":
            self.query_one(SchedulesTab).load()

    # ── API PÚBLICA PARA SCREENS ──────────────────────────────────────────────

    def refresh_norms_table(self) -> None:
        """Recarga la tabla de normas. Llamado desde SyncModal via call_from_thread."""
        self._normas_tab.refresh_norms_table()

    def tui_log(self, msg: str) -> None:
        """Escribe en el log interno. Disponible para cualquier screen."""
        self._logs_tab.write(msg)

    # ── CICLO DE VIDA ─────────────────────────────────────────────────────────

    def on_unmount(self) -> None:
        self._state.close()

def main() -> None:
    app = BCNApp()
    app.run()


if __name__ == "__main__":
    main()
