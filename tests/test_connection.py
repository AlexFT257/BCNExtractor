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
    
    print("Intentando conectar a PostgreSQL...")
    print(f"   Host: {db_config['host']}:{db_config['port']}")
    print(f"   Database: {db_config['database']}")
    print(f"   User: {db_config['user']}")
    print()
    
    try:
        # Intentar conexión
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Verificar versión de PostgreSQL
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print("Conexión exitosa!")
        print(f"   PostgreSQL: {version.split(',')[0]}")
        print()
        
        # Verificar extensiones
        cursor.execute("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname IN ('uuid-ossp', 'pg_trgm', 'unaccent')
            ORDER BY extname;
        """)
        
        extensiones = cursor.fetchall()
        if extensiones:
            print("📦 Extensiones instaladas:")
            for ext in extensiones:
                print(f"   - {ext[0]} (v{ext[1]})")
        else:
            print("No se encontraron extensiones")
        print()
        
        # Verificar esquemas
        cursor.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'bcn';
        """)
        
        esquema = cursor.fetchone()
        if esquema:
            print("Esquema 'bcn' encontrado")
        else:
            print("Esquema 'bcn' no encontrado")
        print()
        
        # Listar tablas existentes
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' OR table_schema = 'bcn'
            ORDER BY table_name;
        """)
        
        tablas = cursor.fetchall()
        if tablas:
            print("Tablas existentes:")
            for tabla in tablas:
                print(f"   - {tabla[0]}")
        else:
            print("No hay tablas creadas aún")
        print()
        
        # Cerrar conexión
        cursor.close()
        conn.close()
        
        print("Test completado exitosamente")
        return True
        
    except psycopg2.OperationalError as e:
        print("❌ Error de conexión:")
        print(f"   {e}")
        print()
        print("Verifica que:")
        print("   1. Docker Desktop esté corriendo")
        print("   2. El contenedor PostgreSQL esté activo: docker-compose ps")
        print("   3. Las credenciales en .env sean correctas")
        return False
        
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False


if __name__ == "__main__":
    test_connection()