"""
BCN Extractor — TUI
Interfaz de terminal interactiva. Usa los managers del proyecto directamente.

Uso:
    python bcn_tui.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    ProgressBar,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

# ── HELPERS ──────────────────────────────────────────────────────────────────

def _init_managers(conn=None):
    """
    Devuelve un dict con todos los managers compartiendo una sola conexion.
    Si no se pasa conn, crea una nueva.
    """
    import psycopg2
    from dotenv import load_dotenv

    from managers.institutions import InstitutionManager
    from managers.norms import NormsManager
    from managers.norms_types import TiposNormasManager
    from managers.downloads import DownloadManager

    load_dotenv()

    if conn is None:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432),
            database=os.getenv("POSTGRES_DB", "bcn_normas"),
            user=os.getenv("POSTGRES_USER", "bcn_user"),
            password=os.getenv("POSTGRES_PASSWORD", "bcn_password"),
        )

    return {
        "conn": conn,
        "normas": NormsManager(db_connection=conn),
        "tipos": TiposNormasManager(db_connection=conn),
        "instituciones": InstitutionManager(db_connection=conn),
        "logger": DownloadManager(db_connection=conn),
    }


# ── MODAL: LECTOR ─────────────────────────────────────────────────────────────

class ReaderModal(ModalScreen):
    """Muestra el Markdown de una norma usando su md_path de la DB."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cerrar"),
        Binding("q", "dismiss", "Cerrar"),
    ]

    def __init__(self, norm_id: int, titulo: str, md_path: Optional[str]):
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


# ── MODAL: SINCRONIZACION ─────────────────────────────────────────────────────

class SyncModal(ModalScreen):
    """
    Sincroniza normas de una institucion en un thread separado.
    Usa BCNClient, BCNXMLParser, NormsManager, TiposNormasManager y DownloadManager
    exactamente igual que bcn_cli.py sync.
    """

    BINDINGS = [Binding("escape", "cancel_sync", "Cancelar")]

    def __init__(self, inst_id: int, inst_nombre: str, limit: Optional[int] = None):
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
        from bcn_client import BCNClient
        from utils.norm_parser import BCNXMLParser

        log = self.query_one(RichLog)
        prog = self.query_one(ProgressBar)

        def ui_log(msg: str):
            self.app.call_from_thread(log.write, msg)

        def ui_sub(msg: str):
            self.app.call_from_thread(self.query_one("#sync-sub", Label).update, msg)

        try:
            mgrs = _init_managers()
            client = BCNClient()
            parser = BCNXMLParser()

            ui_log("Consultando lista de normas en BCN...")
            normas = client.get_normas_por_institucion(self.inst_id)

            if not normas:
                ui_log("[red]Error: no se pudo obtener la lista de normas[/red]")
                return

            if self.limit:
                normas = normas[: self.limit]

            total = len(normas)
            ui_sub(f"{total} normas en cola")
            self.app.call_from_thread(prog.__setattr__, "total", total)

            # Registrar tipos en batch antes de procesar normas
            tipos = {
                n["id_tipo"]: {
                    "id": n["id_tipo"],
                    "nombre": n["tipo"],
                    "abreviatura": n["abreviatura"],
                }
                for n in normas
                if n.get("id_tipo") and n.get("tipo")
            }
            if tipos:
                mgrs["tipos"].add_batch(list(tipos.values()))

            stats = {"nuevas": 0, "actualizadas": 0, "sin_cambios": 0, "errores": 0}

            for norma_info in normas:
                if self._cancelled:
                    ui_log("[yellow]Cancelado por el usuario[/yellow]")
                    break

                nid = norma_info["id"]
                try:
                    xml = client.get_norma_completa(nid)
                    if not xml:
                        stats["errores"] += 1
                        mgrs["logger"].log(
                            nid, "error", "sincronizacion", "Sin respuesta XML"
                        )
                        ui_log(f"[red]x #{nid} sin respuesta[/red]")
                    else:
                        markdown, metadata = parser.parse_from_string(xml)
                        parsed = {
                            "numero": metadata.numero,
                            "titulo": metadata.titulo,
                            "estado": "derogada" if metadata.derogado else "vigente",
                            "fecha_publicacion": metadata.fecha_publicacion,
                            "fecha_promulgacion": metadata.fecha_promulgacion,
                            "organismo": metadata.organismos[0]
                            if metadata.organismos
                            else None,
                            "materias": metadata.materias,
                            "organismos": metadata.organismos,
                        }
                        result = mgrs["normas"].save(
                            id_norma=nid,
                            xml_content=xml,
                            parsed_data=parsed,
                            id_tipo=norma_info.get("id_tipo"),
                            id_institucion=self.inst_id,
                            markdown=markdown,
                        )
                        key = {
                            "nueva": "nuevas",
                            "actualizada": "actualizadas",
                            "sin_cambios": "sin_cambios",
                        }[result]
                        stats[key] += 1
                        mgrs["logger"].log(nid, "exitosa", "sincronizacion")

                        color = {
                            "nueva": "green",
                            "actualizada": "cyan",
                            "sin_cambios": "dim",
                        }.get(result, "white")
                        ui_log(f"[{color}]v #{nid} {result}[/{color}]")

                except Exception as e:
                    stats["errores"] += 1
                    mgrs["logger"].log(nid, "error", "sincronizacion", str(e))
                    ui_log(f"[red]x #{nid} {str(e)[:55]}[/red]")

                self.app.call_from_thread(prog.advance, 1)

            summary = (
                f"Completado: {stats['nuevas']} nuevas, "
                f"{stats['actualizadas']} actualizadas, "
                f"{stats['sin_cambios']} sin cambios, "
                f"{stats['errores']} errores"
            )
            ui_log(f"\n{summary}")

            severity = "information" if stats["errores"] == 0 else "warning"
            self.app.call_from_thread(self.app.notify, summary, severity=severity)
            self.app.call_from_thread(self.app.refresh_norms_table)
            self.app.call_from_thread(self._set_sync_done)

            client.close()
            mgrs["conn"].close()

        except Exception as e:
            ui_log(f"[red]Error fatal: {e}[/red]")
            self.app.call_from_thread(self.app.notify, f"Error: {e}", severity="error")
            self.app.call_from_thread(self._set_sync_done)

    def _set_sync_done(self) -> None:
        """Cambia el boton Cancelar por Cerrar al terminar el sync."""
        self._cancelled = True  # evita que Esc intente cancelar algo ya terminado
        btn = self.query_one("#sync-cancel", Button)
        btn.label = "Cerrar  [Esc]"
        btn.add_class("primary")
        btn.remove_class("ghost")

    def action_cancel_sync(self) -> None:
        self._cancelled = True
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sync-cancel":
            self.action_cancel_sync()


# ── APP PRINCIPAL ─────────────────────────────────────────────────────────────

class BCNApp(App):
    """BCN Extractor TUI."""

    TITLE = "BCN Extractor"
    CSS_PATH = "tui.css"
    DARK = True

    BINDINGS = [
        Binding("1", "show_tab('normas')", "Normas", show=True),
        Binding("2", "show_tab('dashboard')", "Dashboard", show=True),
        Binding("3", "show_tab('logs')", "Logs", show=True),
        Binding("s", "sync", "Sync", show=True),
        Binding("slash", "focus_search", "Buscar", show=True),
        Binding("r", "read_norm", "Leer", show=True),
        Binding("q", "quit", "Salir", show=True),
    ]

    _selected_inst: reactive = reactive((None, "", 0))
    _selected_norm: reactive = reactive(None)
    _all_instituciones: list = []

    # ── COMPOSE ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent(id="tabs"):
            with TabPane("1  Normas", id="tab-normas"):
                with Horizontal(id="main-layout"):
                    with Vertical(id="sidebar"):
                        yield Static("INSTITUCIONES", id="sidebar-header")
                        yield Input(placeholder="Filtrar...", id="inst-search")
                        yield ListView(id="inst-list")

                    with Vertical(id="content-area"):
                        with Horizontal(id="content-header"):
                            yield Label("Selecciona una institucion", id="inst-label")
                            with Horizontal(id="header-btns"):
                                yield Button(
                                    "Sincronizar [s]", id="btn-sync", classes="ghost"
                                )
                                yield Button(
                                    "Leer  [r]", id="btn-read", classes="ghost"
                                )
                        yield DataTable(
                            id="norms-table", cursor_type="row", zebra_stripes=True
                        )

                    with Vertical(id="detail-panel"):
                        yield Static("DETALLE", id="detail-header-label")
                        with ScrollableContainer(id="detail-scroll"):
                            yield Static("Selecciona una norma", id="detail-body")
                        with Vertical(id="detail-actions"):
                            yield Button(
                                "Leer texto completo",
                                id="btn-read-detail",
                                classes="primary",
                            )
                            yield Button(
                                "Abrir en BCN", id="btn-open-bcn", classes="ghost"
                            )

            with TabPane("2  Dashboard", id="tab-dashboard"):
                with ScrollableContainer(id="dashboard-content"):
                    yield Static("Cargando estadisticas...", id="dash-body")

            with TabPane("3  Logs", id="tab-logs"):
                with Vertical(id="logs-content"):
                    yield RichLog(id="log-widget", auto_scroll=True, markup=True)

        yield Footer()

    # ── MOUNT ────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.query_one("#norms-table", DataTable).add_columns(
            "ID", "Tipo", "Numero", "Titulo", "Fecha", "Estado"
        )
        self._load_instituciones()
        self._load_dashboard()

    # ── INSTITUCIONES ─────────────────────────────────────────────────────────

    def _load_instituciones(self) -> None:
        try:
            mgrs = _init_managers()
            self._all_instituciones = mgrs["instituciones"].get_all()
            mgrs["conn"].close()
            self._render_inst_list(self._all_instituciones)
        except Exception as e:
            self.notify(f"Error cargando instituciones: {e}", severity="error")

    def _render_inst_list(self, instituciones: list) -> None:
        lv = self.query_one("#inst-list", ListView)
        lv.clear()
        for inst in instituciones:
            item = ListItem(Label(inst.nombre[:27]))
            item._inst_id = inst.id
            item._inst_nombre = inst.nombre
            lv.append(item)

    # ── NORMAS ───────────────────────────────────────────────────────────────

    def refresh_norms_table(self) -> None:
        """Recarga la tabla de la institucion activa. Seguro llamarlo desde threads."""
        inst_id, inst_nombre, _ = self._selected_inst
        if inst_id:
            self._load_norms_for(inst_id, inst_nombre)

    def _load_norms_for(self, inst_id: int, inst_nombre: str) -> None:
        try:
            from rich.text import Text

            mgrs = _init_managers()
            normas = mgrs["normas"].get_by_institucion(inst_id)
            mgrs["conn"].close()

            table = self.query_one("#norms-table", DataTable)
            table.clear()

            for n in normas:
                est = n["estado"]
                table.add_row(
                    Text(f"#{n['id']}", style="dim"),
                    Text(n["tipo_nombre"], style="cyan"),
                    Text(n["numero"], style="dim"),
                    Text(n["titulo"][:52] + ("..." if len(n["titulo"]) > 52 else "")),
                    Text(
                        str(n["fecha_publicacion"]) if n["fecha_publicacion"] else "—",
                        style="dim",
                    ),
                    Text(est, style="green" if est == "vigente" else "red"),
                    key=str(n["id"]),
                )

            self.query_one("#inst-label", Label).update(
                f"{inst_nombre}  ·  {len(normas)} normas en DB"
            )
        except Exception as e:
            self.notify(f"Error cargando normas: {e}", severity="error")
            self._tui_log(f"[red]Error: {e}[/red]")

    # ── DETALLE ──────────────────────────────────────────────────────────────

    def _show_norm_detail(self, norm_id_str: str) -> None:
        """Usa NormsManager.get_by_id() que ya devuelve tipo, instituciones y materias."""
        try:
            nid = int(norm_id_str.lstrip("#"))
            mgrs = _init_managers()
            n = mgrs["normas"].get_by_id(nid)
            mgrs["conn"].close()

            if not n:
                return

            self._selected_norm = {
                "id": n["id"],
                "titulo": n["titulo"] or "",
                "md_path": n["md_path"],
            }

            est = n["estado"] or "vigente"
            lines = [
                f"[bold white]{n['titulo'] or '—'}[/bold white]\n",
                f"[dim]ID BCN[/dim]       #{n['id']}",
                f"[dim]Tipo[/dim]         {n['tipo_nombre'] or '—'}",
                f"[dim]Numero[/dim]       {n['numero'] or '—'}",
                f"[dim]Publicacion[/dim]  [yellow]{n['fecha_publicacion'] or '—'}[/yellow]",
                f"[dim]Promulgacion[/dim] {n['fecha_promulgacion'] or '—'}",
                f"[dim]Estado[/dim]       {'[green]vigente[/green]' if est == 'vigente' else '[red]derogada[/red]'}",
                f"[dim]Organismo[/dim]    {n['organismo'] or '—'}",
            ]

            if n["instituciones"]:
                lines.append("\n[dim]Instituciones[/dim]")
                for inst in n["instituciones"]:
                    lines.append(f"  {inst}")

            if n["materias"]:
                lines.append("\n[dim]Materias[/dim]")
                for m in n["materias"][:6]:
                    lines.append(f"  {m}")

            self.query_one("#detail-body", Static).update("\n".join(lines))

        except Exception as e:
            self._tui_log(f"[red]Error cargando detalle: {e}[/red]")

    # ── DASHBOARD ────────────────────────────────────────────────────────────

    def _load_dashboard(self) -> None:
        """Usa get_stats() de NormsManager, InstitutionManager y DownloadManager."""
        try:
            mgrs = _init_managers()
            ns = mgrs["normas"].get_stats()
            is_ = mgrs["instituciones"].get_stats()
            ls = mgrs["logger"].get_stats(days=7)
            mgrs["conn"].close()

            pct = round(ns["vigentes"] / ns["total"] * 100) if ns["total"] else 0

            lines = [
                "ESTADISTICAS GENERALES\n",
                f"  Normas total       {ns['total']:>8,}",
                f"  Vigentes           {ns['vigentes']:>8,}  ({pct}%)",
                f"  Derogadas          {ns['derogadas']:>8,}",
                f"  Instituciones      {is_['total']:>8,}",
                f"  Con normas         {is_['con_normas']:>8,}",
                f"  Sin normas         {is_['sin_normas']:>8,}",
                "",
                "OPERACIONES (ultimos 7 dias)\n",
                f"  Total              {ls['total']:>8,}",
            ]
            for estado, cnt in (ls.get("por_estado") or {}).items():
                lines.append(f"  {estado:<18} {cnt:>6,}")

            if ns.get("por_tipo"):
                lines.append("\nNORMAS POR TIPO\n")
                max_cnt = max(t["total"] for t in ns["por_tipo"]) or 1
                for t in ns["por_tipo"]:
                    bar = "█" * round(t["total"] / max_cnt * 22)
                    lines.append(f"  {t['tipo'][:22]:<22}  {bar:<22}  {t['total']:,}")

            if ls.get("errores_recientes"):
                lines.append("\nERRORES RECIENTES\n")
                for err in ls["errores_recientes"][:5]:
                    lines.append(f"  #{err['id_norma']}  {(err['error'] or '')[:56]}")

            self.query_one("#dash-body", Static).update("\n".join(lines))

        except Exception as e:
            self.query_one("#dash-body", Static).update(
                f"Error cargando estadisticas:\n{e}"
            )

    # ── LOG INTERNO ──────────────────────────────────────────────────────────

    def _tui_log(self, msg: str) -> None:
        try:
            self.query_one("#log-widget", RichLog).write(msg)
        except Exception:
            pass

    # ── EVENTOS ──────────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "inst-list":
            return
        inst_id = getattr(event.item, "_inst_id", None)
        inst_nombre = getattr(event.item, "_inst_nombre", "")
        if inst_id is None:
            return
        self._selected_inst = (inst_id, inst_nombre, 0)
        self._load_norms_for(inst_id, inst_nombre)
        self._tui_log(f"[cyan]Institucion: {inst_nombre} (#{inst_id})[/cyan]")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "inst-search":
            return
        q = event.value.strip().lower()
        filtered = (
            [i for i in self._all_instituciones if q in i.nombre.lower()]
            if q
            else self._all_instituciones
        )
        self._render_inst_list(filtered)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "norms-table":
            self._show_norm_detail(event.row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-sync":
            self.action_sync()
        elif bid in ("btn-read", "btn-read-detail"):
            self.action_read_norm()
        elif bid == "btn-open-bcn":
            norm = self._selected_norm
            if norm:
                import webbrowser

                webbrowser.open(f"https://www.leychile.cl/Navegar?idNorma={norm['id']}")

    # ── ACCIONES ─────────────────────────────────────────────────────────────

    def action_sync(self) -> None:
        inst_id, inst_nombre, _ = self._selected_inst
        if not inst_id:
            self.notify("Selecciona una institucion primero", severity="warning")
            return
        self.push_screen(SyncModal(inst_id, inst_nombre))

    def action_read_norm(self) -> None:
        norm = self._selected_norm
        if not norm:
            self.notify("Selecciona una norma primero", severity="warning")
            return
        self.push_screen(ReaderModal(norm["id"], norm["titulo"], norm.get("md_path")))

    def action_focus_search(self) -> None:
        self.query_one("#inst-search", Input).focus()

    def action_show_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = f"tab-{tab}"
        if tab == "dashboard":
            self._load_dashboard()

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if event.pane and event.pane.id == "tab-dashboard":
            self._load_dashboard()


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        import textual  # noqa
    except ImportError:
        print("Textual no esta instalado. Ejecuta: pip install textual rich")
        sys.exit(1)

    try:
        mgrs = _init_managers()
        mgrs["conn"].close()
    except Exception as e:
        print(f"No se pudo conectar a la base de datos: {e}")
        print("Verifica que Docker este corriendo: docker-compose up -d")
        sys.exit(1)

    BCNApp().run()
