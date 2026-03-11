import os
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

from utils.institution_types import Institution

load_dotenv()


class InstitutionManager:
    """Clase que se encarga de manejar las instituciones de la base de datos"""

    table_name = "instituciones"

    def __init__(self, db_connection=None) -> None:
        self.conn = db_connection
        self.own_connection = False

        if not self.conn:
            self.conn = psycopg2.connect(
                host="localhost",
                port=os.getenv("POSTGRES_PORT", 5432),
                database=os.getenv("POSTGRES_DB", "bcn_normas"),
                user=os.getenv("POSTGRES_USER", "bcn_user"),
                password=os.getenv("POSTGRES_PASSWORD", "changeme"),
            )
            self.own_connection = True
        
        self.ensure_institution_table()
            
    
    def ensure_institution_table(self) -> None:
        cursor = self.conn.cursor()

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                fecha_agregada TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_instituciones_nombre
                ON {self.table_name}(nombre);
        """)

        self.conn.commit()
        cursor.close()
        print(f"Tabla {self.table_name} creada/validada")

    def get_all(self) -> List[Institution]:
        cursor = self.conn.cursor()

        cursor.execute(f"""
            SELECT id, nombre, fecha_agregada, fecha_actualizada
            FROM {self.table_name}
            ORDER BY nombre
        """)

        instituciones = [
            Institution(
                id=row[0],
                nombre=row[1],
                fecha_agregada=row[2],
                fecha_actualizada=row[3],
            )
            for row in cursor.fetchall()
        ]

        cursor.close()
        return instituciones

    def get_by_id(self, id: int) -> Optional[Institution]:
        cursor = self.conn.cursor()

        cursor.execute(
            f"""
            SELECT id, nombre, fecha_agregada, fecha_actualizada
            FROM {self.table_name}
            WHERE id = %s
        """,
            (id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if row:
            return Institution(
                id=row[0],
                nombre=row[1],
                fecha_agregada=row[2],
                fecha_actualizada=row[3],
            )
        else:
            return None

    def search(self, query: str) -> List[Institution]:
        cursor = self.conn.cursor()

        cursor.execute(
            f"""
            SELECT id, nombre, fecha_agregada, fecha_actualizada
            FROM {self.table_name}
            WHERE nombre ILIKE %s
            ORDER BY nombre
        """,
            (f"%{query}%",),
        )

        instituciones = [
            Institution(
                id=row[0],
                nombre=row[1],
                fecha_agregada=row[2],
                fecha_actualizada=row[3],
            )
            for row in cursor.fetchall()
        ]

        cursor.close()
        return instituciones

    def get_stats(self) -> Dict:
        """Estadísticas básicas de instituciones."""
        cursor = self.conn.cursor()
        stats = {}

        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        stats["total"] = cursor.fetchone()[0]

        # Instituciones que tienen al menos una norma asociada
        cursor.execute(f"""
            SELECT COUNT(DISTINCT id_institucion)
            FROM normas_instituciones
        """)
        stats["con_normas"] = cursor.fetchone()[0]
        stats["sin_normas"] = stats["total"] - stats["con_normas"]

        cursor.close()
        return stats

    def close(self):
        if self.own_connection and self.conn:
            self.conn.close()
            print("Conexion cerrada")
