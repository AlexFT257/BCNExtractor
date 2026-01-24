import psycopg2
from psycopg2.extras import execute_batch
from pathlib import Path
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class TiposNormasManager():
    """Clase que se encarga de manejar los tipos de normas en la base de datos"""
    TABLE_NAME = 'tipos_normas'
    
    def __init__(self, db_connection=None) -> None:
        self.conn = db_connection
        self.own_connection = False
        
        if not self.conn:
            self.conn = psycopg2.connect(
                host='localhost',
                port=os.getenv('POSTGRES_PORT', 5432),
                database=os.getenv('POSTGRES_DB', 'bcn_normas'),
                user=os.getenv('POSTGRES_USER', 'bcn_user'),
                password=os.getenv('POSTGRES_PASSWORD', 'changeme')
            )
            self.own_connection = True
        
        self.ensure_table_exists()
            
    def ensure_table_exists(self):
        cursor = self.conn.cursor()
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL UNIQUE,
                abreviatura TEXT,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_tipos_normas_nombre ON {self.TABLE_NAME} (nombre);
            CREATE INDEX IF NOT EXISTS idx_tipos_normas_abreviatura ON {self.TABLE_NAME} (abreviatura);
        """)
        self.conn.commit()
        cursor.close()
        print(f"Tabla {self.TABLE_NAME} creada/validada")
        
    def add_or_update(
            self, 
            id: int, 
            nombre: str,
            abreviatura: Optional[str] = None,
        ) -> bool:
        
        cursor = self.conn.cursor()
        
        try:
            cursor.execute(f"""
                INSERT INTO {self.TABLE_NAME} 
                    (id, nombre, abreviatura, fecha_creacion)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) 
                DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    abreviatura = EXCLUDED.abreviatura,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            """, (id, nombre, abreviatura, datetime.now()))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"\tError agregando tipo {nombre}: {e}")
            return False
        finally:
            cursor.close()
    
    def add_batch(self, tipos: List[Dict]) -> Dict:
        cursor = self.conn.cursor()
        stats = {'total': len(tipos), 'insertados': 0, 'actualizados': 0, 'errores': 0}
        
        try:
            # Obtener IDs existentes
            cursor.execute(f"SELECT id FROM {self.TABLE_NAME}")
            existing_ids = {row[0] for row in cursor.fetchall()}
            
            # Preparar datos
            data = [
                (
                    tipo['id'],
                    tipo['nombre'],
                    tipo.get('abreviatura'),
                    datetime.now()
                )
                for tipo in tipos
            ]
            
            # Ejecutar upsert en batch
            query = f"""
                INSERT INTO {self.TABLE_NAME}
                    (id, nombre, abreviatura, fecha_creacion)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    abreviatura = EXCLUDED.abreviatura,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            """
            
            execute_batch(cursor, query, data)
            
            # Calcular estadísticas
            new_ids = {tipo['id'] for tipo in tipos}
            stats['insertados'] = len(new_ids - existing_ids)
            stats['actualizados'] = len(new_ids & existing_ids)
            
            self.conn.commit()
            print(f"\tBatch completado: {stats['insertados']} nuevos, {stats['actualizados']} actualizados")
            
        except Exception as e:
            self.conn.rollback()
            print(f"✗ Error en batch: {e}")
            stats['errores'] = len(tipos)
        finally:
            cursor.close()
        
        return stats
            
    def get_by_id(self, id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        
        cursor.execute(f"""
            SELECT id, nombre, abreviatura, fecha_creacion, fecha_actualizacion
            FROM {self.TABLE_NAME}
            WHERE id = %s
        """, (id,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                'id': row[0],
                'nombre': row[1],
                'abreviatura': row[2],
                'fecha_creacion': row[3],
                'fecha_actualizacion': row[4]
            }
            
        return None
        
    def get_by_name(self, nombre: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        
        cursor.execute(f"""
            SELECT id, nombre, abreviatura, fecha_creacion, fecha_actualizacion
            FROM {self.TABLE_NAME}
            WHERE LOWER(nombre) = LOWER(%s)
        """, (nombre,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                'id': row[0],
                'nombre': row[1],
                'abreviatura': row[2],
                'fecha_creacion': row[3],
                'fecha_actualizacion': row[4]
            }
            
        return None
    
    def get_all(self) -> List[Dict]:
        cursor = self.conn.cursor()
        
        cursor.execute(f"""
            SELECT id, nombre, abreviatura, fecha_creacion, fecha_actualizacion
            FROM {self.TABLE_NAME}
            ORDER BY nombre
        """)
        
        tipos = [
            {
                'id': row[0],
                'nombre': row[1],
                'abreviatura': row[2],
                'fecha_creacion': row[3],
                'fecha_actualizacion': row[4]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return tipos
        
    def get_or_create(
            self, 
            id: int, 
            nombre: str,
            abreviatura: Optional[str] = None
        ) -> Dict:
        
        # Intentar obtener
        tipo = self.get_by_id(id)
        
        if tipo:
            return tipo
        
        # Si no existe, crear
        self.add_or_update(id, nombre, abreviatura)
        
        # Retornar el recién creado
        return self.get_by_id(id)
            
    def close(self):
        if self.own_connection and self.conn:
                    self.conn.close()
                    print("✓ Conexión cerrada")