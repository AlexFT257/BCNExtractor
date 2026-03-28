"""
Toda la lógica de presentación vive acá.
Los comandos nunca llaman a print() directamente.
"""

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.console import console

# ── Normas ────────────────────────────────────────────────────────────────────


def print_normas_list(normas: list, verbose: bool = False):
    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        highlight=True,
        header_style="bold cyan",
    )
    table.add_column("N°", style="dim", width=4, justify="right")
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Tipo", width=12)
    table.add_column("Número", width=10)
    table.add_column("Título")
    if verbose:
        table.add_column("Publicación", width=12)

    for i, norma in enumerate(normas, 1):
        row = [
            str(i),
            str(norma["id"]),
            norma.get("tipo", "—"),
            norma.get("numero", "—"),
            norma["titulo"][:70],
        ]
        if verbose:
            row.append(str(norma.get("fecha_publicacion", "—")))
        table.add_row(*row)

    console.print(table)


def print_norma_preview(xml: str):
    lines = "\n".join(xml.split("\n")[:30]) + "\n..."
    console.print(Panel(lines, title="Vista previa XML", border_style="dim"))


def print_search_results(results: list):
    if not results:
        console.print("[yellow]No se encontraron resultados.[/yellow]")
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        header_style="bold cyan",
    )
    table.add_column("N°", style="dim", width=4, justify="right")
    table.add_column("Estado", width=3, justify="center")
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Título")
    table.add_column("Tipo", width=20)
    table.add_column("Número", width=10)
    table.add_column("Publicación", width=12)

    for i, norma in enumerate(results, 1):
        estado_icon = "🟢" if norma["estado"] == "vigente" else "🔴"
        table.add_row(
            str(i),
            estado_icon,
            str(norma["norma_id"]),
            norma["titulo"][:60],
            norma.get("tipo_nombre", "—"),
            norma.get("numero", "—"),
            str(norma.get("fecha_publicacion", "—")),
        )

    console.print(f"\n  [bold]{len(results)}[/bold] resultado(s) encontrado(s)\n")
    console.print(table)


def print_sync_progress(i: int, total: int, id_norma: int, result: str):
    color = {"nueva": "green", "actualizada": "yellow", "sin_cambios": "dim"}.get(
        result, "red"
    )
    console.print(
        f"  [{i}/{total}] Norma [cyan]{id_norma}[/cyan] → [bold {color}]{result}[/bold {color}]"
    )


def print_sync_error(i: int, total: int, id_norma: int, error: str):
    console.print(
        f"  [{i}/{total}] Norma [cyan]{id_norma}[/cyan] → [bold red]✗ {error}[/bold red]"
    )


def print_sync_summary(stats: dict, total: int):
    table = Table(box=box.ROUNDED, show_header=False, border_style="green")
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")

    table.add_row("Total procesadas", str(total))
    table.add_row("[green]Nuevas[/green]", str(stats["nuevas"]))
    table.add_row("[yellow]Actualizadas[/yellow]", str(stats["actualizadas"]))
    table.add_row("[dim]Sin cambios[/dim]", str(stats["sin_cambios"]))
    table.add_row("[red]Errores[/red]", str(stats["errores"]))

    console.print("\n")
    console.print(Panel(table, title="Sincronización completada", border_style="green"))


# ── Stats ─────────────────────────────────────────────────────────────────────


def print_stats(norms_stats: dict, inst_stats: dict, tipos_total: int, log_stats: dict):
    # Normas
    normas_table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    normas_table.add_column("Tipo", min_width=30)
    normas_table.add_column("Total", justify="right", style="bold")

    normas_table.add_row("Total normas", str(norms_stats["total"]))
    normas_table.add_row("[green]Vigentes[/green]", str(norms_stats["vigentes"]))
    normas_table.add_row("[red]Derogadas[/red]", str(norms_stats["derogadas"]))

    if norms_stats.get("por_tipo"):
        normas_table.add_section()
        for t in norms_stats["por_tipo"]:
            normas_table.add_row(f"  {t['tipo']}", str(t["total"]))

    # Instituciones
    inst_table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    inst_table.add_column("Métrica", min_width=20)
    inst_table.add_column("Valor", justify="right", style="bold")
    inst_table.add_row("Total", str(inst_stats["total"]))
    inst_table.add_row("[green]Con normas[/green]", str(inst_stats["con_normas"]))
    inst_table.add_row("[dim]Sin normas[/dim]", str(inst_stats["sin_normas"]))
    inst_table.add_row("Tipos de normas", str(tipos_total))

    # Operaciones recientes
    ops_table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    ops_table.add_column("Estado", min_width=16)
    ops_table.add_column("Cantidad", justify="right", style="bold")

    ops_table.add_row("Total", str(log_stats.get("total", 0)))

    por_estado = log_stats.get("por_estado", {})
    if por_estado:
        ops_table.add_section()
        for estado, count in por_estado.items():
            ops_table.add_row(f"  {estado.capitalize()}", str(count))

    console.print(Panel(normas_table, title="Normas", border_style="cyan"))
    console.print(Panel(inst_table, title="Instituciones", border_style="cyan"))
    console.print(
        Panel(ops_table, title="Operaciones (últimos 7 días)", border_style="cyan")
    )


def print_recent_errors(errors: list):
    if not errors:
        return
    console.print("\n[bold red]Errores recientes:[/bold red]")
    for err in errors:
        mensaje = err.get("error_mensaje") or "sin detalle"
        console.print(f"  Norma [cyan]{err['id_norma']}[/cyan] — {mensaje[:80]}")


# ── Cache ─────────────────────────────────────────────────────────────────────


def print_cache_stats(stats: dict):
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    table.add_column("Métrica", min_width=16)
    table.add_column("Valor", justify="right")

    table.add_row("Archivos", str(stats["total_archivos"]))
    table.add_row("Tamaño", f"{stats['tamano_total_mb']:.2f} MB")
    table.add_row("Directorio", stats["directorio"])

    console.print(Panel(table, title="Caché local", border_style="dim"))

# ── Scheduler ─────────────────────────────────────────────────────────────────


def print_scheduler_jobs(jobs: list):
    if not jobs:
        console.print("[yellow]No hay jobs registrados.[/yellow]")
        console.print("[dim]Usa 'scheduler add <inst_id>' para registrar uno.[/dim]")
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        highlight=True,
        header_style="bold cyan",
    )
    table.add_column("ID",        style="dim",  width=4,  justify="right")
    table.add_column("Inst",      style="cyan", width=6,  justify="right")
    table.add_column("Nombre",                  width=20)
    table.add_column("Horario",                 width=10, justify="center")
    table.add_column("Límite",                  width=7,  justify="right")
    table.add_column("Última ejecución",        width=18)
    table.add_column("Estado",                  width=8,  justify="center")
    table.add_column("Runs",                    width=5,  justify="right")

    status_style = {
        "ok":    "[green]ok[/green]",
        "error": "[red]error[/red]",
    }

    for job in jobs:
        last_run = job.get("last_run")
        last_run_str = last_run.strftime("%Y-%m-%d %H:%M") if last_run else "[dim]nunca[/dim]"

        last_status = job.get("last_status") or "—"
        status_str = status_style.get(last_status, f"[dim]{last_status}[/dim]")

        table.add_row(
            str(job["id"]),
            str(job["inst_id"]),
            job.get("nombre", "—"),
            f"{job['hora']:02d}:{job['minuto']:02d} UTC",
            str(job.get("limite", "—")),
            last_run_str,
            status_str,
            str(job.get("run_count", 0)),
        )

    console.print(f"\n  [bold]{len(jobs)}[/bold] job(s) registrado(s)\n")
    console.print(table)

    errors = [j for j in jobs if j.get("last_status") == "error" and j.get("last_error")]
    if errors:
        console.print("\n[bold red]Últimos errores:[/bold red]")
        for job in errors:
            console.print(
                f"  [cyan]{job['nombre']}[/cyan] — {job['last_error'][:80]}"
            )
            
# ── Metadata ──────────────────────────────────────────────────────────────────


def print_norma_metadata(id_norma: int, metadata: dict):
    if not metadata:
        console.print(f"[yellow]La norma {id_norma} no tiene metadata registrada.[/yellow]")
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        header_style="bold cyan",
    )
    table.add_column("Clave", style="bold", width=20)
    table.add_column("Valor")

    for clave, valor in metadata.items():
        if isinstance(valor, list):
            for i, item in enumerate(valor):
                if i == 0:
                    table.add_row(clave, str(item))
                else:
                    table.add_row("", str(item))
        else:
            table.add_row(clave, str(valor))

    console.print(Panel(table, title=f"Metadata — Norma {id_norma}", border_style="cyan"))


def print_metadata_stats(stats: dict):
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    table.add_column("Métrica", min_width=24)
    table.add_column("Valor", justify="right", style="bold")

    table.add_row("Total entradas", str(stats.get("total_entradas", 0)))
    table.add_row("Normas con metadata", str(stats.get("normas_con_metadata", 0)))

    por_clave = stats.get("por_clave", [])
    if por_clave:
        table.add_section()
        for entry in por_clave:
            table.add_row(f"  {entry['clave']}", str(entry["total"]))

    console.print(Panel(table, title="Estadísticas de Metadata", border_style="cyan"))


def print_metadata_claves(claves: list):
    if not claves:
        console.print("[yellow]No hay claves registradas.[/yellow]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
    table.add_column("N°", style="dim", width=4, justify="right")
    table.add_column("Clave", style="cyan")

    for i, clave in enumerate(claves, 1):
        table.add_row(str(i), clave)

    console.print(f"\n  [bold]{len(claves)}[/bold] clave(s) disponible(s)\n")
    console.print(table)


# ── Mensajes genéricos ────────────────────────────────────────────────────────


def success(msg: str):
    console.print(f"[bold green]✓[/bold green] {msg}")


def error(msg: str):
    console.print(f"[bold red]✗[/bold red] {msg}")


def info(msg: str):
    console.print(f"[dim]{msg}[/dim]")


def warning(msg: str):
    console.print(f"[yellow]⚠[/yellow] {msg}")

