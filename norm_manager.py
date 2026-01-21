"""
Manager para CRUD de normas en la base de datos
"""
import psycopg2
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


class NormsManager:
    """Gestiona el CRUD de normas en PostgreSQL"""
    
    def __init__(self, xml_dir: str = "data/xml", md_dir: str = "data/md", db_connection=None):
        self.xml_dir = Path(xml_dir)
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        
        self.md_dir = Path(md_dir)
        self.md_dir.mkdir(parents=True, exist_ok=True)
        
        self.conn = db_connection
        self.own_connection = False
        
        if not self.conn:
            self.conn = self._create_connection()
            self.own_connection = True
        
        self._ensure_table()
    
    def _create_connection(self):
        return psycopg2.connect(
            host='localhost',
            port=os.getenv('POSTGRES_PORT', 5432),
            database=os.getenv('POSTGRES_DB', 'bcn_normas'),
            user=os.getenv('POSTGRES_USER', 'bcn_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'changeme')
        )
    
    def _ensure_table(self):
        cursor = self.conn.cursor()
        
        # Tabla normas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS normas (
                id INTEGER PRIMARY KEY,
                id_tipo INTEGER REFERENCES tipos_normas(id),
                numero VARCHAR(50),
                titulo TEXT,
                estado VARCHAR(20) DEFAULT 'vigente',
                fecha_publicacion DATE,
                fecha_promulgacion DATE,
                organismo TEXT,
                
                xml_path TEXT,
                md_path TEXT,
                contenido_texto TEXT,
                metadata_json JSONB,
                
                hash_xml VARCHAR(32),
                fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_normas_tipo ON normas(id_tipo);
            CREATE INDEX IF NOT EXISTS idx_normas_estado ON normas(estado);
            CREATE INDEX IF NOT EXISTS idx_normas_titulo 
                ON normas USING gin(to_tsvector('spanish', titulo));
        """)
        
        # Tabla relación normas-instituciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS normas_instituciones (
                id_norma INTEGER,
                id_institucion INTEGER,
                fecha_asociacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id_norma, id_institucion),
                FOREIGN KEY (id_norma) REFERENCES normas(id),
                FOREIGN KEY (id_institucion) REFERENCES instituciones(id)
            );
        """)
        
        
        
        self.conn.commit()
        cursor.close()
        print("Tablas de normas creadas/validadas")
    
    def save(
        self,
        id_norma: int,
        xml_content: str,
        parsed_data: Dict,
        id_tipo: Optional[int] = None,
        id_institucion: Optional[int] = None,
        markdown: Optional[str] = None,
        force: bool = False
    ) -> str:
        """
        Returns:
            'nueva', 'actualizada', 'sin_cambios'
        """
        # Hash para detectar cambios
        hash_xml = hashlib.md5(xml_content.encode()).hexdigest()
        
        # Verificar si existe
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT hash_xml FROM normas WHERE id = %s",
            (id_norma,)
        )
        existing = cursor.fetchone()
        
        # Sin cambios
        if existing and existing[0] == hash_xml and not force:
            cursor.close()
            return 'sin_cambios'
        
        # Guardar XML
        xml_path = self.xml_dir / f"{id_norma}.xml"
        xml_path.write_text(xml_content, encoding='utf-8')
        
        # Guardar Markdown si existe
        md_path = None
        if markdown:
            md_path = self.md_dir / f"{id_norma}.md"
            md_path.write_text(markdown, encoding='utf-8')
        
        # Metadata
        metadata = {
            'materias': parsed_data.get('materias', []),
            'organismos': parsed_data.get('organismos', []),
            'derogado': parsed_data.get('derogado', False),
            'es_tratado': parsed_data.get('es_tratado', False),           
        }
        
        # UPSERT
        cursor.execute("""
            INSERT INTO normas (
                id, id_tipo, numero, titulo, estado,
                fecha_publicacion, fecha_promulgacion, organismo,
                xml_path, md_path, contenido_texto, metadata_json,
                hash_xml, fecha_descarga, fecha_actualizacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                id_tipo = EXCLUDED.id_tipo,
                numero = EXCLUDED.numero,
                titulo = EXCLUDED.titulo,
                estado = EXCLUDED.estado,
                fecha_publicacion = EXCLUDED.fecha_publicacion,
                fecha_promulgacion = EXCLUDED.fecha_promulgacion,
                organismo = EXCLUDED.organismo,
                xml_path = EXCLUDED.xml_path,
                md_path = EXCLUDED.md_path,
                contenido_texto = EXCLUDED.contenido_texto,
                metadata_json = EXCLUDED.metadata_json,
                hash_xml = EXCLUDED.hash_xml,
                fecha_actualizacion = CURRENT_TIMESTAMP
        """, (
            id_norma,
            id_tipo,
            parsed_data.get('numero'),
            parsed_data.get('titulo'),
            parsed_data.get('estado', 'vigente'),
            parsed_data.get('fecha_publicacion'),
            parsed_data.get('fecha_promulgacion'),
            parsed_data.get('organismo'),
            str(xml_path),
            str(md_path) if md_path else None,
            parsed_data.get('contenido_texto'),
            json.dumps(metadata, ensure_ascii=False),
            hash_xml,
            datetime.now(),
            datetime.now()
        ))
        
        # Asociar con institución
        if id_institucion:
            cursor.execute("""
                INSERT INTO normas_instituciones (id_norma, id_institucion)
                VALUES (%s, %s)
                ON CONFLICT (id_norma, id_institucion) DO NOTHING
            """, (id_norma, id_institucion))
        
        self.conn.commit()
        cursor.close()
        
        return 'actualizada' if existing else 'nueva'
    
    def get_by_id(self, id_norma: int) -> Optional[Dict]:
        """Obtiene una norma por ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, id_tipo, numero, titulo, estado,
                   fecha_publicacion, fecha_promulgacion, organismo,
                   xml_path, md_path, metadata_json
            FROM normas
            WHERE id = %s
        """, (id_norma,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                'id': row[0],
                'id_tipo': row[1],
                'numero': row[2],
                'titulo': row[3],
                'estado': row[4],
                'fecha_publicacion': row[5],
                'fecha_promulgacion': row[6],
                'organismo': row[7],
                'xml_path': row[8],
                'md_path': row[9],
                'metadata': json.loads(row[10]) if row[10] else {}
            }
        return None
    
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Búsqueda full-text en normas"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, titulo, numero, estado, fecha_publicacion
            FROM normas
            WHERE to_tsvector('spanish', titulo) @@ plainto_tsquery('spanish', %s)
               OR titulo ILIKE %s
            ORDER BY fecha_publicacion DESC
            LIMIT %s
        """, (query, f'%{query}%', limit))
        
        results = [
            {
                'id': row[0],
                'titulo': row[1],
                'numero': row[2],
                'estado': row[3],
                'fecha_publicacion': row[4]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return results
    
    def get_stats(self) -> Dict:
        """Estadísticas de normas"""
        cursor = self.conn.cursor()
        
        stats = {}
        cursor.execute("SELECT COUNT(*) FROM normas")
        stats['total'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM normas WHERE estado = 'vigente'")
        stats['vigentes'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM normas WHERE estado = 'derogada'")
        stats['derogadas'] = cursor.fetchone()[0]
        
        cursor.close()
        return stats
    
    def close(self):
        if self.own_connection and self.conn:
            self.conn.close()