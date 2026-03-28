import os
from typing import Dict, List

import psycopg2
from dotenv import load_dotenv

load_dotenv()


class MetadataManager:
    """Gestiona el CRUD de metadata de normas en la tabla EAV normas_metadata."""

    table_name = "normas_metadata"

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

        self.ensure_metadata_table()

    def ensure_metadata_table(self) -> None:
        """Crea la tabla EAV de metadata si no existe."""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id          SERIAL PRIMARY KEY,
                id_norma    INTEGER NOT NULL REFERENCES normas(id) ON DELETE CASCADE,
                clave       VARCHAR(100) NOT NULL,
                valor       TEXT NOT NULL,
                tipo_valor  VARCHAR(20) DEFAULT 'string'
            );

            CREATE INDEX IF NOT EXISTS idx_meta_norma
                ON {self.table_name}(id_norma);
            CREATE INDEX IF NOT EXISTS idx_meta_clave
                ON {self.table_name}(clave);
            CREATE INDEX IF NOT EXISTS idx_meta_kv
                ON {self.table_name}(clave, valor);
        """)
        self.conn.commit()
        cursor.close()

    def save(self, cursor, id_norma: int, parsed_data: Dict) -> None:
        """Reemplaza toda la metadata de una norma dentro de una transacción existente.

        Recibe el cursor del llamador para participar en su transacción.
        """
        cursor.execute(
            f"DELETE FROM {self.table_name} WHERE id_norma = %s",
            (id_norma,),
        )

        entries = []

        for materia in parsed_data.get("materias", []):
            entries.append((id_norma, "materia", str(materia), "string"))

        for organismo in parsed_data.get("organismos", []):
            entries.append((id_norma, "organismo", str(organismo), "string"))

        if parsed_data.get("derogado") is not None:
            entries.append(
                (id_norma, "derogado", str(parsed_data["derogado"]).lower(), "boolean")
            )

        if parsed_data.get("es_tratado") is not None:
            entries.append(
                (
                    id_norma,
                    "es_tratado",
                    str(parsed_data["es_tratado"]).lower(),
                    "boolean",
                )
            )

        if not entries:
            return

        cursor.executemany(
            f"""
            INSERT INTO {self.table_name} (id_norma, clave, valor, tipo_valor)
            VALUES (%s, %s, %s, %s)
            """,
            entries,
        )

    def get_by_norma(self, id_norma: int) -> Dict:
        """Devuelve toda la metadata de una norma como dict reconstruido."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT clave, valor, tipo_valor
            FROM {self.table_name}
            WHERE id_norma = %s
            """,
            (id_norma,),
        )
        rows = cursor.fetchall()
        cursor.close()

        return self._rows_to_dict(rows)

    def get_by_norma_clave(self, id_norma: int, clave: str) -> List[str]:
        """Devuelve los valores de una clave específica para una norma."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT valor
            FROM {self.table_name}
            WHERE id_norma = %s AND clave = %s
            """,
            (id_norma, clave),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [row[0] for row in rows]

    def get_normas_by_clave_valor(
        self, clave: str, valor: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        """Devuelve normas (con datos básicos) que tengan una clave/valor de metadata."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT n.id, tn.nombre, n.numero, n.titulo, n.estado, n.fecha_publicacion
            FROM normas n
            LEFT JOIN tipos_normas tn ON n.id_tipo = tn.id
            JOIN {self.table_name} m ON n.id = m.id_norma
            WHERE m.clave = %s AND m.valor ILIKE %s
            LIMIT %s OFFSET %s
            """,
            (clave, f"%{valor}%", limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "norma_id": row[0],
                "tipo_nombre": row[1] or "—",
                "numero": row[2] or "—",
                "titulo": row[3] or "",
                "estado": row[4] or "vigente",
                "fecha_publicacion": row[5],
            }
            for row in rows
        ]

    def get_claves_disponibles(self) -> List[str]:
        """Devuelve todas las claves únicas registradas en la tabla."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT DISTINCT clave FROM {self.table_name} ORDER BY clave")
        rows = cursor.fetchall()
        cursor.close()

        return [row[0] for row in rows]

    def get_stats(self) -> Dict:
        """Estadísticas de la tabla de metadata."""
        cursor = self.conn.cursor()
        stats = {}

        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        stats["total_entradas"] = cursor.fetchone()[0]

        cursor.execute(f"SELECT COUNT(DISTINCT id_norma) FROM {self.table_name}")
        stats["normas_con_metadata"] = cursor.fetchone()[0]

        cursor.execute(
            f"""
            SELECT clave, COUNT(*) as total
            FROM {self.table_name}
            GROUP BY clave
            ORDER BY total DESC
            """
        )
        stats["por_clave"] = [
            {"clave": row[0], "total": row[1]} for row in cursor.fetchall()
        ]

        cursor.close()
        return stats

    def _rows_to_dict(self, rows: list) -> Dict:
        """Convierte filas (clave, valor, tipo_valor) en un dict tipado."""
        result: Dict = {}
        for clave, valor, tipo_valor in rows:
            parsed_valor: object = valor == "true" if tipo_valor == "boolean" else valor

            if clave in ("materia", "organismo"):
                result.setdefault(f"{clave}s", []).append(parsed_valor)
            else:
                result[clave] = parsed_valor

        return result

    def close(self) -> None:
        if self.own_connection and self.conn:
            self.conn.close()
