"""
tui/tabs/metadata.py

Tab de metadata EAV: búsqueda de normas por clave/valor y visualización
de la metadata completa de la norma seleccionada.

Diseño:
  - Sidebar izquierdo: RadioSet con las claves EAV disponibles + input de valor
  - Tabla central: normas que coinciden con el filtro
  - Panel derecho: metadata completa de la norma seleccionada
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

if TYPE_CHECKING:
    from tui.state import AppState

_CLAVES_DEFAULT = ["derogado", "materia", "organismo", "es_tratado"]


class MetadataTab(Vertical):
    """
    Búsqueda de normas por metadata EAV y visualización de metadata completa.
    """

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._claves: list[str] = []
        self._clave_activa: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            # ── Sidebar de filtros ─────────────────────────────────────────
            with Vertical(id="sidebar"):
                yield Static("BUSCAR POR METADATA", id="sidebar-header")
                yield Static("Clave", classes="field-label")
                # RadioSet vacío — se puebla en on_mount con las claves de la DB
                yield RadioSet(id="clave-radioset")
                yield Static("Valor", classes="field-label")
                yield Input(placeholder="Filtrar por valor...", id="meta-valor")
                yield Button("Buscar", id="btn-meta-buscar", classes="primary")

            # ── Tabla de resultados ────────────────────────────────────────
            with Vertical(id="content-area"):
                with Horizontal(id="content-header"):
                    yield Label("Selecciona una clave y un valor", id="meta-label")
                yield DataTable(id="meta-table", cursor_type="row", zebra_stripes=True)

            # ── Panel de detalle de metadata ───────────────────────────────
            with Vertical(id="detail-panel"):
                yield Static("METADATA", id="detail-header-label")
                with ScrollableContainer(id="detail-scroll"):
                    yield Static(
                        "Selecciona una norma para ver su metadata completa",
                        id="meta-detail-body",
                    )

    def on_mount(self) -> None:
        self.query_one("#meta-table", DataTable).add_columns(
            "ID", "Tipo", "Número", "Título", "Estado"
        )
        self._load_claves()

    # ── CARGA DE CLAVES ───────────────────────────────────────────────────────

    def _load_claves(self) -> None:
        """
        Carga las claves EAV desde la DB y las monta en el RadioSet.
        Se usa mount() porque las claves son dinámicas y no se conocen en compose().
        """
        try:
            claves_db = self._state.metadata.get_claves_disponibles()
            self._claves = claves_db if claves_db else _CLAVES_DEFAULT
        except Exception:
            self._claves = _CLAVES_DEFAULT

        radio_set = self.query_one("#clave-radioset", RadioSet)
        for clave in self._claves:
            radio_set.mount(RadioButton(clave, compact=True))

        # Seleccionar la primera por defecto
        if self._claves:
            self._clave_activa = self._claves[0]

    # ── BÚSQUEDA ──────────────────────────────────────────────────────────────

    def _buscar(self) -> None:
        valor = self.query_one("#meta-valor", Input).value.strip()

        if not self._clave_activa:
            self.app.notify("Selecciona una clave primero", severity="warning")
            return
        if not valor:
            self.app.notify("Escribe un valor para filtrar", severity="warning")
            return

        try:
            resultados = self._state.metadata.get_normas_by_clave_valor(
                clave=self._clave_activa, valor=valor, limit=200
            )
            self._render_resultados(resultados, self._clave_activa, valor)
        except Exception as e:
            self.app.notify(f"Error en búsqueda: {e}", severity="error")

    def _render_resultados(self, resultados: list, clave: str, valor: str) -> None:
        table = self.query_one("#meta-table", DataTable)
        table.clear()

        self.query_one("#meta-label", Label).update(
            f"{clave} = '{valor}'  ·  {len(resultados)} resultados"
        )

        for n in resultados:
            est = n.get("estado", "vigente")
            table.add_row(
                Text(f"#{n['norma_id']}", style="dim"),
                Text(n.get("tipo_nombre", "—"), style="cyan"),
                Text(n.get("numero", "—"), style="dim"),
                Text(
                    (n.get("titulo", "") or "")[:52]
                    + ("..." if len(n.get("titulo", "") or "") > 52 else "")
                ),
                Text(est, style="green" if est == "vigente" else "red"),
                key=n["norma_id"],
            )

    # ── DETALLE DE METADATA ───────────────────────────────────────────────────

    def _show_metadata_detail(self, norm_id: int) -> None:
        """Carga y muestra la metadata EAV completa de una norma."""
        try:
            meta = self._state.metadata.get_by_norma(norm_id)
            norma = self._state.normas.get_by_id(norm_id)

            lines: list[str] = []

            if norma:
                lines += [
                    f"[bold white]{norma.get('titulo', '—')}[/bold white]\n",
                    f"[dim]ID BCN[/dim]    #{norm_id}",
                    f"[dim]Tipo[/dim]      {norma.get('tipo_nombre', '—')}",
                    f"[dim]Número[/dim]    {norma.get('numero', '—')}",
                    "",
                ]

            if not meta:
                lines.append("[dim]Sin metadata registrada[/dim]")
            else:
                lines.append("[dim]── Metadata EAV ──[/dim]\n")
                for clave, valor in meta.items():
                    if isinstance(valor, list):
                        lines.append(f"[dim]{clave}[/dim]")
                        for v in valor:
                            lines.append(f"  · {v}")
                    else:
                        v_str = (
                            "[green]sí[/green]"
                            if valor is True
                            else "[red]no[/red]"
                            if valor is False
                            else str(valor)
                        )
                        lines.append(f"[dim]{clave}[/dim]    {v_str}")

            self.query_one("#meta-detail-body", Static).update("\n".join(lines))

        except Exception as e:
            self.app.notify(f"Error cargando metadata: {e}", severity="error")

    # ── EVENTOS ───────────────────────────────────────────────────────────────

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Actualiza la clave activa cuando el usuario cambia la selección."""
        event.stop()
        # El label del RadioButton es la clave EAV
        self._clave_activa = str(event.pressed.label)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-meta-buscar":
            event.stop()
            self._buscar()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "meta-valor":
            self._buscar()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "meta-table":
            self._show_metadata_detail(int(event.row_key.value))
