"""
Comandos del sistema:
  bcn init
  bcn stats
  bcn cache stats | clear
"""

from pathlib import Path
from typing import Optional

import typer

from cli import output
from cli._internal import require_managers
from cli.console import console

app = typer.Typer(help="Operaciones del sistema")


@app.command("init")
def init_db(
    csv: Optional[Path] = typer.Option(
        None, "--csv", help="Ruta al CSV de instituciones (default: data/instituciones.csv)"
    ),
):
    """Inicializa la base de datos y carga instituciones desde CSV."""
    managers = require_managers()

    csv_path = csv or Path("data/instituciones.csv")

    console.print("\n[bold]Inicializando base de datos...[/bold]")

    if csv_path.exists():
        output.info(f"Cargando instituciones desde {csv_path}")
        try:
            stats = managers["instituciones_loader"].load_from_csv(str(csv_path), mode="append")
            output.success(f"{stats['insertadas']} instituciones cargadas ({stats['total']} en CSV)")
        except Exception as e:
            output.warning(f"No se pudieron cargar instituciones: {e}")
    else:
        output.warning(f"CSV no encontrado en {csv_path} — omitiendo carga de instituciones")

    managers["conn"].close()
    output.success("Base de datos inicializada correctamente\n")


@app.command("stats")
def stats(
    errors: bool = typer.Option(False, "--errors", "-e", help="Mostrar errores recientes"),
):
    """Muestra estadísticas del sistema."""
    managers = require_managers()

    norms_mgr = managers["normas"]
    tipos_mgr = managers["tipos"]
    inst_mgr = managers["instituciones"]
    logger = managers["logger"]

    try:
        norms_stats = norms_mgr.get_stats()
        inst_stats = inst_mgr.get_stats()
        tipos_total = len(tipos_mgr.get_all())
        log_stats = logger.get_stats(days=7)

        output.print_stats(norms_stats, inst_stats, tipos_total, log_stats)

        if errors:
            recent_errors = logger.get_recent(days=7, estado="error", limit=5)
            output.print_recent_errors(recent_errors)

    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


# Cache es un sub-grupo con dos acciones: stats y clear
cache_app = typer.Typer(help="Gestiona el caché local")


@cache_app.command("stats")
def cache_stats():
    """Muestra información sobre el caché local."""
    from bcn_client import BCNClient

    client = BCNClient()
    try:
        stats = client.get_cache_stats()
        output.print_cache_stats(stats)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()


@cache_app.command("clear")
def cache_clear(
    force: bool = typer.Option(False, "--force", "-f", help="No pedir confirmación"),
):
    """Elimina el caché local."""
    from bcn_client import BCNClient

    if not force:
        typer.confirm("¿Eliminar el caché?", abort=True)

    client = BCNClient()
    try:
        client.clear_cache()
        output.success("Caché eliminado correctamente.")
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()