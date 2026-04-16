"""
tui/state.py

Conexión PostgreSQL y managers compartidos para toda la sesión TUI.
Se inicializa una sola vez en BCNApp.on_mount() y se pasa a cada componente
que lo necesite. El SyncModal usa su propia conexión porque corre en un thread.
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg2
from dotenv import load_dotenv

from managers.downloads import DownloadManager
from managers.institutions import InstitutionManager
from managers.metadata import MetadataManager
from managers.norms import NormsManager
from managers.nlp import NLPManager
from managers.norms_types import TiposNormasManager
from managers.schedules import SchedulesManager

load_dotenv()


class AppState:
    """
    Mantiene una conexión PostgreSQL viva durante toda la sesión TUI
    y expone los managers como atributos.

    No usar fuera del hilo principal — el SyncModal crea sus propios managers.
    """

    def __init__(self) -> None:
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432),
            database=os.getenv("POSTGRES_DB", "bcn_normas"),
            user=os.getenv("POSTGRES_USER", "bcn_user"),
            password=os.getenv("POSTGRES_PASSWORD", "bcn_password"),
        )

        self.normas = NormsManager(db_connection=self.conn)
        self.tipos = TiposNormasManager(db_connection=self.conn)
        self.instituciones = InstitutionManager(db_connection=self.conn)
        self.metadata = MetadataManager(db_connection=self.conn)
        self.logger = DownloadManager(db_connection=self.conn)
        self.schedules = SchedulesManager(db_connection=self.conn)
        self.nlp = NLPManager(db_connection=self.conn)

    def close(self) -> None:
        """Cierra la conexión compartida al salir de la app."""
        if self.conn:
            self.conn.close()


def build_sync_managers() -> dict:
    """
    Crea un conjunto de managers con su propia conexión independiente.
    Usar exclusivamente en threads (SyncModal) donde no se puede compartir
    la conexión del hilo principal.
    """
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", 5432),
        database=os.getenv("POSTGRES_DB", "bcn_normas"),
        user=os.getenv("POSTGRES_USER", "bcn_user"),
        password=os.getenv("POSTGRES_PASSWORD", "bcn_password"),
    )

    return {
        "conn": conn,
        "normas": NormsManager(db_connection=conn),
        "tipos": TiposNormasManager(db_connection=conn),
        "metadata": MetadataManager(db_connection=conn),
        "logger": DownloadManager(db_connection=conn),
    }


def check_connection() -> Optional[str]:
    """
    Intenta conectar a la DB. Devuelve None si todo está bien,
    o un string con el error si falla. Usar antes de lanzar la app.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432),
            database=os.getenv("POSTGRES_DB", "bcn_normas"),
            user=os.getenv("POSTGRES_USER", "bcn_user"),
            password=os.getenv("POSTGRES_PASSWORD", "bcn_password"),
        )
        conn.close()
        return None
    except Exception as e:
        return str(e)