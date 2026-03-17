"""
Comandos de instituciones:
  bcn instituciones list [--search <texto>] [--limit <n>]
  bcn instituciones get <id>
  bcn instituciones load <csv> [--mode update|append|replace]
"""

from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from cli import output
from cli._internal import require_managers
from cli.console import console

app = typer.Typer(help="Gestión de instituciones")


@app.command("list")
def list_instituciones(
    search: Optional[str] = typer.Option(
        None, "--search", "-s", help="Filtrar por nombre"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n", help="Máximo de resultados"
    ),
):
    """Lista instituciones en la base de datos."""
    managers = require_managers()
    inst_mgr = managers["instituciones"]

    try:
        if search:
            instituciones = inst_mgr.search(search)
            console.print(f"\n  Resultados para [bold]'{search}'[/bold]")
        else:
            instituciones = inst_mgr.get_all()
            console.print("\n  Todas las instituciones")

        if not instituciones:
            output.warning("No se encontraron instituciones.")
            raise typer.Exit(0)

        if limit:
            instituciones = instituciones[:limit]

        table = Table(box=box.SIMPLE_HEAD, show_edge=False, header_style="bold cyan")
        table.add_column("ID", style="cyan", width=8, justify="right")
        table.add_column("Nombre")

        for inst in instituciones:
            table.add_row(str(inst.id), inst.nombre)

        console.print(f"  [dim]{len(instituciones)} institución(es)[/dim]\n")
        console.print(table)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("get")
def get_institucion(
    id: int = typer.Argument(..., help="ID de la institución"),
):
    """Muestra el detalle de una institución."""
    managers = require_managers()
    inst_mgr = managers["instituciones"]

    try:
        inst = inst_mgr.get_by_id(id)

        if not inst:
            output.error(f"Institución {id} no encontrada.")
            raise typer.Exit(1)

        table = Table(box=box.SIMPLE_HEAD, show_edge=False, show_header=False)
        table.add_column("Campo", style="dim", width=12)
        table.add_column("Valor", style="bold")
        table.add_row("ID", str(inst.id))
        table.add_row("Nombre", inst.nombre)

        console.print(Panel(table, title=f"Institución {inst.id}", border_style="cyan"))

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("load")
def load_instituciones(
    csv_path: Path = typer.Argument(..., help="Ruta al CSV de instituciones"),
    mode: str = typer.Option(
        "update",
        "--mode",
        "-m",
        help="Modo de carga: update | append | replace",
    ),
):
    """Carga instituciones desde un archivo CSV."""
    managers = require_managers()
    loader = managers["instituciones_loader"]

    try:
        if not csv_path.exists():
            output.error(f"Archivo no encontrado: {csv_path}")
            raise typer.Exit(1)

        output.info(f"Cargando desde {csv_path} (modo: {mode})...")
        stats = loader.load_from_csv(str(csv_path), mode=mode)

        # Soporte para ambas variantes de claves que puede devolver el loader
        insertadas = stats.get("insertadas") or stats.get("success", 0)
        errores = stats.get("errores") or stats.get("errors", 0)
        total = stats.get("total", 0)

        output.success(f"{insertadas} instituciones cargadas de {total}")
        if errores:
            output.warning(f"{errores} institución(es) con error")

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()
