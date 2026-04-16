"""
tui/tabs/nlp.py

Tab NLP: análisis de la norma seleccionada en NormasTab.
Muestra referencias normativas (salientes e inversas), entidades nombradas
y obligaciones detectadas mediante sub-tabs internos.

El tab escucha el mensaje NormSelected que NormasTab emite al seleccionar
una norma, para mantenerse sincronizado sin acoplamiento directo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import (
    DataTable,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

if TYPE_CHECKING:
    from tui.state import AppState

# Colores por tipo de entidad NER
_COLORES_ENTIDAD = {
    "organismo": "cyan",
    "persona": "yellow",
    "lugar": "green",
    "fecha": "magenta",
}


class NLPTab(Vertical):
    """
    Muestra el análisis NLP de la norma actualmente seleccionada en NormasTab.
    Se actualiza al recibir el mensaje NormSelected desde la app.
    """

    # Mensaje que la app envía cuando cambia la norma seleccionada
    class NormSelected(Message):
        def __init__(self, norm_id: int, titulo: str) -> None:
            super().__init__()
            self.norm_id = norm_id
            self.titulo = titulo

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._norm_id: Optional[int] = None
        self._norm_titulo: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="nlp-header"):
            yield Label(
                "Selecciona una norma en el tab Normas para ver su análisis NLP",
                id="nlp-norm-label",
            )

        with TabbedContent(id="nlp-tabs"):
            with TabPane("Referencias", id="nlp-tab-referencias"):
                yield DataTable(
                    id="nlp-ref-table", cursor_type="row", zebra_stripes=True
                )
            with TabPane("Citado por", id="nlp-tab-citado"):
                yield DataTable(
                    id="nlp-citado-table", cursor_type="row", zebra_stripes=True
                )
            with TabPane("Entidades", id="nlp-tab-entidades"):
                yield DataTable(
                    id="nlp-ent-table", cursor_type="row", zebra_stripes=True
                )
            with TabPane("Obligaciones", id="nlp-tab-obligaciones"):
                with ScrollableContainer():
                    yield Static("", id="nlp-obl-body")

    def on_mount(self) -> None:
        self.query_one("#nlp-ref-table", DataTable).add_columns(
            "Tipo", "Número", "Año", "Organismo", "Texto original", "En DB"
        )
        self.query_one("#nlp-citado-table", DataTable).add_columns(
            "ID", "Tipo", "Número", "Título"
        )
        self.query_one("#nlp-ent-table", DataTable).add_columns(
            "Entidad", "Tipo", "Menciones"
        )

    # ── CARGA DE DATOS ────────────────────────────────────────────────────────

    def load_for_norm(self, norm_id: int, titulo: str) -> None:
        """Carga todos los datos NLP para la norma indicada."""
        self._norm_id = norm_id
        self._norm_titulo = titulo

        self.query_one("#nlp-norm-label", Label).update(
            f"#{norm_id}  {titulo[:80]}"
        )

        self._load_referencias(norm_id)
        self._load_citado_por(norm_id)
        self._load_entidades(norm_id)
        self._load_obligaciones(norm_id)

    def _load_referencias(self, norm_id: int) -> None:
        """Referencias normativas que esta norma cita (salientes)."""
        table = self.query_one("#nlp-ref-table", DataTable)
        table.clear()
        try:
            refs = self._state.nlp.get_referencias(norm_id)
            for ref in refs:
                en_db = Text("✓", style="green") if ref["resolvida"] else Text("—", style="dim")
                table.add_row(
                    Text(ref["tipo_norma"].replace("_", " ").title(), style="cyan"),
                    Text(ref["numero"] or "—"),
                    Text(ref["anio"] or "—", style="dim"),
                    Text((ref["organismo"] or "—")[:30]),
                    Text((ref["texto_original"] or "")[:45], style="dim"),
                    en_db,
                    key=str(ref["id"]),
                )
        except Exception as e:
            self.app.notify(f"Error cargando referencias: {e}", severity="error")

    def _load_citado_por(self, norm_id: int) -> None:
        """Grafo inverso: normas que citan a esta norma (entrantes)."""
        table = self.query_one("#nlp-citado-table", DataTable)
        table.clear()
        try:
            citantes = self._state.nlp.get_normas_que_referencian(norm_id)
            for n in citantes:
                table.add_row(
                    Text(f"#{n['id_norma']}", style="dim"),
                    Text(n.get("tipo", "—"), style="cyan"),
                    Text(n.get("numero", "—"), style="dim"),
                    Text((n.get("titulo", "") or "")[:55]),
                    key=str(n["id_norma"]),
                )
        except Exception as e:
            self.app.notify(f"Error cargando grafo inverso: {e}", severity="error")

    def _load_entidades(self, norm_id: int) -> None:
        """Entidades nombradas detectadas (NER), agrupadas por frecuencia."""
        table = self.query_one("#nlp-ent-table", DataTable)
        table.clear()
        try:
            entidades = self._state.nlp.get_entidades(norm_id)
            for ent in entidades:
                color = _COLORES_ENTIDAD.get(ent["tipo"], "white")
                table.add_row(
                    Text(ent["texto"][:55]),
                    Text(ent["tipo"], style=color),
                    Text(str(ent["frecuencia"]), style="dim"),
                )
        except Exception as e:
            self.app.notify(f"Error cargando entidades: {e}", severity="error")

    def _load_obligaciones(self, norm_id: int) -> None:
        """Obligaciones y plazos detectados via árbol sintáctico."""
        body = self.query_one("#nlp-obl-body", Static)
        try:
            obligaciones = self._state.nlp.get_obligaciones(norm_id)

            if not obligaciones:
                body.update("[dim]Sin obligaciones detectadas para esta norma[/dim]")
                return

            lines: list[str] = []
            for i, obl in enumerate(obligaciones, 1):
                lines.append(f"[bold]{i}.[/bold] {obl['texto_completo']}\n")

                if obl.get("sujeto"):
                    lines.append(f"  [dim]Sujeto[/dim]  {obl['sujeto']}")
                if obl.get("verbo"):
                    lines.append(f"  [dim]Verbo[/dim]   [cyan]{obl['verbo']}[/cyan]")
                if obl.get("plazo"):
                    lines.append(f"  [dim]Plazo[/dim]   [yellow]{obl['plazo']}[/yellow]")

                lines.append("")

            body.update("\n".join(lines))

        except Exception as e:
            self.app.notify(f"Error cargando obligaciones: {e}", severity="error")

    # ── EVENTOS ───────────────────────────────────────────────────────────────

    def on_nlp_tab_norm_selected(self, message: NormSelected) -> None:
        """Responde al mensaje enviado por BCNApp cuando cambia la norma activa."""
        self.load_for_norm(message.norm_id, message.titulo)
        
    