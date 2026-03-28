"""
Comandos relacionados con metadata de normas:
  bcn metadata claves
  bcn metadata stats
  bcn normas metadata <id>
  bcn normas by-metadata <clave> <valor>
"""

from typing import Optional

import typer

from cli import output
from cli._internal import require_managers
from cli.console import console

app = typer.Typer(help="Gestión de metadata de normas")


@app.command("claves")
def claves():
    """Lista todas las claves de metadata registradas en la base de datos."""
    managers = require_managers()
    meta_mgr = managers["metadata"]

    try:
        claves = meta_mgr.get_claves_disponibles()
        output.print_metadata_claves(claves)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()


@app.command("stats")
def stats():
    """Muestra estadísticas de la tabla de metadata."""
    managers = require_managers()
    meta_mgr = managers["metadata"]

    try:
        stats = meta_mgr.get_stats()
        output.print_metadata_stats(stats)
    except Exception as e:
        output.error(str(e))
        raise typer.Exit(1)
    finally:
        managers["conn"].close()