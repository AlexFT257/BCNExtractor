# Extractor de Normas BCN

> Sistema de extracción y almacenamiento de normas legales chilenas desde la Biblioteca del Congreso Nacional (BCN)

**Extractor de Normas BCN** es una herramienta de código abierto diseñada para automatizar la descarga, procesamiento y almacenamiento de normas legales chilenas (leyes, decretos, resoluciones, etc.) desde los servicios web de la [Biblioteca del Congreso Nacional de Chile](https://www.bcn.cl/leychile/).

Este proyecto está pensado como la capa de **Extracción** de un pipeline ELT (Extract, Load, Transform) para análisis legal, permitiendo a investigadores, desarrolladores y organizaciones acceder de forma programática a las normas relevantes para instituciones específicas.

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15+](https://img.shields.io/badge/postgresql-15+-blue.svg)](https://www.postgresql.org/)

> [!NOTE]
> Este proyecto no está afiliado oficialmente con la Biblioteca del Congreso Nacional de Chile. Es una herramienta independiente que utiliza sus servicios web públicos.

## 🎯 Objetivos

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

## 🏗️ Arquitectura

### Stack Tecnológico

```
┌─────────────────────────────────────────────────────────┐
│                    USUARIO                              │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              PYTHON APPLICATION                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  BCN Client  │  │  XML Parser  │  │   Database   │   │
│  │   (HTTP)     │→ │   (lxml)     │→ │   Services   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              POSTGRESQL DATABASE                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Normas     │  │Instituciones │  │  Relaciones  │   │
│  │              │  │              │  │              │   │
│  │  (+ FTS)     │  │              │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              DOCKER VOLUMES                             │
│  ┌──────────────┐              ┌──────────────┐         │
│  │  PostgreSQL  │              │   XML Files  │         │
│  │     Data     │              │   (backup)   │         │
│  └──────────────┘              └──────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### Componentes Principales

1. **BCN Client**: Módulo HTTP para interactuar con los servicios web de la BCN
2. **XML Parser**: Procesador de documentos XML usando lxml y xmltodict
3. **Database Service**: Capa de abstracción para PostgreSQL usando SQLAlchemy
4. **CLI Interface**: Interfaz de línea de comandos para gestionar el sistema

## ✨ Características

### Versión 1.0 (MVP)

- ✅ Extracción de instituciones desde página de agrupadores de la BCN
- ✅ Descarga de normas por institución vía servicios web
- ✅ Almacenamiento en PostgreSQL con Docker
- ✅ Parseo de XML y extracción de metadatos
- ✅ Búsqueda full-text (PostgreSQL FTS)
- ✅ Sistema de logging y manejo de errores
- ✅ Detección de cambios en normas (hash MD5)
- ✅ CLI para operaciones básicas

### Roadmap (Futuras Versiones)

- 🔲 API REST para consultas
- 🔲 Actualización incremental de normas modificadas
- 🔲 Exportación a formatos alternativos (JSON, CSV)
- 🔲 Interfaz web para búsqueda y visualización
- 🔲 Sistema de notificaciones para normas nuevas/modificadas
- 🔲 Soporte para versiones históricas de normas
- 🔲 Análisis de relaciones entre normas (modificaciones, derogaciones)

## 📋 Requisitos Previos

- **Docker Desktop** (o Docker Engine + Docker Compose)
  - Windows: [Descargar Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)
  - Linux: [Instalar Docker Engine](https://docs.docker.com/engine/install/)
  - macOS: [Descargar Docker Desktop](https://docs.docker.com/desktop/install/mac-install/)
  
- **Python 3.9 o superior**
  ```bash
  python --version  # Verificar versión
  ```

- **Git** (para clonar el repositorio)
  ```bash
  git --version  # Verificar instalación
  ```

## 🚀 Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/extractor-normas-bcn.git
cd extractor-normas-bcn
```

### 2. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# .env
POSTGRES_USER=bcn_user
POSTGRES_PASSWORD=tu_password_seguro
POSTGRES_DB=bcn_normas
POSTGRES_PORT=5432

# Configuración de la aplicación
LOG_LEVEL=INFO
XML_STORAGE_PATH=./data/xml
```

### 3. Iniciar Servicios con Docker

```bash
# Construir e iniciar contenedores
docker-compose up -d

# Verificar que los servicios estén corriendo
docker-compose ps
```

### 4. Instalar Dependencias de Python

```bash
# Crear entorno virtual (recomendado)
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## 💻 Uso

### Comandos Básicos

#### 1. Instituciones

```bash
# Cargar instituciones desde CSV (actualiza existentes)
python institution_cli.py load data/instituciones.csv

# Reemplazar todas las instituciones
python institution_cli.py load data/instituciones.csv --mode replace

# Solo agregar nuevas (ignora duplicados)
python institution_cli.py load data/instituciones.csv --mode append

# Listar todas las instituciones
python institution_cli.py list

# Buscar instituciones
python institution_cli.py list --search ministerio

# Ver detalles de una institución
python institution_cli.py get 1041
```

#### 2. Normas por institución

```bash
# Listar normas de una institución
python bcn_cli.py list 1041 --limit 10

```

## 📁 Estructura del Proyecto

```
extractor-normas-bcn/
│
├── docker-compose.yml          # Configuración Docker
├── Dockerfile                  # Imagen Python
├── requirements.txt            # Dependencias Python
├── .env.example                # Plantilla variables de entorno
├── README.md                   # Este archivo
│
├── bcn_client.py               # Cliente para la API de la BCN
├── bcn_cli.py                  # CLI para manejar la aplicación
│
├── institution_cli.py          # CLI para manejar instituciones
├── institution_loader.py       # Util para cargar instituciones desde un archivo CSV
├── institution_manager.py      # Gestor de instituciones en la base de datos
│
├── norms_types_manager.py      # Gestor de tipos de normas en la base de datos
│
│
├── data/
│   ├── xml/                        # XMLs y schemas descargados (backup)
│   ├── logs/                       # Archivos de log
│   ├── cache/                      # Cache de datos
│   ├── sample/                     # Ejemplos de respuesta del web service de la BCN
│   ├── extractor_instituciones.py  # Util para extraer instituciones del html
│   ├── instituciones.html          # Instituciones de la BCN (simplificado)
│   └── instituciones.csv           # Instituciones de la BCN (backup)
│
├── tests/
│   ├── test_bcn_client.py
│   ├── test_parser.py
│   └── test_database.py
│
└── docs/
    ├── API_BCN.md              # Documentación servicios BCN
    └── DATABASE_SCHEMA.md      # Esquema de base de datos
```

## 🗄️ Base de Datos

### Esquema Principal (WIP)

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

Ver [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) para detalles completos.

## 🗺️ Roadmap

### Fase 1: MVP (Versión 1.0)
- [x] Extracción de instituciones
- [x] Descarga de normas por institución
- [x] Almacenamiento en PostgreSQL
- [x] CLI básica
- [x] Docker setup

### Fase 2: Optimización (Versión 1.1)
- [ ] Sistema de caché para reducir requests
- [ ] Rate limiting configurable
- [ ] Reintentos automáticos en fallos
- [ ] Métricas de performance

### Fase 3: API (Versión 2.0)
- [ ] API REST con FastAPI
- [ ] Endpoints de búsqueda avanzada
- [ ] Autenticación y rate limiting
- [ ] Documentación OpenAPI

### Fase 4: Frontend (Versión 3.0)
- [ ] Interfaz web de búsqueda
- [ ] Dashboard de estadísticas
- [ ] Visualización de relaciones entre normas

### Fase 5: Análisis Avanzado
- [ ] NLP para extracción de entidades
- [ ] Clasificación automática por materias
- [ ] Detección de similitud entre normas
- [ ] Generación de resúmenes automáticos

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

