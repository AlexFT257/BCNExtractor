import psycopg2
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

def test_connection():
    """Prueba la conexión a PostgreSQL"""
    
    # Configuración desde .env
    db_config = {
        'host': 'localhost',
        'port': os.getenv('POSTGRES_PORT', 5432),
        'database': os.getenv('POSTGRES_DB', 'bcn_normas'),
        'user': os.getenv('POSTGRES_USER', 'bcn_user'),
        'password': os.getenv('POSTGRES_PASSWORD', 'changeme')
    }
    
    try:
        # Intentar conexión
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Verificar versión de PostgreSQL
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        assert True
        assert version.split(',')[0].startswith('PostgreSQL')
        
        # Verificar extensiones
        cursor.execute("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname IN ('uuid-ossp', 'pg_trgm', 'unaccent')
            ORDER BY extname;
        """)
        
        extensiones = cursor.fetchall()
        
        assert extensiones, "No se encontraron extensiones"
        
        # Verificar esquemas
        cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'bcn';
        """)
        
        esquema = cursor.fetchone()
        assert esquema, "Esquema 'bcn' no encontrado"
        
        # Listar tablas existentes
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' OR table_schema = 'bcn'
            ORDER BY table_name;
        """)
        
        tablas = cursor.fetchall()
        
        assert tablas, "No hay tablas creadas aún"
        
        # Cerrar conexión
        cursor.close()
        conn.close()
        assert True
        
    except psycopg2.OperationalError as e:
        print("Error de conexión:")
        print(f"\t{e}")
        assert False
        
    except Exception as e:
        print(f"Error inesperado: {e}")
        assert False
