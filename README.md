# BCN Extractor

> Pipeline ELT para descargar, procesar y almacenar normas legales chilenas desde la Biblioteca del Congreso Nacional (BCN).

[![Status](https://img.shields.io/badge/status-active%20development-green)](https://github.com/AlexFT257/BCNExtractor)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15+](https://img.shields.io/badge/postgresql-15+-blue.svg)](https://www.postgresql.org/)

Herramienta de código abierto pensada para investigadores, desarrolladores y organizaciones que necesiten acceso programático a la legislación chilena. Cubre el pipeline completo: extracción desde los servicios web de la BCN, parseo de XML, almacenamiento en PostgreSQL, búsqueda full-text y análisis NLP de referencias normativas.

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
python bcn_cli.py normas list 17 --limit 10               # Listar normas de una institución (consulta directa a BCN)
python bcn_cli.py normas get 206396 --md out.md           # Descargar norma como Markdown
python bcn_cli.py normas sync 17 --limit 50               # Sincronizar normas a la base de datos
python bcn_cli.py normas sync 17 --force                  # Re-sincronizar aunque no haya cambios
python bcn_cli.py normas search "medio ambiente"          # Buscar en la base de datos local
python bcn_cli.py normas metadata 206396                  # Ver metadata de una norma específica
python bcn_cli.py normas by-metadata materia "medio"      # Buscar normas por clave/valor de metadata

# Metadata
python bcn_cli.py metadata claves                         # Listar todas las claves de metadata disponibles
python bcn_cli.py metadata stats                          # Estadísticas de la tabla de metadata

# Instituciones
python bcn_cli.py instituciones list                      # Listar todas las instituciones
python bcn_cli.py instituciones list --search ministerio  # Filtrar por nombre
python bcn_cli.py instituciones get 1041                  # Ver detalle de una institución
python bcn_cli.py instituciones load data/instituciones.csv  # Cargar desde CSV

# NLP
python bcn_cli.py nlp analizar 206396                     # Analizar una norma específica
python bcn_cli.py nlp analizar-institucion 17             # Analizar todas las normas de una institución
python bcn_cli.py nlp analizar-institucion 17 --limit 50  # Limitar el batch
python bcn_cli.py nlp analizar-institucion 17 --forzar    # Re-analizar aunque ya exista análisis
python bcn_cli.py nlp resolver                            # Resolver referencias pendientes (todas)
python bcn_cli.py nlp resolver 206396                     # Resolver referencias de una norma
python bcn_cli.py nlp referencias 206396                  # Ver referencias extraídas
python bcn_cli.py nlp referencias 206396 --resueltas      # Solo las resueltas contra la DB
python bcn_cli.py nlp entidades 206396                    # Ver entidades nombradas
python bcn_cli.py nlp entidades 206396 --tipo organismo   # Filtrar por tipo
python bcn_cli.py nlp obligaciones 206396                 # Ver obligaciones detectadas
python bcn_cli.py nlp obligaciones 206396 --con-plazo     # Solo las que tienen plazo
python bcn_cli.py nlp stats                               # Estadísticas globales del análisis NLP

# Sistema
python bcn_cli.py stats                                   # Ver estadísticas
python bcn_cli.py stats --errors                          # Incluir errores recientes
python bcn_cli.py cache stats                             # Info del caché local
python bcn_cli.py cache clear                             # Limpiar caché
```

El flag `--debug` es global y puede combinarse con cualquier comando. Activa los logs internos del cliente HTTP (requests, caché, reintentos):

```bash
python bcn_cli.py --debug normas sync 17
```

Sin el flag, solo se muestran warnings relevantes (como normas con ID inválido). Los logs de nivel INFO quedan silenciados.

### Scheduler

Permite programar la sincronización automática de instituciones como un proceso independiente en background. Compatible con Windows, Mac y Linux.

```bash
# Iniciar el scheduler (retorna inmediatamente, corre en background)
python bcn_cli.py scheduler start --inst 17,42,1041

# Con horario y día específicos
python bcn_cli.py scheduler start --inst 17,42 --hora 2 --minuto 0 --dia mon-fri

# Verificar si está corriendo
python bcn_cli.py scheduler status

# Ver jobs registrados y su último estado
python bcn_cli.py scheduler list
python bcn_cli.py scheduler list --inst 17        # filtrar por institución

# Registrar o actualizar un job sin reiniciar el scheduler
python bcn_cli.py scheduler add 1041 --hora 3

# Eliminar un job por su ID (ver IDs con 'scheduler list')
python bcn_cli.py scheduler remove 2

# Detener el scheduler
python bcn_cli.py scheduler stop
```

| Opción | Descripción | Default |
|--------|-------------|---------|
| `--inst` | IDs de instituciones separados por coma | requerido |
| `--hora` | Hora de ejecución UTC (0-23) | `23` |
| `--minuto` | Minuto de ejecución (0-59) | `59` |
| `--limit` | Normas máximas por sync | `200` |
| `--gap` | Minutos de separación entre instituciones | `0` |
| `--dia` | Día(s) de la semana: `mon` `tue` `wed` `thu` `fri` `sat` `sun`. Rangos: `mon-fri`. Varios: `mon,wed,fri`. Omitir = todos los días | `None` |

Los logs del scheduler se escriben en `logs/scheduler.log`. El estado de cada ejecución (ok / error) queda registrado en la tabla `scheduler_jobs` de PostgreSQL.

### API REST

```bash
fastapi dev "./api/main.py"
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
Managers (managers/)                — NormsManager, MetadataManager, InstitutionManager,
                                      TiposNormasManager, SchedulesManager, NLPManager
      |
      v
PostgreSQL (Docker)                 — FTS en español, índices GIN, hash MD5 para detección de cambios
                                      Metadata EAV (normas_metadata), versionado histórico (normas_versiones)
                                      NLP (normas_referencias, normas_entidades, normas_obligaciones)

Interfaces: TUI (bcn_tui.py) · CLI (bcn_cli.py) · REST API (api.py) · Scheduler (scheduler_runner.py)
```

### Pipeline NLP

El análisis NLP corre como una etapa independiente y opcional después del sync. Usa el mismo XML cacheado, por lo que no genera tráfico adicional a la BCN.

```
BCNClient (caché local)
      |
      v
BCNXMLParser → Markdown
      |
      v
NLPAnalyzer (utils/nlp.py)
  ├── EntityRuler   — referencias normativas (NORMA_REF) via patrones de token
  ├── NER           — personas, organismos, lugares (es_core_news_lg)
  └── Dependencias  — obligaciones y plazos via árbol sintáctico
      |
      v
NLPManager (managers/nlp.py)
  ├── normas_referencias  — tipo, número, año, organismo, estado de resolución
  ├── normas_entidades    — entidades nombradas con tipo y posición
  └── normas_obligaciones — verbo, sujeto y plazo detectados
```

Las referencias a normas que no están en la DB local se guardan con `resolvida = false`. Al ejecutar `bcn nlp resolver` el sistema intenta vincularlas contra las normas disponibles. A medida que se sincronizan más instituciones, el grafo de relaciones se completa de forma diferida.

## Modelo de datos

### Normas (`normas`)
Tabla principal. Almacena los campos estructurados y estables de cada norma: tipo, número, título, estado, fechas, paths a XML y Markdown, hash MD5 del XML y número de versión actual.

### Metadata (`normas_metadata`)
Tabla EAV (Entity-Attribute-Value) que separa los campos descriptivos variables de la norma. Permite filtrar por clave específica con índice y absorber nuevos campos sin migración. Claves actuales: `materia`, `organismo`, `derogado`, `es_tratado`.

### Versiones (`normas_versiones`)
Historial de cambios de cada norma. Cuando el sync detecta que el XML cambió (hash MD5 distinto), archiva el estado anterior antes de sobreescribir. Permite auditar el contenido histórico de una ley. Los archivos XML y Markdown de versiones anteriores se guardan como `{id}_v{n}.xml`.

### Referencias NLP (`normas_referencias`)
Referencias a otras normas detectadas en el texto de cada ley o decreto. Incluye tipo de norma, número, año de emisión y organismo cuando están presentes. El campo `resolvida` indica si la norma referenciada existe en la DB local; `id_norma_ref` apunta a ella cuando es así.

### Entidades NLP (`normas_entidades`)
Entidades nombradas extraídas por el modelo NER: organismos, personas, lugares y fechas. Cada entrada incluye el texto original, el tipo y la frecuencia de mención.

### Obligaciones NLP (`normas_obligaciones`)
Oraciones con verbos de obligación o permisión (`deberá`, `podrá`, `se prohíbe`, etc.), con el sujeto gramatical y el plazo detectados cuando están presentes.

## Estado del proyecto

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 — MVP | CLI, extracción, almacenamiento, Docker | Completada |
| 2 — Optimización | Caché, rate limiting, reintentos, benchmarks | Completada |
| 3 — TUI | Interfaz de terminal, sync interactivo, lector de normas | Completada |
| 4 — API | FastAPI, OpenAPI, búsqueda avanzada | Completada |
| 5 — Scheduler | Sync automático programable, proceso independiente cross-platform | Completada |
| 5 — Metadata y versionado | Tabla EAV de metadata, historial de versiones, búsqueda por clave | Completada |
| 5 — NLP | Referencias normativas, NER, obligaciones y plazos | En desarrollo |

## Estructura del proyecto

```
BCNExtractor/
├── bcn_client.py           # Cliente HTTP para la BCN
├── bcn_tui.py              # TUI (interfaz de terminal)
├── bcn_cli.py              # Entry point de la CLI
├── scheduler_runner.py     # Proceso independiente del scheduler
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── cli/                    # Lógica de la CLI
│   ├── output.py           # Presentación con Rich
│   ├── console.py          # Instancia compartida de Console
│   ├── _internal.py        # Conexión y managers compartidos
│   └── commands/
│       ├── normas.py       # list, get, sync, search, metadata, by-metadata
│       ├── metadata.py     # claves, stats
│       ├── instituciones.py# list, get, load
│       ├── sistema.py      # init, stats, cache
│       ├── scheduler.py    # start, stop, status, add, remove, list
│       └── nlp.py          # analizar, analizar-institucion, resolver, referencias, entidades, obligaciones, stats
├── api/                    # Lógica de la API
│   ├── main.py             # App FastAPI + registro de routers
│   ├── dependencies.py     # Instancias compartidas (client, parser, managers)
│   └── routers/
│       ├── normas.py       # Endpoints de normas
│       └── instituciones.py# Endpoints de instituciones
│   └── services/
│       └── sync.py         # Endpoint de sync
├── managers/
│   ├── institutions.py
│   ├── norms.py            # NormsManager — CRUD de normas y versionado
│   ├── metadata.py         # MetadataManager — tabla EAV normas_metadata
│   ├── norms_types.py
│   ├── downloads.py
│   ├── schedules.py        # CRUD de scheduler_jobs
│   └── nlp.py              # NLPManager — referencias, entidades y obligaciones
├── loaders/
│   └── institutions.py
├── utils/
│   ├── norm_parser.py
│   ├── norm_types.py       # Norm (Pydantic), NormResponse — incluye to_parsed_data()
│   ├── db_logger.py
│   └── nlp.py              # Pipeline NLP: EntityRuler + NER + dependencias sintácticas
└── data/
    ├── instituciones.csv
    └── xml/
```

## Licencia

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — uso no comercial, con atribución y compartir igual. Para uso comercial: [ftb2570@gmail.com](mailto:ftb2570@gmail.com).