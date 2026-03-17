# BCN Extractor

> Pipeline ELT para descargar, procesar y almacenar normas legales chilenas desde la Biblioteca del Congreso Nacional (BCN).

[![Status](https://img.shields.io/badge/status-active%20development-green)](https://github.com/AlexFT257/BCNExtractor)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15+](https://img.shields.io/badge/postgresql-15+-blue.svg)](https://www.postgresql.org/)

Herramienta de código abierto pensada para investigadores, desarrolladores y organizaciones que necesiten acceso programático a la legislación chilena. Cubre el pipeline completo: extracción desde los servicios web de la BCN, parseo de XML, almacenamiento en PostgreSQL y búsqueda full-text.

> Este proyecto no está afiliado oficialmente con la Biblioteca del Congreso Nacional de Chile.

**Documentación completa:** [bcne.alexft.dev](https://bcne.alexft.dev/)

---

## Requisitos

- Docker Desktop (o Docker Engine + Compose)
- Python 3.9+
- Git

## Instalación

```bash
git clone https://github.com/AlexFT257/BCNExtractor.git
cd BCNExtractor

# Configurar credenciales
cp .env.example .env

# Levantar PostgreSQL
docker-compose up -d

# Instalar dependencias
pip install -r requirements.txt
```

Las credenciales por defecto en `.env.example` coinciden con las del `docker-compose.yml`, por lo que el proyecto funciona sin editar el `.env` en desarrollo local.

## Uso básico

### TUI (interfaz de terminal)

La forma más cómoda de usar el proyecto. Requiere `textual`:

```bash
pip install textual
python bcn_tui.py
```

| Tecla | Acción |
|-------|--------|
| `1` / `2` / `3` | Cambiar entre Normas, Dashboard y Logs |
| `/` | Filtrar instituciones |
| `s` | Sincronizar institución seleccionada |
| `r` | Leer texto completo de la norma seleccionada |
| `Esc` | Cerrar modal / cancelar sync |
| `q` | Salir |

El sync descarga las normas de la institución activa, las procesa y las guarda en la base de datos. Al terminar muestra un resumen y habilita el botón Cerrar.

### CLI

Los comandos están organizados en grupos. Todos los subcomandos soportan `--help`.

```bash
# Inicializar la base de datos y cargar instituciones desde el CSV incluido
python bcn_cli.py init

# Normas
python bcn_cli.py normas list 17 --limit 10       # Listar normas de una institución (consulta directa a BCN)
python bcn_cli.py normas get 206396 --md out.md   # Descargar norma como Markdown
python bcn_cli.py normas sync 17 --limit 50       # Sincronizar normas a la base de datos
python bcn_cli.py normas search "medio ambiente"  # Buscar en la base de datos local

# Instituciones
python bcn_cli.py instituciones list              # Listar todas las instituciones
python bcn_cli.py instituciones list --search ministerio  # Filtrar por nombre
python bcn_cli.py instituciones get 1041          # Ver detalle de una institución
python bcn_cli.py instituciones load data/instituciones.csv  # Cargar desde CSV

# Sistema
python bcn_cli.py stats                           # Ver estadísticas
python bcn_cli.py stats --errors                  # Incluir errores recientes
python bcn_cli.py cache stats                     # Info del caché local
python bcn_cli.py cache clear                     # Limpiar caché
```

El flag `--debug` es global y puede combinarse con cualquier comando. Activa los logs internos del cliente HTTP (requests, caché, reintentos):

```bash
python bcn_cli.py --debug normas sync 17
```

Sin el flag, solo se muestran warnings relevantes (como normas con ID inválido). Los logs de nivel INFO quedan silenciados.

### API REST

```bash
uvicorn api:app --reload
```

Swagger UI disponible en `http://localhost:8000/docs`.

## Arquitectura

```
BCN (web service)
      |
      v
BCNClient (bcn_client.py)           — HTTP, caché, reintentos, rate limiting
      |
      v
BCNXMLParser (utils/norm_parser.py) — lxml, extracción de metadatos, conversión a Markdown
      |
      v
Managers (managers/)                — NormsManager, InstitutionManager, TiposNormasManager
      |
      v
PostgreSQL (Docker)                 — FTS en español, índices GIN, hash MD5 para detección de cambios

Interfaces: TUI (bcn_tui.py) · CLI (bcn_cli.py) · REST API (api.py)
```

## Estado del proyecto

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 — MVP | CLI, extracción, almacenamiento, Docker | Completada |
| 2 — Optimización | Caché, rate limiting, reintentos, benchmarks | Completada |
| 3 — TUI | Interfaz de terminal, sync interactivo, lector de normas | Completada |
| 4 — API | FastAPI, OpenAPI, búsqueda avanzada | En desarrollo |
| 5 — Frontend | Web UI, visualización de relaciones | Pendiente |

## Estructura del proyecto

```
BCNExtractor/
├── bcn_client.py           # Cliente HTTP para la BCN
├── bcn_tui.py              # TUI (interfaz de terminal)
├── bcn_cli.py              # Entry point de la CLI
├── api.py                  # API REST (FastAPI)
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── cli/                    # Lógica de la CLI
│   ├── main.py             # Registro de comandos (Typer)
│   ├── output.py           # Presentación con Rich
│   ├── console.py          # Instancia compartida de Console
│   ├── _internal.py        # Conexión y managers compartidos
│   └── commands/
│       ├── normas.py       # list, get, sync, search
│       ├── instituciones.py# list, get, load
│       └── sistema.py      # init, stats, cache
├── managers/
│   ├── institutions.py
│   ├── norms.py
│   ├── norms_types.py
│   └── downloads.py
├── loaders/
│   └── institutions.py
├── utils/
│   ├── norm_parser.py
│   └── db_logger.py
└── data/
    ├── instituciones.csv
    └── xml/
```

## Licencia

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — uso no comercial, con atribución y compartir igual. Para uso comercial: [ftb2570@gmail.com](mailto:ftb2570@gmail.com).
