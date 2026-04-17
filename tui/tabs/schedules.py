"""
tui/tabs/schedules.py

Tab de schedules: estado de los jobs del scheduler y opción de ejecutar sync
inmediato de un job seleccionado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, DataTable, Label, Static

if TYPE_CHECKING:
    from tui.state import AppState


class SchedulesTab(Vertical):
    """
    Muestra el estado de todos los jobs registrados en scheduler_jobs.
    Permite refrescar el estado y ejecutar un sync inmediato del job seleccionado.
    """

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._selected_job: Optional[dict] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="content-area"):
            with Vertical(id="sched-panel"):
                with Horizontal(id="content-header"):
                    yield Label("Jobs registrados", id="sched-label")
                    with Horizontal(id="header-btns"):
                        yield Button("Refrescar", id="btn-sched-refresh", classes="ghost")
                        yield Button("Sync ahora", id="btn-sched-run", classes="ghost")
                yield DataTable(
                    id="sched-table", cursor_type="row", zebra_stripes=True
                )

            with Vertical(id="detail-panel"):
                yield Static("DETALLE", id="detail-header-label")
                with ScrollableContainer(id="detail-scroll"):
                    yield Static("Selecciona un job", id="sched-detail-body")

    def on_mount(self) -> None:
        self.query_one("#sched-table", DataTable).add_columns(
            "Job", "Inst", "Horario", "PID", "Proceso", "Último run", "Resultado", "Runs"
        )
        self.load()


    def load(self) -> None:
        """Recarga todos los jobs desde la DB."""
        try:
            jobs = self._state.schedules.get_all(limit=100)
            self._render_jobs(jobs)
            self.query_one("#sched-label", Label).update(
                f"Jobs registrados  ·  {len(jobs)} total"
            )
        except Exception as e:
            self.app.notify(f"Error cargando schedules: {e}", severity="error")

    def _render_jobs(self, jobs: list) -> None:
        table = self.query_one("#sched-table", DataTable)
        table.clear()

        for job in jobs:
            last_status = job.get("last_status") or "—"
            if last_status == "ok":
                result_text = Text("✓ ok", style="green")
            elif last_status == "error":
                result_text = Text("✗ error", style="red")
            else:
                result_text = Text(last_status, style="dim")

            status = job.get("status") or "stopped"
            if status == "running":
                process_text = Text("● running", style="bold green")
            elif status == "scheduled":
                process_text = Text("◌ scheduled", style="cyan")
            else:
                process_text = Text("○ stopped", style="dim")

            pid = job.get("pid")
            pid_text = Text(str(pid), style="dim") if pid else Text("—", style="dim")

            last_run = job.get("last_run")
            last_run_str = last_run.strftime("%Y-%m-%d %H:%M") if last_run else "nunca"

            table.add_row(
                Text(job["nombre"], style="cyan"),
                Text(str(job["inst_id"]), style="dim"),
                Text(f"{job['hora']:02d}:{job['minuto']:02d}"),
                pid_text,
                process_text,
                Text(last_run_str, style="dim"),
                result_text,
                Text(str(job.get("run_count", 0)), style="dim"),
                key=str(job["id"]),
            )

    def _show_job_detail(self, job_id: int) -> None:
        try:
            job = self._state.schedules.get_by_id(job_id)
            if not job:
                return

            self._selected_job = job

            last_run = job.get("last_run")
            last_run_str = last_run.strftime("%Y-%m-%d %H:%M") if last_run else "nunca"
            created = job.get("created_at")
            created_str = created.strftime("%Y-%m-%d %H:%M") if created else "—"

            # Estado del proceso
            status = job.get("status") or "stopped"
            if status == "running":
                status_fmt = "[bold green]● running[/bold green]"
            elif status == "scheduled":
                status_fmt = "[cyan]◌ scheduled[/cyan]"
            else:
                status_fmt = "[dim]○ stopped[/dim]"

            # Resultado de la última ejecución
            last_status = job.get("last_status") or "—"
            result_fmt = (
                "[green]✓ ok[/green]" if last_status == "ok"
                else "[red]✗ error[/red]" if last_status == "error"
                else f"[dim]{last_status}[/dim]"
            )

            pid = job.get("pid")
            pid_str = str(pid) if pid else "—"

            lines = [
                f"[bold white]{job['nombre']}[/bold white]\n",
                f"[dim]ID[/dim]            {job['id']}",
                f"[dim]Institución[/dim]   #{job['inst_id']}",
                f"[dim]Horario[/dim]       {job['hora']:02d}:{job['minuto']:02d} diario",
                f"[dim]Límite normas[/dim] {job['limite']}",
                f"[dim]Creado[/dim]        {created_str}",
                "",
                f"[dim]PID[/dim]           {pid_str}",
                f"[dim]Proceso[/dim]       {status_fmt}",
                "",
                f"[dim]Último run[/dim]    {last_run_str}",
                f"[dim]Resultado[/dim]     {result_fmt}",
                f"[dim]Ejecuciones[/dim]   {job.get('run_count', 0)}",
            ]

            if job.get("last_error"):
                lines += [
                    "",
                    "[dim]Último error[/dim]",
                    f"[red]{job['last_error'][:120]}[/red]",
                ]

            self.query_one("#sched-detail-body", Static).update("\n".join(lines))

        except Exception as e:
            self.app.notify(f"Error cargando detalle: {e}", severity="error")

    def _run_selected_now(self) -> None:
        """Ejecuta el sync del job seleccionado abriendo SyncModal."""
        if not self._selected_job:
            self.app.notify("Selecciona un job primero", severity="warning")
            return

        from tui.screens.sync_modal import SyncModal

        inst_id = self._selected_job["inst_id"]
        nombre = self._selected_job["nombre"]
        limite = self._selected_job.get("limite")
        self.app.push_screen(SyncModal(inst_id, nombre, limit=limite))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-sched-refresh":
            event.stop()
            self.load()
        elif event.button.id == "btn-sched-run":
            event.stop()
            self._run_selected_now()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "sched-table":
            self._show_job_detail(int(event.row_key.value))