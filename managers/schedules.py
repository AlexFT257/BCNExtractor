# managers/schedules.py
import os
from typing import Dict, List, Optional

import psycopg2


class SchedulesManager:
    """Maneja el registro CRUD de schedules de sync en la base de datos."""

    table_name = "scheduler_jobs"

    def __init__(self, db_connection=None) -> None:
        self.conn = db_connection
        self.own_connection = False

        if not self.conn:
            self.conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=os.getenv("POSTGRES_PORT", 5432),
                database=os.getenv("POSTGRES_DB", "bcn_normas"),
                user=os.getenv("POSTGRES_USER", "bcn_user"),
                password=os.getenv("POSTGRES_PASSWORD", "bcn_password"),
            )
            self.own_connection = True

        self.ensure_scheduler_jobs_table()

    def ensure_scheduler_jobs_table(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id          SERIAL PRIMARY KEY,
                inst_id     INTEGER NOT NULL,
                nombre      TEXT NOT NULL UNIQUE,
                hora        INTEGER NOT NULL,
                minuto      INTEGER NOT NULL,
                limite      INTEGER NOT NULL,
                last_run    TIMESTAMPTZ,
                last_status TEXT,
                last_error  TEXT,
                run_count   INTEGER DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        self.conn.commit()
        cursor.close()

    def upsert_job(
        self,
        inst_id: int,
        nombre: str,
        hora: int,
        minuto: int,
        limite: int,
    ) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            INSERT INTO {self.table_name} (inst_id, nombre, hora, minuto, limite)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (nombre) DO UPDATE
            SET hora = EXCLUDED.hora, minuto = EXCLUDED.minuto, limite = EXCLUDED.limite
        """,
            (inst_id, nombre, hora, minuto, limite),
        )
        self.conn.commit()
        cursor.close()

    def update_run(self, nombre: str, status: str, error: Optional[str] = None) -> None:
        """Actualiza el resultado de la última ejecución de un job identificado por nombre."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            UPDATE {self.table_name}
            SET last_run = NOW(), last_status = %s, last_error = %s, run_count = run_count + 1
            WHERE nombre = %s
        """,
            (status, error, nombre),
        )
        self.conn.commit()
        cursor.close()

    def remove_job(self, id_job: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            f"DELETE FROM {self.table_name} WHERE id = %s",
            (id_job,),
        )
        self.conn.commit()
        cursor.close()

    def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            (limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [self._row_to_dict(row) for row in rows]

    def get_by_id(self, id_job: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            WHERE id = %s
        """,
            (id_job,),
        )
        row = cursor.fetchone()
        cursor.close()
        return self._row_to_dict(row) if row else None

    def get_by_inst_id(self, inst_id: int, limit: int = 20, offset: int = 0) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            WHERE inst_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            (inst_id, limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [self._row_to_dict(row) for row in rows]

    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            WHERE nombre ILIKE %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            (f"%{query}%", limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [self._row_to_dict(row) for row in rows]

    def close(self) -> None:
        if self.own_connection and self.conn:
            self.conn.close()

    def _row_to_dict(self, row: tuple) -> Dict:
        return {
            "id":          row[0],
            "inst_id":     row[1],
            "nombre":      row[2],
            "hora":        row[3],
            "minuto":      row[4],
            "limite":      row[5],
            "last_run":    row[6],
            "last_status": row[7],
            "last_error":  row[8],
            "run_count":   row[9],
            "created_at":  row[10],
        }