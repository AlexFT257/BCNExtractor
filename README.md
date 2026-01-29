# Extractor de Normas BCN

> Sistema de extracción y almacenamiento de normas legales chilenas desde la Biblioteca del Congreso Nacional (BCN)

**Extractor de Normas BCN** es una herramienta de código abierto diseñada para automatizar la descarga, procesamiento y almacenamiento de normas legales chilenas (leyes, decretos, resoluciones, etc.) desde los servicios web de la [Biblioteca del Congreso Nacional de Chile](https://www.bcn.cl/leychile/).

Este proyecto está pensado como la capa de **Extracción** de un pipeline ELT (Extract, Load, Transform) para análisis legal, permitiendo a investigadores, desarrolladores y organizaciones acceder de forma programática a las normas relevantes para instituciones específicas.

![Status](https://img.shields.io/badge/status-active%20development-green)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15+](https://img.shields.io/badge/postgresql-15+-blue.svg)](https://www.postgresql.org/)

> [!NOTE]
> Este proyecto no está afiliado oficialmente con la Biblioteca del Congreso Nacional de Chile. Es una herramienta independiente que utiliza sus servicios web públicos.

## Objetivos

### Objetivo Principal
Proporcionar una base de datos estructurada y actualizable de normas legales chilenas organizadas por instituciones, facilitando el acceso programático a la legislación nacional.

### Objetivos Específicos

1. **Extracción Automatizada**: Descargar normas desde los servicios web de la BCN de forma eficiente y resiliente
2. **Almacenamiento Estructurado**: Mantener una base de datos PostgreSQL con las normas, instituciones y sus relaciones
3. **Búsqueda Eficiente**: Implementar capacidades de búsqueda full-text sobre el contenido de las normas
4. **Trazabilidad**: Registrar el historial de descargas y actualizaciones de cada norma
5. **Replicabilidad**: Facilitar el despliegue mediante Docker para cualquier usuario

### Casos de Uso

- **Análisis Legal**: Investigadores que necesitan analizar legislación específica de un sector
- **Compliance**: Empresas que deben monitorear normativas aplicables a su industria
- **Transparencia**: Ciudadanos y organizaciones que buscan acceder a información legal estructurada
- **Data Science**: Científicos de datos que quieren aplicar NLP/ML sobre corpus legales

## Arquitectura

```
┌───────────────────────────────────────────────────────────┐
│                         USUARIO                           │
└────────────────────────────┬──────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────┐
│                    INTERFACES DE USUARIO                  │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│    │   CLI App    │  │   REST API   │  │  Web UI (*)  │   │
│    │  (bcn_cli)   │  │  (FastAPI)   │  │              │   │
│    └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────────────┬──────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────┐
│                     PYTHON APPLICATION                    │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│    │  BCN Client  │  │  XML Parser  │  │   Managers   │   │
│    │   (HTTP)     │→ │   (lxml)     │→ │  (Database)  │   │
│    └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                    POSTGRESQL DATABASE                    │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│    │   Normas     │  │Instituciones │  │Tipos Normas  │   │
│    │              │  │              │  │              │   │
│    │  (+ FTS)     │  │              │  │              │   │
│    └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                      DOCKER VOLUMES                       │
│     ┌──────────────┐              ┌──────────────┐        │
│     │  PostgreSQL  │              │   XML Files  │        │
│     │     Data     │              │   (backup)   │        │
│     └──────────────┘              └──────────────┘        │
└───────────────────────────────────────────────────────────┘

(*) En roadmap
```

### Componentes Principales

1. **BCN Client** (`bcn_client.py`): Módulo HTTP para interactuar con los servicios web de la BCN
2. **XML Parser** (`utils/norm_parser.py`): Procesador de documentos XML que convierte a Markdown y extrae metadatos
3. **Managers** (`managers/`): Capa de abstracción para operaciones de base de datos
   - `NormsManager`: Gestión de normas
   - `InstitutionManager`: Gestión de instituciones
   - `TiposNormasManager`: Gestión de tipos de normas
4. **CLI Interface** (`bcn_cli.py`): Interfaz de línea de comandos para gestionar el sistema
5. **REST API** (`api.py`): API REST con FastAPI para consultas programáticas
6. **Database Logger** (`utils/db_logger.py`): Sistema de logging de operaciones


## Características

### Versión Actual

- ✅ Extracción de instituciones desde página de agrupadores de la BCN
- ✅ Descarga de normas por institución vía servicios web
- ✅ Almacenamiento en PostgreSQL con Docker
- ✅ Parseo de XML y extracción de metadatos
- ✅ Conversión de normas a formato Markdown
- ✅ Búsqueda full-text (PostgreSQL FTS)
- ✅ Sistema de logging y manejo de errores
- ✅ Detección de cambios en normas (hash MD5)
- ✅ CLI completa para operaciones básicas y avanzadas
- ✅ API REST con FastAPI
- ✅ Gestión de tipos de normas
- ✅ Sincronización batch de normas por institución

### Roadmap (Futuras Versiones)

- 🔲 Actualización incremental de normas modificadas
- 🔲 Interfaz web para búsqueda y visualización
- 🔲 Sistema de notificaciones para normas nuevas/modificadas
- 🔲 Soporte para versiones históricas de normas
- 🔲 Análisis de relaciones entre normas (modificaciones, derogaciones)

## Instalación

### 1. Requisitos Previos

- **Docker Desktop** (o Docker Engine + Docker Compose)
  - Windows: [Descargar Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)
  - Linux: [Instalar Docker Engine](https://docs.docker.com/engine/install/)
  - macOS: [Descargar Docker Desktop](https://docs.docker.com/desktop/install/mac-install/)
- **Python 3.9 o superior**
- **Git**

### 2. Instalación

```bash
# Clonar repositorio
git clone https://github.com/AlexFT257/BCNExtractor.git
cd BCNExtractor

# Iniciar PostgreSQL
docker-compose up -d

# Instalar dependencias
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Uso Básico

```bash
# Cargar instituciones
python cli_instituciones.py load data/instituciones.csv

# Listar normas de una institución
python bcn_cli.py list 17

# Sincronizar a base de datos
python bcn_cli.py sync 17 --limit 10

# Buscar normas
python bcn_cli.py search "medio ambiente"

# Ver estadísticas
python bcn_cli.py stats
```

## Documentación

- [Guía de Uso](docs/USAGE.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [API de la BCN](docs/API_BCN.md)

FastAPI genera automáticamente documentación:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI**: `http://localhost:8000/openapi.json`

## 📁 Estructura del Proyecto

```
BCNExtractor/
│
├── docker-compose.yml          # Configuración Docker
├── requirements.txt            # Dependencias Python
├── .env.example                # Plantilla variables de entorno
├── README.md                   # Este archivo
│
├── bcn_client.py               # Cliente para la API de la BCN
├── bcn_cli.py                  # CLI para manejar la aplicación
├── institution_cli.py          # CLI para manejar instituciones
│
├── api.py                      # App de Fast API
├── test_api.py                 # Test de la API
│
├── loaders/                        # Clases para cargar datos desde archivos
│   └── institutions.py
│
├── managers/                       # Clases para manejar datos en la base de datos
│   ├── institutions.py
│   ├── norms.py
│   └── norms_types.py
│
├── utils/                          # Parsers, loggers y utils 
│   ├── db_logger.py
│   └── norm_parser.py              # Parser de normas (xml y md)
│
├── data/
│   ├── xml/                        # XMLs y schemas descargados (backup)
│   ├── logs/                       # Archivos de log
│   ├── cache/                      # Cache de datos
│   ├── sample/                     # Ejemplos de respuesta del web service de la BCN
│   ├── extractor_instituciones.py  # Util para extraer instituciones del html
│   └── instituciones.csv           # Instituciones de la BCN (backup)
│   └── bcn_schema.xml              # Schema del xml de la BCN
│
├── tests/                          # [WIP]
│   ├── test_bcn_client.py
│   ├── test_parser.py
│   └── test_database.py
│
└── docs/
    ├── API_BCN.md              # Documentación servicios BCN
    └── DATABASE_SCHEMA.md      # Esquema de base de datos [WIP]
    └── USAGE.md                # Guia de uso y endpoints
    └── ARCHITECTURE.md         # Arquitectura del proyecto
```

## 🗄️ Base de Datos

### Esquema Principal

```sql
-- Tabla de normas
normas (
  id_norma INTEGER PRIMARY KEY,
  tipo VARCHAR(50),
  numero VARCHAR(50),
  titulo TEXT,
  fecha_promulgacion DATE,
  fecha_publicacion DATE,
  organismo TEXT,
  estado VARCHAR(50),
  contenido_texto TEXT,
  metadata_json JSONB,
  xml_path TEXT,
  hash_xml VARCHAR(32),
  fecha_descarga TIMESTAMP,
  fecha_actualizacion TIMESTAMP
)

-- Tabla de instituciones
instituciones (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL,
  fecha_agregada TIMESTAMP,
  fecha_actualizacion TIMESTAMP
)

-- Tabla de tipos de normas
tipos_normas (
  id INTEGER PRIMARY KEY,
  nombre TEXT NOT NULL,
  abreviatura TEXT,
  fecha_agregada TIMESTAMP,
  fecha_actualizacion TIMESTAMP
)

-- Relación muchos-a-muchos
normas_instituciones (
  id_norma INTEGER,
  id_institucion INTEGER,
  fecha_asociacion TIMESTAMP,
  PRIMARY KEY (id_norma, id_institucion)
)

-- Log de descargas
descargas (
  id SERIAL PRIMARY KEY,
  id_norma INTEGER,
  tipo_descarga VARCHAR(50),
  estado VARCHAR(50),
  fecha_intento TIMESTAMP,
  error_mensaje TEXT
)
```

### Índices y Optimizaciones

- Full-text search en `contenido_texto` usando PostgreSQL `tsvector`
- Índices en `tipo`, `estado`, `fecha_publicacion`
- JSONB indexado para búsquedas en metadata

## 🗺️ Roadmap

### Fase 1: MVP (Versión 1.0)
- [x] Extracción de instituciones
- [x] Descarga de normas por institución
- [x] Almacenamiento en PostgreSQL
- [x] CLI básica
- [x] Docker setup

### Fase 2: Optimización (Versión 1.1)
- [x] Sistema de caché para reducir requests
- [x] Rate limiting configurable
- [x] Reintentos automáticos en fallos
- [ ] Benchmarking
- [ ] Métricas de performance

### Fase 3: API (Versión 2.0)
- [x] API REST con FastAPI
- [x] Test de la API
- [x] Endpoints de búsqueda avanzada
- [x] Documentación OpenAPI

### Fase 4: Frontend (Versión 3.0)
- [ ] Interfaz web de búsqueda
- [ ] Dashboard de estadísticas
- [ ] Visualización de relaciones entre normas


## 📄 Licencia

Este proyecto está licenciado bajo **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

### Esto significa que puedes:

- ✅ **Compartir**: Copiar y redistribuir el material en cualquier medio o formato
- ✅ **Adaptar**: Remezclar, transformar y construir sobre el material

### Bajo las siguientes condiciones:

- **Atribución**: Debes dar crédito apropiado, proporcionar un enlace a la licencia e indicar si se realizaron cambios
- **No Comercial**: No puedes usar el material con fines comerciales
- **Compartir Igual**: Si remezclas, transformas o construyes sobre el material, debes distribuir tus contribuciones bajo la misma licencia

Para uso comercial, por favor contacta a [ftb2570@gmail.com](mailto:ftb2570@gmail.com).