"""
tui/tabs/normas.py

Tab principal: sidebar de instituciones + tabla de normas + panel de detalle.
Toda la lógica de carga y presentación de normas vive aquí.
"""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from tui.tabs.nlp import NLPTab

if TYPE_CHECKING:
    from tui.state import AppState


class NormasTab(Vertical):
    """
    Tab de normas: sidebar con instituciones, tabla central y panel de detalle.

    Recibe AppState en el constructor para usar la conexión compartida.
    Las operaciones de escritura (sync) se delegan a SyncModal.
    """

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._all_instituciones: list = []
        self.selected_norm: Optional[dict] = None
        self.selected_inst: Optional[tuple[int, str, str]] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            with Vertical(id="sidebar"):
                yield Static("INSTITUCIONES", id="sidebar-header")
                yield Input(placeholder="Filtrar...", id="inst-search")
                yield ListView(id="inst-list")

            with Vertical(id="content-area"):
                with Horizontal(id="content-header"):
                    yield Label("Selecciona una institucion", id="inst-label")
                    with Horizontal(id="header-btns"):
                        yield Button("Sincronizar [s]", id="btn-sync", classes="ghost")
                        yield Button("Leer  [r]", id="btn-read", classes="ghost")
                yield DataTable(id="norms-table", cursor_type="row", zebra_stripes=True)

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
                    yield Button("Abrir en BCN", id="btn-open-bcn", classes="ghost")

    def on_mount(self) -> None:
        self.query_one("#norms-table", DataTable).add_columns(
            "ID", "Tipo", "Numero", "Titulo", "Fecha", "Estado"
        )
        self.load_instituciones()

    # ── INSTITUCIONES ─────────────────────────────────────────────────────────

    def load_instituciones(self) -> None:
        try:
            self._all_instituciones = self._state.instituciones.get_all(limit=500)
            self._render_inst_list(self._all_instituciones)
        except Exception as e:
            self.app.notify(f"Error cargando instituciones: {e}", severity="error")

    def _render_inst_list(self, instituciones: list) -> None:
        lv = self.query_one("#inst-list", ListView)
        lv.clear()
        for inst in instituciones:
            item = ListItem(Label(inst.nombre[:27]))
            item._inst_id = inst.id
            item._inst_nombre = inst.nombre
            lv.append(item)

    # ── NORMAS ────────────────────────────────────────────────────────────────

    def load_norms_for(self, inst_id: int, inst_nombre: str) -> None:
        try:
            normas = self._state.normas.get_by_institucion(inst_id)

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
                    Text(
                        est,
                        style="green" if est == "vigente" else "red",
                    ),
                    key=str(n["id"]),
                )

            self.query_one("#inst-label", Label).update(
                f"{inst_nombre}  ·  {len(normas)} normas en DB"
            )
        except Exception as e:
            self.app.notify(f"Error cargando normas: {e}", severity="error")

    def refresh_norms_table(self) -> None:
        """Recarga la tabla de la institución activa. Seguro llamarlo desde threads."""
        selected = getattr(self.app, "_selected_inst", (None, "", 0))
        inst_id, inst_nombre, _ = selected
        if inst_id:
            self.load_norms_for(inst_id, inst_nombre)

    # ── DETALLE ───────────────────────────────────────────────────────────────

    def show_norm_detail(self, norm_id_str: str) -> None:
        """Carga y muestra el detalle de una norma en el panel lateral."""
        try:
            nid = int(norm_id_str.lstrip("#"))
            n = self._state.normas.get_by_id(nid)

            if not n:
                return

            self.selected_norm = {
                "id": n["id"],
                "titulo": n["titulo"] or "",
                "md_path": n["md_path"],
            }

            # Notificar a NLPTab que la norma activa cambió
            from tui.tabs.nlp import NLPTab

            result = self.app._nlp_tab.on_nlp_tab_norm_selected(
                NLPTab.NormSelected(n["id"], n["titulo"] or "")
            )
            if result is not None:
                self.app.notify(result)

            est = n["estado"] or "vigente"
            lines = [
                f"[bold white]{n['titulo'] or '—'}[/bold white]\n",
                f"[dim]ID BCN[/dim]       #{n['id']}",
                f"[dim]Tipo[/dim]         {n['tipo_nombre'] or '—'}",
                f"[dim]Numero[/dim]       {n['numero'] or '—'}",
                f"[dim]Publicacion[/dim]  [yellow]{n['fecha_publicacion'] or '—'}[/yellow]",
                f"[dim]Promulgacion[/dim] {n['fecha_promulgacion'] or '—'}",
                f"[dim]Estado[/dim]       "
                + (
                    "[green]vigente[/green]"
                    if est == "vigente"
                    else "[red]derogada[/red]"
                ),
                f"[dim]Organismo[/dim]    {n['organismo'] or '—'}",
            ]

            if n.get("instituciones"):
                lines.append("\n[dim]Instituciones[/dim]")
                for inst in n["instituciones"]:
                    lines.append(f"  {inst}")

            if n.get("materias"):
                lines.append("\n[dim]Materias[/dim]")
                for m in n["materias"][:6]:
                    lines.append(f"  {m}")

            self.query_one("#detail-body", Static).update("\n".join(lines))

        except Exception as e:
            self.app.notify(f"Error cargando detalle: {e}", severity="error")

    # ── EVENTOS ───────────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "inst-list":
            return
        inst_id = getattr(event.item, "_inst_id", None)
        inst_nombre = getattr(event.item, "_inst_nombre", "")
        if inst_id is None:
            return
        self.selected_inst = (inst_id, inst_nombre, 0)
        self.load_norms_for(inst_id, inst_nombre)

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
            self.show_norm_detail(event.row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-sync":
            self.app.action_sync()
        elif bid in ("btn-read", "btn-read-detail"):
            self.app.action_read_norm()
        elif bid == "btn-open-bcn":
            norm = self.selected_norm
            if not norm:
                self.notify("Selecciona una norma primero", severity="warning")
                return

            webbrowser.open(f"https://www.leychile.cl/Navegar?idNorma={norm['id']}")
