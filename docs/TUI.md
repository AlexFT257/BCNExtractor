# Interfaz de Terminal (TUI)

`bcn_tui.py` es la interfaz interactiva de BCN Extractor. Permite navegar instituciones, consultar normas almacenadas, sincronizar desde la BCN y leer el texto completo de cualquier norma, todo desde la terminal y sin tocar la CLI.

## Requisitos

La TUI necesita `textual` y `rich` además de las dependencias base del proyecto:

```bash
pip install textual rich
```

La base de datos debe estar activa antes de iniciar:

```bash
docker-compose up -d
python bcn_cli.py init   # solo la primera vez
```

## Inicio

```bash
python bcn_tui.py
```

Al arrancar, la TUI verifica la conexión a PostgreSQL. Si no puede conectar, muestra el error y termina sin abrir la interfaz.

## Atajos de teclado

| Tecla | Acción |
|-------|--------|
| `1` | Ir a la pestaña Normas |
| `2` | Ir a la pestaña Dashboard |
| `3` | Ir a la pestaña Logs |
| `/` | Enfocar el filtro de instituciones |
| `s` | Sincronizar la institución seleccionada |
| `r` | Leer texto completo de la norma seleccionada |
| `Esc` | Cerrar modal activo / cancelar sync en progreso |
| `q` | Salir de la aplicación |

---

## Pestañas

### 1 — Normas

Vista principal. Está dividida en tres paneles horizontales.

**Panel izquierdo — Instituciones**

Lista todas las instituciones cargadas en la base de datos. Escribir en el campo de búsqueda filtra la lista en tiempo real por nombre. Al seleccionar una institución, el panel central se actualiza con sus normas.

**Panel central — Tabla de normas**

Muestra las normas almacenadas en la base de datos para la institución activa, ordenadas por fecha de publicación descendente. Las columnas son:

| Columna | Descripción |
|---------|-------------|
| ID | Identificador BCN de la norma |
| Tipo | Tipo normativo (Ley, Decreto, Resolución, etc.) |
| Número | Número de la norma |
| Título | Título abreviado |
| Fecha | Fecha de publicación |
| Estado | `vigente` (verde) o `derogada` (rojo) |

Al seleccionar una fila, el panel derecho muestra el detalle completo.

**Panel derecho — Detalle**

Muestra los metadatos completos de la norma seleccionada: tipo, número, fechas de publicación y promulgación, estado, organismo, instituciones relacionadas y materias. Incluye dos botones:

- **Leer texto completo** — abre el lector de Markdown con el contenido de la norma.
- **Abrir en BCN** — abre la norma directamente en `leychile.cl` en el navegador del sistema.

---

### 2 — Dashboard

Estadísticas generales de la base de datos local, actualizadas cada vez que se entra a la pestaña. Incluye:

- Total de normas, vigentes y derogadas (con porcentaje).
- Total de instituciones, cuántas tienen normas y cuántas no.
- Operaciones de los últimos 7 días, desglosadas por estado (`exitosa`, `error`, etc.).
- Distribución de normas por tipo, con barra de proporción visual.
- Últimos 5 errores registrados.

---

### 3 — Logs

Registro en tiempo real de las acciones realizadas durante la sesión: cambios de institución, errores de carga, resultados de sync. Los mensajes usan color para distinguir tipos de evento:

- Cian — navegación (institución seleccionada)
- Verde / cyan / tenue — resultado de sync por norma (`nueva`, `actualizada`, `sin_cambios`)
- Rojo — errores

---

## Modal de sincronización

Se activa con `s` o el botón "Sincronizar" cuando hay una institución seleccionada.

El proceso corre en un thread separado para no bloquear la interfaz. Para cada norma de la institución:

1. Descarga el XML desde el servicio web de la BCN.
2. Lo parsea con `BCNXMLParser` para extraer metadatos y convertirlo a Markdown.
3. Guarda la norma con `NormsManager.save()`, que detecta si es nueva, actualizada o sin cambios.
4. Registra el resultado en `DBLogger`.

Durante el proceso se muestra una barra de progreso con ETA y un log de actividad por norma.

**Estados posibles por norma:**

| Estado | Significado |
|--------|-------------|
| `nueva` | La norma no existía en la base de datos |
| `actualizada` | El XML cambió respecto a la descarga anterior |
| `sin_cambios` | El hash MD5 del XML coincide; no se reescribe |
| error | No se pudo descargar o procesar |

Al terminar, el botón "Cancelar" cambia a "Cerrar". Presionar `Esc` durante el sync lo cancela; presionar `Esc` una vez terminado cierra el modal.

Después de cerrar, la tabla de normas se recarga automáticamente con los datos nuevos.

---

## Modal lector

Se activa con `r` o el botón "Leer texto completo" cuando hay una norma seleccionada.

Muestra el archivo Markdown de la norma generado durante el sync. Si el archivo no existe (la norma fue indexada pero no descargada), muestra un aviso indicando que hay que ejecutar sync.

Cerrar con `Esc`, `q` o el botón "Cerrar".

---

## Arquitectura interna

La TUI no contiene lógica de negocio ni queries SQL directas. Delega completamente en los managers del proyecto:

| Operación | Manager |
|-----------|---------|
| Listar instituciones | `InstitutionManager.get_all()` |
| Normas de una institución | `NormsManager.get_by_institucion()` |
| Detalle de una norma | `NormsManager.get_by_id()` |
| Estadísticas de normas | `NormsManager.get_stats()` |
| Estadísticas de instituciones | `InstitutionManager.get_stats()` |
| Estadísticas de operaciones | `DBLogger.get_stats()` |
| Guardar norma sincronizada | `NormsManager.save()` |
| Registrar operación | `DBLogger.log()` |

Todos los managers comparten una única conexión a PostgreSQL por operación, que se abre y cierra en cada llamada.
