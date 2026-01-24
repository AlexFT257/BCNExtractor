import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_batch

load_dotenv()


class InstitutionLoader:
    """Clase que se encarga de cargar las instituciones desde un archivo CSV"""

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

    def load_from_csv(self, csv_path: str, mode: str = "append") -> Dict:
        """
        mode:
            - update: Actualiza datos existentes, agregando nuevas
            - replace: Borra todas y carga de cero
            - append: Agrega nuevas instituciones ignorando existentes
        """

        csv_file = Path(csv_path)

        if not csv_file.exists():
            raise FileNotFoundError(f"El archivo {csv_file} no existe")

        print(f"\nCargando datos desde {csv_file}")
        print(f"    Modo: {mode}")

        instituciones = self._read_csv(csv_file)

        if not instituciones:
            print("No hay datos para cargar")
            return {"total": 0, "insertadas": 0, "actualizadas": 0, "errores": 0}

        print(f"    Instituciones en CSV: {len(instituciones)}")

        self.ensure_institution_table()

        if mode == "replace":
            stats = self._replace_all(instituciones)
        elif mode == "update":
            stats = self._update_or_insert(instituciones)
        elif mode == "append":
            stats = self._append_only(instituciones)
        else:
            raise ValueError(f"Modo no válido: {mode}")

        return stats

    def _read_csv(self, csv_file: Path) -> List[Dict]:
        instituciones = []

        with open(csv_file, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # limpiar espacios
                row = {k.strip(): v.strip() for k, v in row.items()}

                try:
                    inst = {"id": int(row["id"]), "nombre": row["institucion"]}

                    instituciones.append(inst)
                except ValueError as e:
                    print(f"Error al leer fila: {row}. Error: {e}")
                    continue

        return instituciones

    def _replace_all(self, instituciones: List[Dict]):
        cursor = self.conn.cursor()
        stats = {
            "total": len(instituciones),
            "insertadas": 0,
            "actualizadas": 0,
            "errores": 0,
        }

        try:
            cursor.execute(f"DELETE FROM {self.table_name}")
            print("    Instituciones anteriores eliminadas")

            insert_query = f"""
                INSERT INTO {self.table_name} (id, nombre, fecha_agregada)
                VALUES (%s, %s, NOW())
            """

            data = [(inst["id"], inst["nombre"]) for inst in instituciones]

            execute_batch(cursor, insert_query, data)
            stats["insertadas"] = len(instituciones)

            self.conn.commit()
            print(f"    {stats['insertadas']} instituciones insertadas")
        except Exception as e:
            print(f"    Error al insertar instituciones: {e}")
            stats["errores"] = len(instituciones)
        finally:
            cursor.close()

        return stats

    def _update_or_insert(self, instituciones: List[Dict]) -> Dict:
        cursor = self.conn.cursor()
        stats = {
            "total": len(instituciones),
            "insertadas": 0,
            "actualizadas": 0,
            "errores": 0,
        }

        upsert_query = f"""
            INSERT INTO {self.table_name} (id, nombre, fecha_agregada)
            VALUES (%s, %s, %s)
            ON CONFLICT (id)
            DO UPDATE SET
                nombre = EXCLUDED.nombre,
                fecha_actualizada = CURRENT_TIMESTAMP
        """

        try:
            # Obtener IDs existentes
            cursor.execute(f"SELECT id FROM {self.table_name}")
            existing_ids = {row[0] for row in cursor.fetchall()}

            data = [
                (inst["id"], inst["nombre"], datetime.now())
                for inst in instituciones
            ]

            execute_batch(cursor, upsert_query, data)

            # Calcular estadísticas
            new_ids = {inst["id"] for inst in instituciones}
            stats["insertadas"] = len(new_ids - existing_ids)
            stats["actualizadas"] = len(new_ids & existing_ids)

            self.conn.commit()
            print(f"    {stats['insertadas']} instituciones nuevas insertadas")
            print(f"    {stats['actualizadas']} instituciones actualizadas")

        except Exception as e:
            self.conn.rollback()
            print(f"    Error al actualizar o insertar instituciones: {e}")
            stats["errores"] = len(instituciones)

        finally:
            cursor.close()

        return stats

    def _append_only(self, instituciones: List[Dict]) -> Dict:
        cursor = self.conn.cursor()
        stats = {"total": len(instituciones), "insertadas": 0, "errores": 0}

        insert_query = f"""
            INSERT INTO {self.table_name} (id, nombre, fecha_agregada)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """

        try:
            data = [
                (inst["id"], inst["nombre"], datetime.now())
                for inst in instituciones
            ]

            execute_batch(cursor, insert_query, data)
            stats["insertadas"] = cursor.rowcount

            self.conn.commit()
            print(f"    {stats['insertadas']} instituciones nuevas insertadas")
            print(
                f"    {stats['total'] - stats['insertadas']} instituciones ya existentes (ignoradas)"
            )

        except Exception as e:
            self.conn.rollback()
            print(f"    Error al insertar nuevas instituciones: {e}")
            stats["errores"] = len(instituciones)

        finally:
            cursor.close()

        return stats

    def close(self):
        if self.own_connection and self.conn:
            self.conn.close()
            print("Conexion cerrada")
