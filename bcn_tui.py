"""
BCN Extractor TUI — Interfaz de terminal con Textual
Requiere: pip install textual rich

Estructura: app.py (o reemplaza tu bcn_cli.py)
"""

import asyncio

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Log,
    Markdown,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
)

from managers.institutions import InstitutionManager
from managers.norms import NormsManager
from managers.norms_types import TiposNormasManager

# ── CSS DE LA APP ─────────────────────────────────────────────────────────────

CSS = """
/* === PALETA === */
$bg:        #0d0f14;
$bg2:       #141720;
$bg3:       #1a1e2e;
$border:    #2a3050;
$accent:    #4f7cff;
$accent2:   #00d4aa;
$accent3:   #f0a500;
$red:       #ff4f6a;
$text:      #c8d0e8;
$text-dim:  #5a6380;

Screen {
    background: $bg;
    color: $text;
}

Header {
    background: $bg2;
    color: $accent;
    border-bottom: tall $border;
}

Footer {
    background: $accent;
    color: white;
}

/* === LAYOUT PRINCIPAL === */
#main-layout {
    layout: horizontal;
    height: 1fr;
}

/* === SIDEBAR === */
#sidebar {
    width: 28;
    background: $bg2;
    border-right: tall $border;
    padding: 0;
}

#sidebar-title {
    background: $bg3;
    color: $text-dim;
    text-style: bold;
    padding: 0 1;
    border-bottom: tall $border;
}

#inst-search {
    border: tall $border;
    background: $bg3;
    color: $text;
    margin: 1 1 0 1;
}

#inst-search:focus {
    border: tall $accent;
}

#inst-list {
    height: 1fr;
    background: $bg2;
}

/* === CONTENT === */
#content-area {
    width: 1fr;
    background: $bg;
}

#content-header {
    background: $bg2;
    border-bottom: tall $border;
    padding: 0 2;
    height: 4;
    layout: horizontal;
}

#inst-label {
    color: white;
    text-style: bold;
    width: 1fr;
    padding-top: 1;
}

#header-buttons {
    layout: horizontal;
    align: right middle;
    width: auto;
    padding-top: 1;
}

Button {
    margin-left: 1;
    min-width: 14;
}

Button.primary {
    background: $accent;
    color: white;
    border: none;
}

Button.ghost {
    background: $bg3;
    color: $text-dim;
    border: tall $border;
}

Button:hover {
    background: $accent;
    color: white;
}

/* === TABLA DE NORMAS === */
DataTable {
    height: 1fr;
    background: $bg;
    color: $text;
    border: none;
}

DataTable > .datatable--header {
    background: $bg3;
    color: $text-dim;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1e2a4a;
    color: white;
}

DataTable > .datatable--hover {
    background: $bg3;
}

/* === PANEL DETALLE === */
#detail-panel {
    width: 38;
    background: $bg2;
    border-left: tall $border;
    padding: 1 2;
}

#detail-title {
    color: white;
    text-style: bold;
    margin-bottom: 1;
}

#detail-content {
    height: 1fr;
    color: $text;
}

#detail-actions {
    height: auto;
    border-top: tall $border;
    padding-top: 1;
    layout: vertical;
}

#detail-actions Button {
    margin: 0 0 1 0;
    width: 100%;
}

/* === DASHBOARD === */
#dashboard {
    layout: vertical;
    padding: 1 2;
    background: $bg;
}

#stats-row {
    layout: horizontal;
    height: 7;
    margin-bottom: 1;
}

.stat-card {
    width: 1fr;
    background: $bg2;
    border: tall $border;
    padding: 1;
    margin-right: 1;
    text-align: center;
}

.stat-card .stat-num {
    color: $accent;
    text-style: bold;
}

#charts-row {
    layout: horizontal;
    height: 1fr;
}

.chart-panel {
    width: 1fr;
    background: $bg2;
    border: tall $border;
    padding: 1;
    margin-right: 1;
}

/* === MODAL SYNC === */
SyncModal {
    align: center middle;
}

#sync-dialog {
    background: $bg2;
    border: thick $accent;
    padding: 2 4;
    width: 60;
    height: 22;
}

#sync-log {
    height: 8;
    background: $bg3;
    border: tall $border;
    margin: 1 0;
}

/* === MODAL LECTOR === */
ReaderModal {
    align: center middle;
}

#reader-dialog {
    background: $bg2;
    border: thick $accent2;
    padding: 1 2;
    width: 90;
    height: 40;
}

#reader-content {
    height: 1fr;
    background: $bg;
    border: tall $border;
    padding: 1;
}
"""


# ── DATOS MOCK (reemplazar con queries reales a tu DB) ──────────────────────

INSTITUCIONES = []

NORMAS = []

TEXTO_MOCK = """# DS 42/2024 — Reglamento Residuos Sólidos

**Publicado:** 15/11/2024 · **Estado:** Vigente · **Organismo:** Min. Medio Ambiente

---

## Artículo 1° — Ámbito de aplicación

Las disposiciones del presente reglamento serán aplicables a todas las
actividades de generación, almacenamiento, recolección, transporte, tratamiento
y disposición final de residuos sólidos domiciliarios y asimilables, conforme
a lo establecido en la Ley N° 19.300.

## Artículo 2° — Definiciones

Para los efectos de este reglamento, se entenderá por:

**a) Residuos sólidos domiciliarios:** aquellos generados en las viviendas
como consecuencia de la actividad doméstica.

**b) Gestor autorizado:** toda persona natural o jurídica que cuente con
autorización sanitaria y ambiental para realizar actividades de gestión
de residuos.

## Artículo 3° — Obligaciones del generador

Todo generador de residuos sólidos deberá:

1. Almacenar los residuos en recipientes herméticos
2. Separar los residuos en las fracciones establecidas
3. Entregar los residuos al gestor autorizado en los horarios fijados

---

*Continúa en 42 artículos más...*
"""


# ── MODAL: SINCRONIZACIÓN ────────────────────────────────────────────────────


class SyncModal(ModalScreen):
    """Modal de sincronización con progress bar y log en tiempo real."""

    BINDINGS = [Binding("escape", "dismiss", "Cancelar")]

    def __init__(self, inst_name: str, inst_id: int, total: int):
        super().__init__()
        self.inst_name = inst_name
        self.inst_id = inst_id
        self.total = total

    def compose(self) -> ComposeResult:
        with Vertical(id="sync-dialog"):
            yield Label(f"⟳  Sincronizando: {self.inst_name}", id="sync-title")
            yield Label(
                f"{self.total} normas en cola · ID {self.inst_id}", id="sync-sub"
            )
            yield ProgressBar(total=self.total, id="sync-progress", show_eta=True)
            yield Log(id="sync-log", auto_scroll=True)
            with Horizontal():
                yield Button("✕  Cancelar", id="sync-cancel", classes="ghost")

    def on_mount(self) -> None:
        self.run_sync()

    @work(exclusive=True, thread=True)
    def run_sync(self) -> None:
        """Simula la sincronización — reemplaza con tu lógica real."""
        import random
        import time

        progress = self.query_one(ProgressBar)
        log = self.query_one(Log)
        done = 0
        while done < self.total:
            step = random.randint(3, 15)
            done = min(done + step, self.total)
            progress.advance(step)

            # Simula log de normas descargadas
            norm_id = random.randint(1000000, 1099999)
            if random.random() < 0.05:
                log.write_line(f"[red]✗ #{norm_id} — parse error[/red]")
            else:
                log.write_line(f"[green]✓ #{norm_id} OK[/green]")

            time.sleep(0.08)

        log.write_line("[bold green]✓ Sincronización completada[/bold green]")
        self.app.call_from_thread(self._done)

    def _done(self):
        self.app.notify(f"✓ {self.inst_name} sincronizado", severity="information")
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sync-cancel":
            self.dismiss()


# ── MODAL: LECTOR DE NORMA ───────────────────────────────────────────────────


class ReaderModal(ModalScreen):
    """Lector de texto completo de una norma."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cerrar"),
        Binding("q", "dismiss", "Cerrar"),
    ]

    def __init__(self, norm_id: int, titulo: str, contenido: str):
        super().__init__()
        self.norm_id = norm_id
        self.titulo = titulo
        self.contenido = contenido

    def compose(self) -> ComposeResult:
        with Vertical(id="reader-dialog"):
            yield Label(f"📄  #{self.norm_id} — {self.titulo[:60]}…", id="reader-title")
            with ScrollableContainer(id="reader-content"):
                yield Markdown(self.contenido)
            with Horizontal():
                yield Button("✕  Cerrar  [Esc]", id="reader-close", classes="ghost")
                yield Button("↗  Abrir en BCN", id="reader-bcn", classes="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# ── PANTALLA PRINCIPAL ───────────────────────────────────────────────────────


class BCNApp(App):
    """BCN Extractor — TUI completa."""

    TITLE = "BCN Extractor"
    CSS = CSS
    DARK = True

    BINDINGS = [
        Binding("1", "show_tab('normas')", "Normas", show=True),
        Binding("2", "show_tab('dashboard')", "Dashboard", show=True),
        Binding("3", "show_tab('instituciones')", "Instituciones", show=True),
        Binding("s", "sync", "Sync", show=True),
        Binding("slash", "focus_search", "Buscar", show=True),
        Binding("q", "quit", "Salir", show=True),
        Binding("enter", "open_norm", "Abrir", show=False),
    ]

    selected_inst = reactive((10248, "Min. Medio Ambiente", 847))
    selected_norm = reactive(None)

    # ── COMPOSE ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        INSTITUCIONES = InstitutionManager().get_all()

        with TabbedContent(id="tabs"):
            # ── TAB 1: NORMAS ─────────────────────────────────────────────
            with TabPane("1  Normas", id="tab-normas"):
                with Horizontal(id="main-layout"):
                    # Sidebar instituciones

                    with Vertical(id="sidebar"):
                        yield Static("INSTITUCIONES", id="sidebar-title")
                        yield Input(placeholder="🔍 filtrar...", id="inst-search")
                        yield ListView(
                            *[
                                ListItem(
                                    Label(f"{n}  ({c})", id=f"inst-{i}"), id=f"li-{i}"
                                )
                                for i, n, c in INSTITUCIONES
                            ],
                            id="inst-list",
                        )

                    # Área central
                    with Vertical(id="content-area"):
                        with Horizontal(id="content-header"):
                            yield Label(
                                "Min. Medio Ambiente  ·  847 normas", id="inst-label"
                            )
                            with Horizontal(id="header-buttons"):
                                yield Button(
                                    "⟳ Sincronizar", id="btn-sync", classes="ghost"
                                )
                                yield Button(
                                    "↓ Exportar", id="btn-export", classes="primary"
                                )

                        yield DataTable(
                            id="norms-table", cursor_type="row", zebra_stripes=True
                        )

                    # Panel detalle
                    with Vertical(id="detail-panel"):
                        yield Label("DETALLE", id="detail-header")
                        yield Static("← Selecciona una norma", id="detail-title")
                        with ScrollableContainer(id="detail-content"):
                            yield Static("")
                        with Vertical(id="detail-actions"):
                            yield Button(
                                "📄 Leer texto completo",
                                id="btn-read",
                                classes="primary",
                            )
                            yield Button(
                                "🔗 Ver relaciones", id="btn-rels", classes="ghost"
                            )
                            yield Button(
                                "↗ Abrir en BCN", id="btn-bcn", classes="ghost"
                            )

            # ── TAB 2: DASHBOARD ──────────────────────────────────────────
            with TabPane("2  Dashboard", id="tab-dashboard"):
                with Vertical(id="dashboard"):
                    yield Static(self._render_dashboard())

            # ── TAB 3: INSTITUCIONES ──────────────────────────────────────
            with TabPane("3  Instituciones", id="tab-instituciones"):
                yield DataTable(id="inst-table", cursor_type="row", zebra_stripes=True)

        yield Footer()

    # ── ON MOUNT ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._load_norms_table()
        self._load_inst_table()

    def _load_norms_table(self) -> None:
        table = self.query_one("#norms-table", DataTable)
        table.add_columns("ID", "Tipo", "Nº", "Título", "Fecha", "Estado")
        for norm in NORMAS:
            nid, tipo, num, titulo, fecha, estado = norm
            estado_text = Text(estado, style="green" if estado == "vigente" else "red")
            table.add_row(
                Text(f"#{nid}", style="dim"),
                Text(tipo, style="cyan"),
                Text(num, style="dim"),
                Text(titulo[:55] + "…" if len(titulo) > 55 else titulo),
                Text(fecha, style="dim"),
                estado_text,
                key=str(nid),
            )

    def _load_inst_table(self) -> None:
        table = self.query_one("#inst-table", DataTable)
        table.add_columns("ID BCN", "Institución", "Normas", "Último Sync", "Estado")
        for i, (iid, name, count) in enumerate(INSTITUCIONES):
            table.add_row(
                Text(str(iid), style="dim"),
                name,
                Text(str(count), style="cyan"),
                Text("2024-11-15", style="dim"),
                Text("✓ sync", style="green"),
            )

    def _render_dashboard(self) -> str:
        """Retorna un panel Rich con estadísticas."""
        return (
            "\n"
            "  [bold cyan]ESTADÍSTICAS GENERALES[/bold cyan]\n\n"
            "  Total normas    [bold white]12,847[/bold white]   "
            "  Vigentes        [bold green]9,203[/bold green]   "
            "  Derogadas       [bold red]3,644[/bold red]   "
            "  Instituciones   [bold yellow]203[/bold yellow]\n\n"
            "  [dim]Normas por tipo:[/dim]\n"
            "  Decreto Supremo  ████████████████████  4,821\n"
            "  Ley              █████████████         3,204\n"
            "  Resolución       ██████████            2,347\n"
            "  DFL              █████                 1,204\n"
            "  Otros            ████                  1,271\n\n"
            "  [dim]Última sincronización:[/dim] hoy 09:41  ·  "
            "[dim]DB:[/dim] [green]●[/green] conectada  ·  "
            "[dim]Cache:[/dim] 2.3 GB\n"
        )

    # ── EVENTOS ──────────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "norms-table":
            self._show_norm_detail(event.row_key.value)

    def _show_norm_detail(self, norm_id_str: str) -> None:
        norm_id = int(norm_id_str.lstrip("#"))
        norm = next((n for n in NORMAS if n[0] == norm_id), None)
        if not norm:
            return
        nid, tipo, num, titulo, fecha, estado = norm
        self.selected_norm = norm

        self.query_one("#detail-title", Static).update(f"[bold]{tipo} {num}[/bold]")
        detail = self.query_one("#detail-content")
        detail.query_one(Static).update(
            f"[bold white]{titulo}[/bold white]\n\n"
            f"[dim]ID BCN:[/dim]  [cyan]#{nid}[/cyan]\n"
            f"[dim]Tipo:[/dim]    {tipo}\n"
            f"[dim]Número:[/dim]  {num}\n"
            f"[dim]Fecha:[/dim]   [yellow]{fecha}[/yellow]\n"
            f"[dim]Estado:[/dim]  {'[green]vigente[/green]' if estado == 'vigente' else '[red]derogada[/red]'}\n\n"
            f"[dim]Relaciones:[/dim]\n"
            f"  → Modifica [cyan]DS 148/2003[/cyan]\n"
            f"  → Complementa [cyan]Ley 19.300[/cyan]\n"
            f"  ← Citado por [green]3 normas[/green]\n"
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Selección de institución en sidebar."""
        idx = int(event.item.id.split("-")[1])
        inst = INSTITUCIONES[idx]
        self.selected_inst = inst
        self.query_one("#inst-label", Label).update(f"{inst[1]}  ·  {inst[2]} normas")
        self.notify(f"Cargando normas de {inst[1]}…", timeout=1.5)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-sync":
            self.action_sync()
        elif event.button.id == "btn-read":
            self.action_open_norm()
        elif event.button.id == "btn-export":
            self.notify("Exportando a CSV…", severity="information")

    # ── ACCIONES ─────────────────────────────────────────────────────────────

    def action_sync(self) -> None:
        i, n, c = self.selected_inst
        self.push_screen(SyncModal(n, i, c))

    def action_open_norm(self) -> None:
        if self.selected_norm is None:
            self.notify("Selecciona una norma primero", severity="warning")
            return
        nid, tipo, num, titulo, *_ = self.selected_norm
        self.push_screen(ReaderModal(nid, titulo, TEXTO_MOCK))

    def action_focus_search(self) -> None:
        self.query_one("#inst-search", Input).focus()

    def action_show_tab(self, tab: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = f"tab-{tab}"


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = BCNApp()
    app.run()
