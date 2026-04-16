"""
tui/tabs/dashboard.py

Tab de estadísticas: normas, instituciones, metadata y operaciones recientes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Static

if TYPE_CHECKING:
    from tui.state import AppState


class DashboardTab(ScrollableContainer):
    """Tab de estadísticas generales del sistema."""

    def __init__(self, state: AppState) -> None:
        super().__init__(id="dashboard-content")
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("Cargando estadisticas...", id="dash-body")

    def load(self) -> None:
        """Recarga todas las estadísticas desde la DB. Llamar al activar el tab."""
        try:
            ns = self._state.normas.get_stats()
            is_ = self._state.instituciones.get_stats()
            ls = self._state.logger.get_stats(days=7)
            ms = self._state.metadata.get_stats()

            pct_vigentes = round(ns["vigentes"] / ns["total"] * 100) if ns["total"] else 0

            lines = [
                "NORMAS\n",
                f"  Total              {ns['total']:>8,}",
                f"  Vigentes           {ns['vigentes']:>8,}  ({pct_vigentes}%)",
                f"  Derogadas          {ns['derogadas']:>8,}",
                "",
                "INSTITUCIONES\n",
                f"  Total              {is_['total']:>8,}",
                f"  Con normas         {is_['con_normas']:>8,}",
                f"  Sin normas         {is_['sin_normas']:>8,}",
                "",
                "METADATA\n",
                f"  Entradas totales   {ms['total_entradas']:>8,}",
                f"  Normas con meta    {ms['normas_con_metadata']:>8,}",
            ]

            if ms.get("por_clave"):
                for entrada in ms["por_clave"]:
                    lines.append(f"  {entrada['clave']:<18} {entrada['total']:>6,}")

            lines += [
                "",
                "OPERACIONES — ultimos 7 dias\n",
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