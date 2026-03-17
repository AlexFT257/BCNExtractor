import os
import sys

import logging
import psycopg2
from dotenv import load_dotenv

from cli.output import error


def configure_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s")


def create_connection():
    load_dotenv()
    return psycopg2.connect(
        host="localhost",
        port=os.getenv("POSTGRES_PORT", 5432),
        database=os.getenv("POSTGRES_DB", "bcn_normas"),
        user=os.getenv("POSTGRES_USER", "bcn_user"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )


def init_managers():
    """
    Crea una única conexión y retorna todos los managers.
    Si falla, imprime el error y retorna None.
    """
    from loaders.institutions import InstitutionLoader
    from managers.downloads import DownloadManager
    from managers.institutions import InstitutionManager
    from managers.norms import NormsManager
    from managers.norms_types import TiposNormasManager

    try:
        conn = create_connection()
        return {
            "conn": conn,
            "instituciones": InstitutionManager(db_connection=conn),
            "instituciones_loader": InstitutionLoader(db_connection=conn),
            "tipos": TiposNormasManager(db_connection=conn),
            "normas": NormsManager(db_connection=conn),
            "logger": DownloadManager(db_connection=conn),
        }
    except Exception as e:
        error(f"No se pudo conectar a la base de datos: {e}")
        return None


def require_managers(ctx_obj: dict | None = None):
    """
    Obtiene managers desde el contexto de Typer o crea uno nuevo.
    Llama a sys.exit(1) si la conexión falla, para abortar el comando limpiamente.
    """
    managers = ctx_obj if ctx_obj else init_managers()
    if not managers:
        sys.exit(1)
    return managers