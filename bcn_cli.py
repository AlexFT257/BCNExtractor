from typing import Annotated

import typer

from cli._internal import configure_logging
from cli.commands import institutions, norms, system, schedules


def main_callback(
    debug: Annotated[
        bool, typer.Option("--debug", help="Mostrar logs internos")
    ] = False,
):
    configure_logging(debug)


app = typer.Typer(
    callback=main_callback,
    name="bcn",
    help="Herramienta para extraer y gestionar normas legales de la BCN.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # Los comandos manejan sus propios errores
)

# Grupos de comandos
app.add_typer(norms.app, name="normas")
app.add_typer(institutions.app, name="instituciones")
app.add_typer(schedules.app, name="scheduler")

# Comandos de sistema directamente en raíz
app.add_typer(system.app, name="sistema")

# Init y stats van en raíz también para compatibilidad
app.command("init")(system.init_db)
app.command("stats")(system.stats)

# Cache como sub-grupo
app.add_typer(system.cache_app, name="cache")


def main():
    app()


if __name__ == "__main__":
    main()
