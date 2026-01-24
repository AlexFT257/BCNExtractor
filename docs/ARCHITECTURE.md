# Arquitectura del Sistema

## Visión General

```
┌─────────────────────────────────────────────────────────────┐
│                       bcn_cli.py                            │
│                   (Orquestación + CLI)                      │
└──────────┬──────────────────────────────────────────────────┘
           │
           ├─► BCNClient          → HTTP/API BCN
           ├─► BCNXMLParser       → Parseo XML
           ├─► NormsManager       → CRUD Normas
           ├─► TiposNormasManager → CRUD Tipos
           ├─► InstitutionLoader  → CRUD Instituciones
           └─► DBLogger           → Logging
                      ↓
           ┌──────────────────────┐
           │  PostgreSQL (Docker) │
           └──────────────────────┘
```

## Componentes

### 1. BCNClient (`bcn_client.py`)
**Responsabilidad**: Comunicación con API de BCN

**Características**:
- Retry logic automático
- Rate limiting (0.5s entre requests)
- Caché local de XMLs
- Manejo de errores HTTP

**Métodos principales**:
```python
get_normas_por_institucion(id_institucion) → List[Dict]
get_norma_completa(id_norma) → str
get_norma_metadatos(id_norma) → str
```

### 2. BCNXMLParser (`norm_parser.py`)
**Responsabilidad**: Conversión XML → Markdown

**Características**:
- Parseo de estructura completa BCN
- Extracción de metadatos
- Generación de Markdown legible
- Manejo de namespaces XML

**Métodos principales**:
```python
parse_from_string(xml) → (markdown, metadata)
parse_from_file(filepath) → (markdown, metadata)
```

### 3. NormsManager (`norms_manager.py`)
**Responsabilidad**: CRUD de normas en PostgreSQL

**Características**:
- UPSERT inteligente (detecta cambios con hash)
- Guarda XML y Markdown en disco
- Búsqueda full-text
- Gestión de metadata como JSONB

**Métodos principales**:
```python
save(id_norma, xml, parsed_data, ...) → str
get_by_id(id_norma) → Dict
search(query) → List[Dict]
get_stats() → Dict
```

### 4. TiposNormasManager (`norms_types_manager.py`)
**Responsabilidad**: Gestión de tipos de normas

**Características**:
- Batch insert optimizado
- UPSERT por ID
- Caché de tipos

**Métodos principales**:
```python
add_batch(tipos) → Dict[stats]
get_by_id(id) → Dict
get_or_create(id, nombre, abrev) → Dict
```

### 5. InstitutionLoader (`csv_loader.py`)
**Responsabilidad**: Gestión de instituciones

**Características**:
- Carga desde CSV
- 3 modos: update, replace, append
- Búsqueda por nombre

**Métodos principales**:
```python
load_from_csv(csv_path, mode) → Dict[stats]
get_by_id(id) → Dict
search(query) → List[Dict]
```

### 6. DBLogger (`db_logger.py`)
**Responsabilidad**: Logging de operaciones

**Características**:
- Registro de todas las operaciones
- Estadísticas por período
- Errores recientes

**Métodos principales**:
```python
log(id_norma, tipo, estado, error) → None
get_stats(dias) → Dict
get_recent_errors(limit) → List
```

### 7. bcn_cli.py
**Responsabilidad**: Orquestación y CLI

**Características**:
- 6 comandos principales
- Manejo de argumentos
- Output formateado
- Manejo de errores user-friendly

## Flujo de Datos

### Flujo: Sincronización de Institución

```
1. bcn_cli.py sync 17
         ↓
2. InstitutionLoader.get_by_id(17)
         ↓ (verificar existe)
3. BCNClient.get_normas_por_institucion(17)
         ↓ (lista de normas)
4. TiposNormasManager.add_batch(tipos_unicos)
         ↓ (crear tipos)
5. Para cada norma:
   ├─► BCNClient.get_norma_completa(id)
   ├─► BCNXMLParser.parse_from_string(xml)
   ├─► NormsManager.save(...)
   └─► DBLogger.log(id, 'sync', 'exitosa')
         ↓
6. Retornar estadísticas
```

## Base de Datos

### Esquema

```sql
instituciones
├── id_institucion (PK)
├── nombre
└── tipo

tipos_normas
├── id (PK)
├── nombre
└── abreviatura

normas
├── id (PK)
├── id_tipo (FK → tipos_normas)
├── titulo
├── estado (vigente/derogada)
├── xml_path
├── md_path
└── metadata_json (JSONB)

normas_instituciones
├── id_norma (FK → normas)
└── id_institucion (FK → instituciones)

descargas
├── id_norma
├── tipo_operacion
├── estado
└── error_mensaje
```

### Índices

```sql
-- Búsqueda
CREATE INDEX idx_normas_titulo USING gin(to_tsvector('spanish', titulo));

-- Filtros
CREATE INDEX idx_normas_tipo ON normas(id_tipo);
CREATE INDEX idx_normas_estado ON normas(estado);

-- Logs
CREATE INDEX idx_descargas_norma ON descargas(id_norma);
CREATE INDEX idx_descargas_estado ON descargas(estado);
```

## Patrones de Diseño

### 1. Separation of Concerns
Cada clase tiene una única responsabilidad:
- BCNClient → Solo API
- NormsManager → Solo CRUD
- DBLogger → Solo logging

### 2. Dependency Injection
```python
# Las clases reciben conexiones existentes
norms_mgr = NormsManager()
tipos_mgr = TiposNormasManager(db_connection=norms_mgr.conn)
logger = DBLogger(db_connection=norms_mgr.conn)
```

### 3. UPSERT Pattern
```python
# Detecta cambios con hash, solo actualiza si cambió
hash_xml = hashlib.md5(xml_content.encode()).hexdigest()
if existing_hash == hash_xml:
    return 'sin_cambios'
```

### 4. Batch Processing
```python
# Procesa tipos en lote para eficiencia
tipos_unicos = {n['id_tipo']: {...} for n in normas}
tipos_mgr.add_batch(list(tipos_unicos.values()))
```

## Decisiones de Diseño

### ¿Por qué PostgreSQL y no SQLite?
- Full-text search en español
- JSONB para metadata flexible
- Mejor para múltiples conexiones concurrentes
- Escalable a millones de registros

### ¿Por qué guardar XML y Markdown?
- XML: Fuente original inmutable
- Markdown: Legible para humanos, menor consumo de tokens, fácil de procesar
- Permite re-procesar en el futuro

### ¿Por qué caché HTTP?
- Reduce carga en servidores BCN
- Acelera desarrollo/testing
- Permite trabajar offline

### ¿Por qué separar managers?
- Reutilizable en otros contextos (web, API)
- Fácil de testear
- Escalable a múltiples interfaces

