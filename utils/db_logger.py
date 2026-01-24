import psycopg2
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()


class DBLogger:
    """Registra descargas y operaciones en PostgreSQL"""
    
    def __init__(self, db_connection=None):
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
        
        self._ensure_table()
    
    def _ensure_table(self):
        """Crea tabla de descargas si no existe"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS descargas (
                id SERIAL PRIMARY KEY,
                id_norma INTEGER,
                tipo_descarga VARCHAR(50),
                estado VARCHAR(50),
                fecha_intento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_mensaje TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_descargas_norma ON descargas(id_norma);
            CREATE INDEX IF NOT EXISTS idx_descargas_estado ON descargas(estado);
            CREATE INDEX IF NOT EXISTS idx_descargas_fecha ON descargas(fecha_intento);
        """)
        
        self.conn.commit()
        cursor.close()
        print("Tabla descargas creada/validada")
    
    def log(
        self,
        id_norma: int,
        estado: str,
        tipo_descarga: str = 'completa',
        error: Optional[str] = None
    ):
        """
        Registra una descarga
        
        Args:
            id_norma: ID de la norma
            estado: 'exitosa', 'error', 'sin_cambios'
            tipo_descarga: 'completa', 'metadatos'
            error: Mensaje de error opcional
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                INSERT INTO descargas (id_norma, tipo_descarga, estado, error_mensaje)
                VALUES (%s, %s, %s, %s)
            """, (id_norma, tipo_descarga, estado, error))
            
            self.conn.commit()
            cursor.close()
            
        except Exception as e:
            print(f"Error logging: {e}")
    
    def get_recent(
        self,
        days: int = 7,
        estado: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Obtiene descargas recientes
        
        Args:
            days: Días hacia atrás
            estado: Filtrar por estado
            limit: Límite de resultados
        """
        cursor = self.conn.cursor()
        
        fecha_desde = datetime.now() - timedelta(days=days)
        
        where_clause = "WHERE fecha_intento > %s"
        params = [fecha_desde]
        
        if estado:
            where_clause += " AND estado = %s"
            params.append(estado)
        
        params.append(limit)
        
        cursor.execute(f"""
            SELECT id, id_norma, tipo_descarga, estado, 
                   fecha_intento, error_mensaje
            FROM descargas
            {where_clause}
            ORDER BY fecha_intento DESC
            LIMIT %s
        """, params)
        
        results = [
            {
                'id': row[0],
                'id_norma': row[1],
                'tipo_descarga': row[2],
                'estado': row[3],
                'fecha_intento': row[4],
                'error_mensaje': row[5]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return results
    
    def get_stats(self, days: int = 7) -> Dict:
        """
        Estadísticas de descargas
        
        Args:
            days: Días hacia atrás
        """
        cursor = self.conn.cursor()
        
        fecha_desde = datetime.now() - timedelta(days=days)
        
        stats = {}
        
        # Total
        cursor.execute("""
            SELECT COUNT(*) 
            FROM descargas 
            WHERE fecha_intento > %s
        """, (fecha_desde,))
        stats['total'] = cursor.fetchone()[0]
        
        # Por estado
        cursor.execute("""
            SELECT estado, COUNT(*) 
            FROM descargas 
            WHERE fecha_intento > %s
            GROUP BY estado
        """, (fecha_desde,))
        stats['por_estado'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Errores recientes
        cursor.execute("""
            SELECT id_norma, error_mensaje, fecha_intento
            FROM descargas
            WHERE estado = 'error' AND fecha_intento > %s
            ORDER BY fecha_intento DESC
            LIMIT 10
        """, (fecha_desde,))
        stats['errores_recientes'] = [
            {
                'id_norma': row[0],
                'error': row[1],
                'fecha': row[2]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return stats
    
    def get_by_norma(self, id_norma: int, limit: int = 10) -> List[Dict]:
        """Obtiene historial de descargas de una norma"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT id, tipo_descarga, estado, fecha_intento, error_mensaje
            FROM descargas
            WHERE id_norma = %s
            ORDER BY fecha_intento DESC
            LIMIT %s
        """, (id_norma, limit))
        
        results = [
            {
                'id': row[0],
                'tipo_descarga': row[1],
                'estado': row[2],
                'fecha_intento': row[3],
                'error_mensaje': row[4]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return results
    
    def close(self):
        if self.own_connection and self.conn:
            self.conn.close()