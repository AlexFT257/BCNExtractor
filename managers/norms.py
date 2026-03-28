import hashlib
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

import psycopg2
from dotenv import load_dotenv

from managers.metadata import MetadataManager

load_dotenv()


class NormsManager:
    """Gestiona el CRUD de normas en PostgreSQL, incluyendo versionado histórico."""

    table_name = "normas"
    versions_table = "normas_versiones"

    def __init__(
        self,
        xml_dir: str = "data/xml",
        md_dir: str = "data/md",
        db_connection=None,
    ) -> None:
        self.xml_dir = Path(xml_dir)
        self.xml_dir.mkdir(parents=True, exist_ok=True)

        self.md_dir = Path(md_dir)
        self.md_dir.mkdir(parents=True, exist_ok=True)

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

        self._ensure_normas_table()
        self._ensure_versiones_table()

        # MetadataManager comparte la misma conexión para participar en las mismas transacciones
        self.metadata = MetadataManager(db_connection=self.conn)

    def _ensure_normas_table(self) -> None:
        """Crea la tabla principal de normas y la tabla de relación con instituciones."""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id                  INTEGER PRIMARY KEY,
                id_tipo             INTEGER REFERENCES tipos_normas(id),
                numero              VARCHAR(50),
                titulo              TEXT,
                estado              VARCHAR(20) DEFAULT 'vigente',
                fecha_publicacion   DATE,
                fecha_promulgacion  DATE,
                organismo           TEXT,
                xml_path            TEXT,
                md_path             TEXT,
                contenido_texto     TEXT,
                hash_xml            VARCHAR(32),
                version_actual      INTEGER DEFAULT 1,
                fecha_descarga      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_normas_tipo
                ON {self.table_name}(id_tipo);
            CREATE INDEX IF NOT EXISTS idx_normas_estado
                ON {self.table_name}(estado);
            CREATE INDEX IF NOT EXISTS idx_normas_titulo
                ON {self.table_name} USING gin(to_tsvector('spanish', titulo));

            CREATE TABLE IF NOT EXISTS normas_instituciones (
                id_norma         INTEGER REFERENCES {self.table_name}(id),
                id_institucion   INTEGER REFERENCES instituciones(id),
                fecha_asociacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id_norma, id_institucion)
            );
        """)
        self.conn.commit()
        cursor.close()

    def _ensure_versiones_table(self) -> None:
        """Crea la tabla de versiones históricas si no existe."""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.versions_table} (
                id           SERIAL PRIMARY KEY,
                id_norma     INTEGER NOT NULL REFERENCES {self.table_name}(id),
                version_num  INTEGER NOT NULL,
                hash_xml     VARCHAR(32) NOT NULL,
                xml_path     TEXT,
                md_path      TEXT,
                titulo       TEXT,
                estado       VARCHAR(20),
                detectado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (id_norma, version_num)
            );

            CREATE INDEX IF NOT EXISTS idx_versiones_norma
                ON {self.versions_table}(id_norma);
        """)
        self.conn.commit()
        cursor.close()

    def _archive_version(
        self, cursor, id_norma: int, version_num: int, row: tuple
    ) -> None:
        """Archiva el estado actual de una norma antes de sobreescribirla.

        row debe ser (hash_xml, xml_path, md_path, titulo, estado).
        """
        hash_xml, xml_path, md_path, titulo, estado = row

        versioned_xml_path = None
        if xml_path:
            src = Path(xml_path)
            if src.exists():
                dst = src.parent / f"{id_norma}_v{version_num}{src.suffix}"
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                versioned_xml_path = str(dst)

        versioned_md_path = None
        if md_path:
            src = Path(md_path)
            if src.exists():
                dst = src.parent / f"{id_norma}_v{version_num}{src.suffix}"
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                versioned_md_path = str(dst)

        cursor.execute(
            f"""
            INSERT INTO {self.versions_table}
                (id_norma, version_num, hash_xml, xml_path, md_path, titulo, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_norma, version_num) DO NOTHING
            """,
            (
                id_norma,
                version_num,
                hash_xml,
                versioned_xml_path,
                versioned_md_path,
                titulo,
                estado,
            ),
        )

    def save(
        self,
        id_norma: int,
        xml_content: str,
        parsed_data: Dict,
        id_tipo: Optional[int] = None,
        id_institucion: Optional[int] = None,
        markdown: Optional[str] = None,
        force: bool = False,
    ) -> str:
        """
        Guarda o actualiza una norma, archivando la versión anterior si hubo cambios.

        Returns: 'nueva' | 'actualizada' | 'sin_cambios'
        """
        hash_xml = hashlib.md5(xml_content.encode()).hexdigest()

        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT hash_xml, xml_path, md_path, titulo, estado, version_actual
            FROM {self.table_name}
            WHERE id = %s
            """,
            (id_norma,),
        )
        existing = cursor.fetchone()

        if existing and existing[0] == hash_xml and not force:
            cursor.close()
            return "sin_cambios"

        xml_path = self.xml_dir / f"{id_norma}.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        md_path = None
        if markdown:
            md_path = self.md_dir / f"{id_norma}.md"
            md_path.write_text(markdown, encoding="utf-8")

        if existing:
            prev_hash, prev_xml, prev_md, prev_titulo, prev_estado, version_actual = (
                existing
            )
            self._archive_version(
                cursor,
                id_norma,
                version_actual,
                (prev_hash, prev_xml, prev_md, prev_titulo, prev_estado),
            )
            next_version = version_actual + 1
        else:
            next_version = 1

        cursor.execute(
            f"""
            INSERT INTO {self.table_name} (
                id, id_tipo, numero, titulo, estado,
                fecha_publicacion, fecha_promulgacion, organismo,
                xml_path, md_path, contenido_texto,
                hash_xml, version_actual, fecha_descarga, fecha_actualizacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                id_tipo             = EXCLUDED.id_tipo,
                numero              = EXCLUDED.numero,
                titulo              = EXCLUDED.titulo,
                estado              = EXCLUDED.estado,
                fecha_publicacion   = EXCLUDED.fecha_publicacion,
                fecha_promulgacion  = EXCLUDED.fecha_promulgacion,
                organismo           = EXCLUDED.organismo,
                xml_path            = EXCLUDED.xml_path,
                md_path             = EXCLUDED.md_path,
                contenido_texto     = EXCLUDED.contenido_texto,
                hash_xml            = EXCLUDED.hash_xml,
                version_actual      = EXCLUDED.version_actual,
                fecha_actualizacion = CURRENT_TIMESTAMP
            """,
            (
                id_norma,
                id_tipo,
                parsed_data.get("numero"),
                parsed_data.get("titulo"),
                parsed_data.get("estado", "vigente"),
                parsed_data.get("fecha_publicacion"),
                parsed_data.get("fecha_promulgacion"),
                parsed_data.get("organismo"),
                str(xml_path),
                str(md_path) if md_path else None,
                parsed_data.get("contenido_texto"),
                hash_xml,
                next_version,
                datetime.now(),
                datetime.now(),
            ),
        )

        # Delegar metadata al MetadataManager compartiendo el cursor de esta transacción
        self.metadata.save(cursor, id_norma, parsed_data)

        if id_institucion:
            cursor.execute(
                """
                INSERT INTO normas_instituciones (id_norma, id_institucion)
                VALUES (%s, %s)
                ON CONFLICT (id_norma, id_institucion) DO NOTHING
                """,
                (id_norma, id_institucion),
            )

        self.conn.commit()
        cursor.close()

        return "actualizada" if existing else "nueva"

    def get_by_id(self, id_norma: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT n.id, tn.nombre, n.numero, n.titulo, n.estado,
                   n.fecha_publicacion, n.fecha_promulgacion, n.organismo,
                   n.xml_path, n.md_path, n.version_actual
            FROM {self.table_name} n
            LEFT JOIN tipos_normas tn ON n.id_tipo = tn.id
            WHERE n.id = %s
            """,
            (id_norma,),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return None

        cursor.execute(
            """
            SELECT i.nombre FROM instituciones i
            JOIN normas_instituciones ni ON i.id = ni.id_institucion
            WHERE ni.id_norma = %s
            """,
            (id_norma,),
        )
        instituciones = [r[0] for r in cursor.fetchall()]
        cursor.close()

        metadata = self.metadata.get_by_norma(id_norma)

        return {
            "id": row[0],
            "tipo_nombre": row[1],
            "numero": row[2],
            "titulo": row[3],
            "estado": row[4],
            "fecha_publicacion": row[5],
            "fecha_promulgacion": row[6],
            "organismo": row[7],
            "xml_path": row[8],
            "md_path": row[9],
            "version_actual": row[10],
            "metadata": metadata,
            "materias": metadata.get("materias", []),
            "instituciones": instituciones,
        }

    def get_by_institucion(
        self, id_institucion: int, limit: int = 500, offset: int = 0
    ) -> List[Dict]:
        """Devuelve todas las normas asociadas a una institución."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT n.id, tn.nombre, n.numero, n.titulo,
                   n.fecha_publicacion, n.estado, n.md_path
            FROM {self.table_name} n
            LEFT JOIN tipos_normas tn ON n.id_tipo = tn.id
            JOIN normas_instituciones ni ON n.id = ni.id_norma
            WHERE ni.id_institucion = %s
            ORDER BY n.fecha_publicacion DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (id_institucion, limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "id": row[0],
                "tipo_nombre": row[1] or "—",
                "numero": row[2] or "—",
                "titulo": row[3] or "",
                "fecha_publicacion": row[4],
                "estado": row[5] or "vigente",
                "md_path": row[6],
            }
            for row in rows
        ]

    def get_by_range_date(
        self,
        start_date: date,
        end_date: date = date.today(),
        date_type: Literal["pub", "prom"] = "pub",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        if not start_date:
            raise ValueError("start_date must be provided")
        if date_type not in ("pub", "prom"):
            raise ValueError("date_type must be 'pub' or 'prom'")

        date_column = (
            "fecha_publicacion" if date_type == "pub" else "fecha_promulgacion"
        )

        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, id_tipo, numero, titulo, estado,
                   fecha_publicacion, fecha_promulgacion
            FROM {self.table_name}
            WHERE {date_column} BETWEEN %s AND %s
            LIMIT %s OFFSET %s
            """,
            (start_date, end_date, limit, offset),
        )
        rows = cursor.fetchall()

        norms = [
            {
                "norma_id": row[0],
                "tipo_id": row[1],
                "numero": row[2],
                "titulo": row[3],
                "estado": row[4],
                "fecha_publicacion": row[5],
                "fecha_promulgacion": row[6],
            }
            for row in rows
        ]

        if norms:
            cursor.execute("SELECT id, nombre FROM tipos_normas")
            types = {row[0]: row[1] for row in cursor.fetchall()}
            for result in norms:
                result["tipo_nombre"] = types.get(result["tipo_id"], "—")

        cursor.close()
        return norms

    def get_by_status(
        self, status: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, id_tipo, numero, titulo, estado, fecha_publicacion
            FROM {self.table_name}
            WHERE estado = %s
            LIMIT %s OFFSET %s
            """,
            (status, limit, offset),
        )
        rows = cursor.fetchall()

        norms = [
            {
                "norma_id": row[0],
                "tipo_id": row[1],
                "numero": row[2],
                "titulo": row[3],
                "estado": row[4],
                "fecha_publicacion": row[5],
            }
            for row in rows
        ]

        if norms:
            cursor.execute("SELECT id, nombre FROM tipos_normas")
            types = {row[0]: row[1] for row in cursor.fetchall()}
            for result in norms:
                result["tipo_nombre"] = types.get(result["tipo_id"], "—")

        cursor.close()
        return norms

    def get_by_type(self, type: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT id FROM tipos_normas WHERE nombre ILIKE %s OR abreviatura ILIKE %s",
            (f"%{type}%", f"%{type}%"),
        )
        type_ids = [row[0] for row in cursor.fetchall()]
        if not type_ids:
            cursor.close()
            return []

        cursor.execute(
            f"""
            SELECT id, id_tipo, numero, titulo, estado, fecha_publicacion
            FROM {self.table_name}
            WHERE id_tipo IN %s
            LIMIT %s OFFSET %s
            """,
            (tuple(type_ids), limit, offset),
        )
        rows = cursor.fetchall()

        norms = [
            {
                "norma_id": row[0],
                "tipo_id": row[1],
                "numero": row[2],
                "titulo": row[3],
                "estado": row[4],
                "fecha_publicacion": row[5],
            }
            for row in rows
        ]

        if norms:
            cursor.execute("SELECT id, nombre FROM tipos_normas")
            types = {row[0]: row[1] for row in cursor.fetchall()}
            for result in norms:
                result["tipo_nombre"] = types.get(result["tipo_id"], "—")

        cursor.close()
        return norms

    def search(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Búsqueda full-text en normas."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, id_tipo, titulo, numero, estado, fecha_publicacion
            FROM {self.table_name}
            WHERE to_tsvector('spanish', titulo) @@ plainto_tsquery('spanish', %s)
               OR titulo ILIKE %s
            ORDER BY fecha_publicacion DESC
            LIMIT %s OFFSET %s
            """,
            (query, f"%{query}%", limit, offset),
        )

        results = [
            {
                "norma_id": row[0],
                "tipo_id": row[1],
                "titulo": row[2],
                "numero": row[3],
                "estado": row[4],
                "fecha_publicacion": row[5],
            }
            for row in cursor.fetchall()
        ]

        if results:
            cursor.execute("SELECT id, nombre FROM tipos_normas")
            types = {row[0]: row[1] for row in cursor.fetchall()}
            for result in results:
                result["tipo_nombre"] = types.get(result["tipo_id"], "—")

        cursor.close()
        return results

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT id, id_tipo, numero, titulo, estado, fecha_publicacion
            FROM {self.table_name}
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()

        norms = [
            {
                "norma_id": row[0],
                "tipo_id": row[1],
                "numero": row[2],
                "titulo": row[3],
                "estado": row[4],
                "fecha_publicacion": row[5],
            }
            for row in rows
        ]

        if norms:
            cursor.execute("SELECT id, nombre FROM tipos_normas")
            types = {row[0]: row[1] for row in cursor.fetchall()}
            for result in norms:
                result["tipo_nombre"] = types.get(result["tipo_id"], "—")

        cursor.close()
        return norms

    def get_versiones(self, id_norma: int) -> List[Dict]:
        """Devuelve el historial de versiones de una norma, de más reciente a más antigua."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT version_num, hash_xml, xml_path, md_path, titulo, estado, detectado_en
            FROM {self.versions_table}
            WHERE id_norma = %s
            ORDER BY version_num DESC
            """,
            (id_norma,),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "version_num": row[0],
                "hash_xml": row[1],
                "xml_path": row[2],
                "md_path": row[3],
                "titulo": row[4],
                "estado": row[5],
                "detectado_en": row[6],
            }
            for row in rows
        ]

    def get_version(self, id_norma: int, version_num: int) -> Optional[Dict]:
        """Devuelve una versión histórica específica de una norma."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT version_num, hash_xml, xml_path, md_path, titulo, estado, detectado_en
            FROM {self.versions_table}
            WHERE id_norma = %s AND version_num = %s
            """,
            (id_norma, version_num),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            "version_num": row[0],
            "hash_xml": row[1],
            "xml_path": row[2],
            "md_path": row[3],
            "titulo": row[4],
            "estado": row[5],
            "detectado_en": row[6],
        }

    def get_stats(self) -> Dict:
        """Estadísticas de normas."""
        cursor = self.conn.cursor()
        stats = {}

        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        stats["total"] = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT COUNT(*) FROM {self.table_name} WHERE estado = 'vigente'"
        )
        stats["vigentes"] = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT COUNT(*) FROM {self.table_name} WHERE estado = 'derogada'"
        )
        stats["derogadas"] = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT tn.nombre, COUNT(n.id)
            FROM {self.table_name} n
            JOIN tipos_normas tn ON n.id_tipo = tn.id
            GROUP BY tn.nombre
            ORDER BY COUNT(n.id) DESC
            LIMIT 5
        """)
        stats["por_tipo"] = [
            {"tipo": row[0], "total": row[1]} for row in cursor.fetchall()
        ]

        cursor.execute(f"SELECT COUNT(*) FROM {self.versions_table}")
        stats["versiones_archivadas"] = cursor.fetchone()[0]

        cursor.close()
        return stats

    def close(self) -> None:
        if self.own_connection and self.conn:
            self.conn.close()
