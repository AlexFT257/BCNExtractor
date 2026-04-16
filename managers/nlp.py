import os
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

from utils.nlp import (
    EntidadNombrada,
    NLPAnalyzer,
    ObligacionDetectada,
    ReferenciaNormativa,
    ResultadoNLP,
)

load_dotenv()


class NLPManager:
    """Gestiona el almacenamiento y consulta de datos NLP extraídos de normas."""

    table_referencias = "normas_referencias"
    table_entidades = "normas_entidades"
    table_obligaciones = "normas_obligaciones"
    table_normas = "normas"

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

        self.analyzer = NLPAnalyzer()
        self.ensure_nlp_tables()

    def ensure_nlp_tables(self) -> None:
        """Crea las tablas NLP si no existen."""
        cursor = self.conn.cursor()
        cursor.execute(f"""
            -- Referencias a otras normas detectadas en el texto
            CREATE TABLE IF NOT EXISTS {self.table_referencias} (
                id              SERIAL PRIMARY KEY,
                id_norma        INTEGER NOT NULL REFERENCES normas(id) ON DELETE CASCADE,
                tipo_norma      VARCHAR(50) NOT NULL,
                numero          VARCHAR(20),
                anio            VARCHAR(4),
                organismo       TEXT,
                texto_original  TEXT NOT NULL,
                resolvida       BOOLEAN DEFAULT FALSE,
                id_norma_ref    INTEGER REFERENCES normas(id) ON DELETE SET NULL,
                fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_ref_norma
                ON {self.table_referencias}(id_norma);
            CREATE INDEX IF NOT EXISTS idx_ref_tipo_numero
                ON {self.table_referencias}(tipo_norma, numero);
            CREATE INDEX IF NOT EXISTS idx_ref_no_resolvida
                ON {self.table_referencias}(resolvida) WHERE resolvida = FALSE;

            -- Entidades nombradas (NER)
            CREATE TABLE IF NOT EXISTS {self.table_entidades} (
                id          SERIAL PRIMARY KEY,
                id_norma    INTEGER NOT NULL REFERENCES normas(id) ON DELETE CASCADE,
                texto       TEXT NOT NULL,
                tipo        VARCHAR(30) NOT NULL,
                inicio      INTEGER,
                fin         INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_ent_norma
                ON {self.table_entidades}(id_norma);
            CREATE INDEX IF NOT EXISTS idx_ent_tipo
                ON {self.table_entidades}(tipo);
            CREATE INDEX IF NOT EXISTS idx_ent_texto
                ON {self.table_entidades}(texto);

            -- Obligaciones y plazos detectados
            CREATE TABLE IF NOT EXISTS {self.table_obligaciones} (
                id              SERIAL PRIMARY KEY,
                id_norma        INTEGER NOT NULL REFERENCES normas(id) ON DELETE CASCADE,
                texto_completo  TEXT NOT NULL,
                sujeto          TEXT,
                verbo           VARCHAR(50),
                plazo           TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_obl_norma
                ON {self.table_obligaciones}(id_norma);
        """)
        self.conn.commit()
        cursor.close()

    def analizar_y_guardar(self, id_norma: int, texto_markdown: str) -> ResultadoNLP:
        """Analiza una norma y persiste todos los resultados NLP.

        Reemplaza cualquier análisis previo de la misma norma.
        """
        resultado = self.analyzer.analizar(id_norma, texto_markdown)
        cursor = self.conn.cursor()

        try:
            self._limpiar_analisis_previo(cursor, id_norma)
            self._guardar_referencias(cursor, resultado.referencias, id_norma)
            self._guardar_entidades(cursor, resultado.entidades, id_norma)
            self._guardar_obligaciones(cursor, resultado.obligaciones, id_norma)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

        # Intentar resolver referencias contra la DB local
        self.resolver_referencias_pendientes(id_norma)

        return resultado

    def _limpiar_analisis_previo(self, cursor, id_norma: int) -> None:
        for tabla in [
            self.table_referencias,
            self.table_entidades,
            self.table_obligaciones,
        ]:
            cursor.execute(f"DELETE FROM {tabla} WHERE id_norma = %s", (id_norma,))

    def _guardar_referencias(self, cursor, referencias, id_norma: int) -> None:
        if not referencias:
            return
        cursor.executemany(
            f"""
            INSERT INTO {self.table_referencias}
                (id_norma, tipo_norma, numero, anio, organismo, texto_original)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    id_norma,
                    ref.tipo_norma,
                    ref.numero,
                    ref.anio,
                    ref.organismo,
                    ref.texto_original,
                )
                for ref in referencias
            ],
        )

    def _guardar_entidades(self, cursor, entidades, id_norma: int) -> None:
        if not entidades:
            return
        cursor.executemany(
            f"""
            INSERT INTO {self.table_entidades}
                (id_norma, texto, tipo, inicio, fin)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [(id_norma, ent.texto, ent.tipo, ent.inicio, ent.fin) for ent in entidades],
        )

    def _guardar_obligaciones(self, cursor, obligaciones, id_norma: int) -> None:
        if not obligaciones:
            return
        cursor.executemany(
            f"""
            INSERT INTO {self.table_obligaciones}
                (id_norma, texto_completo, sujeto, verbo, plazo)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (id_norma, obl.texto_completo, obl.sujeto, obl.verbo, obl.plazo)
                for obl in obligaciones
            ],
        )

    def resolver_referencias_pendientes(self, id_norma: Optional[int] = None) -> int:
        """Intenta resolver referencias no resueltas contra la tabla normas.

        Si id_norma es None, procesa todas las referencias pendientes de toda la DB.
        Retorna el número de referencias resueltas en esta ejecución.
        """
        cursor = self.conn.cursor()

        filtro_norma = "AND r.id_norma = %s" if id_norma else ""
        params = (id_norma,) if id_norma else ()

        cursor.execute(
            f"""
            SELECT r.id, r.tipo_norma, r.numero, r.anio
            FROM {self.table_referencias} r
            WHERE r.resolvida = FALSE AND r.numero IS NOT NULL
            {filtro_norma}
            """,
            params,
        )
        pendientes = cursor.fetchall()

        resueltas = 0
        for ref_id, tipo_norma, numero, anio in pendientes:
            id_norma_encontrada = self._buscar_norma_en_db(
                cursor, tipo_norma, numero, anio
            )
            if id_norma_encontrada:
                cursor.execute(
                    f"""
                    UPDATE {self.table_referencias}
                    SET resolvida = TRUE, id_norma_ref = %s
                    WHERE id = %s
                    """,
                    (id_norma_encontrada, ref_id),
                )
                resueltas += 1

        self.conn.commit()
        cursor.close()
        return resueltas

    def _buscar_norma_en_db(
        self, cursor, tipo_norma: str, numero: str, anio: Optional[str]
    ) -> Optional[int]:
        """Busca una norma por tipo y número en la tabla local."""
        # Mapeo de tipo_norma NLP → id_tipo en la tabla tipos_normas
        # Búsqueda flexible: número limpio sin puntos
        numero_limpio = numero.replace(".", "").replace(",", "")

        cursor.execute(
            """
            SELECT n.id
            FROM normas n
            JOIN tipos_normas tn ON n.id_tipo = tn.id
            WHERE REPLACE(n.numero, '.', '') = %s
              AND LOWER(tn.nombre) ILIKE %s
            LIMIT 1
            """,
            (numero_limpio, f"%{tipo_norma.replace('_', ' ')}%"),
        )
        row = cursor.fetchone()
        if row:
            return row[0]

        # Fallback: solo por número (más permisivo, mayor riesgo de colisión)
        cursor.execute(
            "SELECT id FROM normas WHERE REPLACE(numero, '.', '') = %s LIMIT 1",
            (numero_limpio,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_referencias(
        self,
        id_norma: int,
        solo_resueltas: bool = False,
    ) -> List[Dict]:
        """Devuelve las referencias normativas de una norma."""
        cursor = self.conn.cursor()
        filtro = "AND resolvida = TRUE" if solo_resueltas else ""
        cursor.execute(
            f"""
            SELECT id, tipo_norma, numero, anio, organismo,
                   texto_original, resolvida, id_norma_ref
            FROM {self.table_referencias}
            WHERE id_norma = %s {filtro}
            ORDER BY tipo_norma, numero
            """,
            (id_norma,),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "id": row[0],
                "tipo_norma": row[1],
                "numero": row[2],
                "anio": row[3],
                "organismo": row[4],
                "texto_original": row[5],
                "resolvida": row[6],
                "id_norma_ref": row[7],
            }
            for row in rows
        ]

    def get_normas_que_referencian(
        self, id_norma: int, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        """Devuelve qué normas de la DB referencian a esta norma (grafo inverso)."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT r.id_norma, n.numero, n.titulo, tn.nombre AS tipo
            FROM {self.table_referencias} r
            JOIN normas n ON r.id_norma = n.id
            LEFT JOIN tipos_normas tn ON n.id_tipo = tn.id
            WHERE r.id_norma_ref = %s AND r.resolvida = TRUE
            ORDER BY n.fecha_publicacion DESC
            LIMIT %s OFFSET %s
            """,
            (id_norma, limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "id_norma": row[0],
                "numero": row[1],
                "titulo": row[2],
                "tipo": row[3],
            }
            for row in rows
        ]

    def get_entidades(self, id_norma: int, tipo: Optional[str] = None) -> List[Dict]:
        """Devuelve entidades nombradas de una norma, opcionalmente filtradas por tipo."""
        cursor = self.conn.cursor()
        filtro = "AND tipo = %s" if tipo else ""
        params = (id_norma, tipo) if tipo else (id_norma,)

        cursor.execute(
            f"""
            SELECT texto, tipo, COUNT(*) as frecuencia
            FROM {self.table_entidades}
            WHERE id_norma = %s {filtro}
            GROUP BY texto, tipo
            ORDER BY frecuencia DESC, tipo, texto
            """,
            params,
        )
        rows = cursor.fetchall()
        cursor.close()

        return [{"texto": row[0], "tipo": row[1], "frecuencia": row[2]} for row in rows]

    def get_obligaciones(self, id_norma: int) -> List[Dict]:
        """Devuelve las obligaciones detectadas en una norma."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT texto_completo, sujeto, verbo, plazo
            FROM {self.table_obligaciones}
            WHERE id_norma = %s
            """,
            (id_norma,),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "texto_completo": row[0],
                "sujeto": row[1],
                "verbo": row[2],
                "plazo": row[3],
            }
            for row in rows
        ]

    def get_normas_analizadas(self) -> List[Dict]:
        """Devuelve todas las normas que han sido analizadas."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT n.id, n.id_tipo, n.numero
            FROM {self.table_normas} n
            JOIN {self.table_referencias} r ON n.id = r.id_norma
            GROUP BY n.id
            """
        )
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return []

        return [
            {
                "id": row[0],
                "tipo_norma": row[1],
                "numero": row[2],
            }
            for row in rows
        ]

    def get_stats_globales(self) -> Dict:
        """Estadísticas globales del análisis NLP."""
        cursor = self.conn.cursor()
        stats = {}

        cursor.execute(f"SELECT COUNT(*) FROM {self.table_referencias}")
        stats["total_referencias"] = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT COUNT(*) FROM {self.table_referencias} WHERE resolvida = TRUE"
        )
        stats["referencias_resueltas"] = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT COUNT(*) FROM {self.table_referencias} WHERE resolvida = FALSE"
        )
        stats["referencias_pendientes"] = cursor.fetchone()[0]

        cursor.execute(
            f"""
            SELECT tipo_norma, COUNT(*) as total
            FROM {self.table_referencias}
            GROUP BY tipo_norma
            ORDER BY total DESC
            """
        )
        stats["por_tipo_norma"] = [
            {"tipo": row[0], "total": row[1]} for row in cursor.fetchall()
        ]

        cursor.execute(
            f"""
            SELECT tipo, COUNT(DISTINCT texto) as entidades_unicas
            FROM {self.table_entidades}
            GROUP BY tipo
            ORDER BY entidades_unicas DESC
            """
        )
        stats["entidades_por_tipo"] = [
            {"tipo": row[0], "unicas": row[1]} for row in cursor.fetchall()
        ]

        cursor.execute(f"SELECT COUNT(*) FROM {self.table_obligaciones}")
        stats["total_obligaciones"] = cursor.fetchone()[0]

        cursor.close()
        return stats

    def build_context_for_llm(self, id_norma: int) -> str:
        """Genera un bloque de contexto estructurado para pasar a un LLM.

        Incluye referencias normativas, entidades relevantes y obligaciones clave.
        Útil para aumentar el contexto antes de una consulta RAG.
        """
        referencias = self.get_referencias(id_norma)
        entidades = self.get_entidades(id_norma)
        obligaciones = self.get_obligaciones(id_norma)

        partes: List[str] = []

        if referencias:
            partes.append("## Normas referenciadas")
            for ref in referencias:
                estado = "✓ en DB" if ref["resolvida"] else "no sincronizada"
                linea = f"- {ref['tipo_norma'].replace('_', ' ').title()} N° {ref['numero'] or '?'}"
                if ref["anio"]:
                    linea += f" ({ref['anio']})"
                if ref["organismo"]:
                    linea += f" — {ref['organismo']}"
                linea += f" [{estado}]"
                partes.append(linea)

        organismos = [e for e in entidades if e["tipo"] == "organismo"]
        if organismos:
            partes.append("\n## Organismos involucrados")
            for ent in organismos[:10]:
                partes.append(f"- {ent['texto']} (mencionado {ent['frecuencia']}x)")

        plazos = [o for o in obligaciones if o["plazo"]]
        if plazos:
            partes.append("\n## Obligaciones con plazo")
            for obl in plazos[:5]:
                linea = f"- {obl['sujeto'] or 'Sujeto no identificado'}: {obl['plazo']}"
                partes.append(linea)

        return "\n".join(partes)

    def close(self) -> None:
        if self.own_connection and self.conn:
            self.conn.close()
