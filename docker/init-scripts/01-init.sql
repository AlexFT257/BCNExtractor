-- Script de inicialización para PostgreSQL
-- Este script se ejecuta automáticamente cuando se crea el contenedor por primera vez

-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- Para generar UUIDs
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Para búsquedas de similitud
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- Para búsquedas sin acentos

-- Configurar búsqueda en español (solo si no existe)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'es'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION es ( COPY = spanish );
    END IF;
END $$;

-- Crear esquema para la aplicación
CREATE SCHEMA IF NOT EXISTS bcn;

-- Dar permisos al usuario actual de la base de datos
GRANT ALL PRIVILEGES ON SCHEMA bcn TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA bcn TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA bcn TO CURRENT_USER;

-- Configurar defaults para futuras tablas
ALTER DEFAULT PRIVILEGES IN SCHEMA bcn
    GRANT ALL PRIVILEGES ON TABLES TO CURRENT_USER;

ALTER DEFAULT PRIVILEGES IN SCHEMA bcn
    GRANT ALL PRIVILEGES ON SEQUENCES TO CURRENT_USER;

-- También dar permisos al esquema public
GRANT ALL PRIVILEGES ON SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;

-- Log de inicialización
DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Base de datos BCN Normas inicializada';
    RAISE NOTICE 'Usuario: %', CURRENT_USER;
    RAISE NOTICE 'Base de datos: %', CURRENT_DATABASE();
    RAISE NOTICE 'Extensiones: uuid-ossp, pg_trgm, unaccent';
    RAISE NOTICE 'Esquema creado: bcn';
    RAISE NOTICE 'Text Search Config: es (español)';
    RAISE NOTICE '===========================================';
END $$;
