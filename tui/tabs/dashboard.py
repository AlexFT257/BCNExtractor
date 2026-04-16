"""
Dashboard TUI denso + responsive (adaptado al ancho)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Static

if TYPE_CHECKING:
    from tui.state import AppState


BARS = "▁▂▃▄▅▆▇█"


# ── Helpers ────────────────────────────────────────────────────────────────

def _spark(value: int, max_val: int, width: int) -> str:
    if not max_val:
        return " " * width
    ratio = value / max_val
    level = int(ratio * (len(BARS) - 1))
    return BARS[level] * width


def _hbar(value: int, total: int, width: int) -> str:
    if not total:
        return "·" * width
    filled = int(value / total * width)
    return "█" * filled + "·" * (width - filled)


def _fmt(n: int) -> str:
    return f"{n:,}"


def _section(title: str, width: int) -> str:
    line = "━" * max(10, width - len(title) - 6)
    return f"\n[bold #5a6380]━━━ {title} {line}[/bold #5a6380]\n"


# ── Dashboard ─────────────────────────────────────────────────────────────


class DashboardTab(ScrollableContainer):

    DEFAULT_CSS = """
    DashboardTab {
        padding: 1 2;
        background: #0d0f14;
    }
    """

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("Cargando…", id="content")

    # ── Load ──────────────────────────────────────────────────────────────

    def load(self) -> None:
        try:
            ns  = self._state.normas.get_stats()
            is_ = self._state.instituciones.get_stats()
            ls  = self._state.logger.get_stats(days=7)
            ms  = self._state.metadata.get_stats()
            nlp = self._state.nlp.get_stats()
        except Exception as e:
            self.query_one("#content", Static).update(f"[red]{e}[/red]")
            return

        width = self.size.width or 80

        parts = []
        parts.append(self._render_kpis(ns, ls, width))
        parts.append(self._render_normas(ns, width))
        parts.append(self._render_instituciones(is_, width))
        parts.append(self._render_tipos(ns, width))
        parts.append(self._render_ops(ls, width))
        parts.append(self._render_metadata(ms, width))
        parts.append(self._render_nlp(nlp, width))
        parts.append(self._render_errores(ls, width))

        self.query_one("#content", Static).update("\n".join(parts))

    # ── Secciones ─────────────────────────────────────────────────────────

    def _render_kpis(self, ns, ls, width) -> str:
        total = ns.get("total", 0)
        vig   = ns.get("vigentes", 0)
        der   = ns.get("derogadas", 0)
        ops   = ls.get("total", 0)
        errs  = len(ls.get("errores_recientes") or [])

        # modo compacto si pantalla chica
        if width < 70:
            return (
                f"[bold]{_fmt(total)}[/bold] normas · "
                f"[#00d4aa]{_fmt(vig)}[/#00d4aa] vig · "
                f"[#ff4f6e]{_fmt(der)}[/#ff4f6e] der · "
                f"{_fmt(ops)} ops · "
                f"{_fmt(errs)} err\n"
            )

        return (
            "[bold white]"
            f"{_fmt(total):>10}   {_fmt(vig):>10}   {_fmt(der):>10}   {_fmt(ops):>10}   {_fmt(errs):>10}"
            "[/bold white]\n"
            "[#5a6380]"
            f"{'TOTAL':>10}   {'VIGENTES':>10}   {'DEROGADAS':>10}   {'OPS 7D':>10}   {'ERRORES':>10}"
            "[/#5a6380]\n"
        )

    def _render_normas(self, ns, width) -> str:
        total = ns.get("total", 0)
        vig   = ns.get("vigentes", 0)
        der   = ns.get("derogadas", 0)
        ver   = ns.get("versiones_archivadas", 0)

        bar_w = max(10, width // 4)

        pct_v = int((vig / total) * 100) if total else 0
        pct_d = int((der / total) * 100) if total else 0

        return (
            _section("NORMAS", width) +
            f"  Vigentes   [#00d4aa]{_hbar(vig, total, bar_w)}[/#00d4aa] {_fmt(vig)} ({pct_v}%)\n"
            f"  Derogadas  [#ff4f6e]{_hbar(der, total, bar_w)}[/#ff4f6e] {_fmt(der)} ({pct_d}%)\n"
            f"  Versiones  [#5a6380]{_fmt(ver)}[/#5a6380]\n"
        )

    def _render_instituciones(self, is_, width) -> str:
        total = is_.get("total", 0)
        con   = is_.get("con_normas", 0)
        sin   = is_.get("sin_normas", 0)

        bar_w = max(10, width // 4)
        pct = int((con / total) * 100) if total else 0

        return (
            _section("INSTITUCIONES", width) +
            f"  Con normas [#00d4aa]{_hbar(con, total, bar_w)}[/#00d4aa] {_fmt(con)} ({pct}%)\n"
            f"  Sin normas {_fmt(sin)}\n"
        )

    def _render_tipos(self, ns, width) -> str:
        tipos = ns.get("por_tipo") or []
        if not tipos:
            return _section("TIPOS", width) + "  Sin datos\n"

        max_val = max(t["total"] for t in tipos)
        bar_w = max(8, width // 5)

        lines = [_section("TIPOS", width)]
        for t in tipos[:10]:
            bar = _spark(t["total"], max_val, bar_w)
            lines.append(f"  [#4f7cff]{bar}[/#4f7cff] {t['tipo'][:18]:<18} {_fmt(t['total'])}")

        return "\n".join(lines)

    def _render_ops(self, ls, width) -> str:
        por_estado = ls.get("por_estado") or {}
        max_val = max(por_estado.values(), default=1)
        bar_w = max(8, width // 5)

        lines = [_section("OPERACIONES (7D)", width)]
        for estado, cnt in sorted(por_estado.items(), key=lambda x: -x[1]):
            color = {
                "exitoso": "#00d4aa",
                "error": "#ff4f6e",
                "pendiente": "#f5a623",
            }.get(estado, "#5a6380")

            bar = _spark(cnt, max_val, bar_w)
            lines.append(f"  [{color}]{bar}[/{color}] {estado:<12} {_fmt(cnt)}")

        return "\n".join(lines)

    def _render_metadata(self, ms, width) -> str:
        claves = ms.get("por_clave") or []
        max_val = max((c["total"] for c in claves), default=1)
        bar_w = max(8, width // 5)

        lines = [_section("METADATA", width)]
        for c in claves[:8]:
            bar = _spark(c["total"], max_val, bar_w)
            lines.append(f"  {bar} {c['clave'][:16]:<16} {_fmt(c['total'])}")

        return "\n".join(lines)

    def _render_nlp(self, nlp, width) -> str:
        total = nlp.get("total_referencias", 0)
        res   = nlp.get("referencias_resueltas", 0)
        pen   = nlp.get("referencias_pendientes", 0)
        obl   = nlp.get("total_obligaciones", 0)

        bar_w = max(10, width // 4)
        pct = int((res / total) * 100) if total else 0

        return (
            _section("NLP", width) +
            f"  Resueltas   [#9b59b6]{_hbar(res, total, bar_w)}[/#9b59b6] {_fmt(res)} ({pct}%)\n"
            f"  Pendientes  {_fmt(pen)}\n"
            f"  Obligaciones {_fmt(obl)}\n"
        )

    def _render_errores(self, ls, width) -> str:
        errores = ls.get("errores_recientes") or []

        lines = [_section("ERRORES", width)]

        if not errores:
            lines.append("  [#00d4aa]Sin errores ✓[/#00d4aa]")
            return "\n".join(lines)

        for err in errores[:8]:
            msg = (err.get("error") or "")[: max(30, width - 25)]
            lines.append(f"  [#ff4f6e]{err['id_norma']}[/#ff4f6e] · {msg}")

        return "\n".join(lines)