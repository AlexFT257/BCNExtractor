import os
from typing import Dict, List, Optional

import psycopg2


class SchedulesManager:
    """Maneja el registro CRUD de schedules de sync en la base de datos.

    Cada fila representa un job por institución. El campo 'pid' guarda el PID
    del proceso scheduler activo para esa institución — None cuando está detenido.
    """

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
        """Crea la tabla si no existe. Agrega la columna 'pid' si falta (migración aditiva)."""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id          SERIAL PRIMARY KEY,
                inst_id     INTEGER NOT NULL UNIQUE,
                nombre      TEXT NOT NULL,
                hora        INTEGER NOT NULL,
                minuto      INTEGER NOT NULL,
                limite      INTEGER NOT NULL,
                pid         INTEGER,
                status      TEXT DEFAULT 'stopped',
                last_run    TIMESTAMPTZ,
                last_status TEXT,
                last_error  TEXT,
                run_count   INTEGER DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Migración aditiva: agrega pid/status si la tabla ya existía sin ellas
        for column, definition in [("pid", "INTEGER"), ("status", "TEXT DEFAULT 'stopped'")]:
            cursor.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE table_name = '{self.table_name}' AND constraint_name = '{self.table_name}_nombre_key'
                    ) THEN
                        ALTER TABLE {self.table_name} DROP CONSTRAINT {self.table_name}_nombre_key;
                    END IF;
            
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE table_name = '{self.table_name}' AND constraint_name = '{self.table_name}_inst_id_key'
                    ) THEN
                        ALTER TABLE {self.table_name} ADD CONSTRAINT {self.table_name}_inst_id_key UNIQUE (inst_id);
                    END IF;
                END
                $$;
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
        pid: Optional[int] = None,
    ) -> None:
        """Inserta o actualiza la configuración del job para una institución."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            INSERT INTO {self.table_name} (inst_id, nombre, hora, minuto, limite, pid, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'scheduled')
            ON CONFLICT (inst_id) DO UPDATE
            SET nombre = EXCLUDED.nombre,
                hora   = EXCLUDED.hora,
                minuto = EXCLUDED.minuto,
                limite = EXCLUDED.limite,
                pid    = EXCLUDED.pid,
                status = 'scheduled'
            """,
            (inst_id, nombre, hora, minuto, limite, pid),
        )
        self.conn.commit()
        cursor.close()

    def update_status(self, inst_id: int, status: str) -> None:
        """Actualiza únicamente el campo status de un job."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.table_name} SET status = %s WHERE inst_id = %s",
            (status, inst_id),
        )
        self.conn.commit()
        cursor.close()

    def update_run(self, inst_id: int, status: str, error: Optional[str] = None) -> None:
        """Registra el resultado de la última ejecución de un job."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            UPDATE {self.table_name}
            SET last_run    = NOW(),
                last_status = %s,
                last_error  = %s,
                run_count   = run_count + 1,
                status      = %s
            WHERE inst_id = %s
            """,
            (status, error, "scheduled", inst_id),
        )
        self.conn.commit()
        cursor.close()

    def set_pid(self, inst_id: int, pid: int) -> None:
        """Vincula un PID activo al job de la institución."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.table_name} SET pid = %s WHERE inst_id = %s",
            (pid, inst_id),
        )
        self.conn.commit()
        cursor.close()

    def clear_pid(self, inst_id: int) -> None:
        """Limpia el PID del job cuando el proceso termina."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.table_name} SET pid = NULL, status = 'stopped' WHERE inst_id = %s",
            (inst_id,),
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
                   pid, status, last_run, last_status, last_error, run_count, created_at
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
                   pid, status, last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            WHERE id = %s
            """,
            (id_job,),
        )
        row = cursor.fetchone()
        cursor.close()
        return self._row_to_dict(row) if row else None

    def get_by_inst_id(self, inst_id: int) -> Optional[Dict]:
        """Retorna el job de una institución, o None si no existe."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   pid, status, last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            WHERE inst_id = %s
            """,
            (inst_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return self._row_to_dict(row) if row else None

    def get_running(self) -> List[Dict]:
        """Retorna todos los jobs con status 'running' o 'scheduled' (proceso activo)."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   pid, status, last_run, last_status, last_error, run_count, created_at
            FROM {self.table_name}
            WHERE pid IS NOT NULL
            ORDER BY created_at DESC
            """,
        )
        rows = cursor.fetchall()
        cursor.close()
        return [self._row_to_dict(row) for row in rows]

    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, inst_id, nombre, hora, minuto, limite,
                   pid, status, last_run, last_status, last_error, run_count, created_at
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
            "pid":         row[6],
            "status":      row[7],
            "last_run":    row[8],
            "last_status": row[9],
            "last_error":  row[10],
            "run_count":   row[11],
            "created_at":  row[12],
        }