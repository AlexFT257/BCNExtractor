# DATABASE_SCHEMA.md — Esquema de Base de Datos

> Documentación del modelo de datos de **BCNExtractor**. Incluye estructura de tablas, relaciones, índices y las decisiones de diseño detrás del esquema.

---

## Diagrama de Relaciones

```
┌──────────────┐         ┌─────────────────────────────────┐         ┌────────────┐
│ tipos_normas │◄────────│              normas              │◄────────│ descargas  │
│              │  N : 1  │                                  │  N : 1  │            │
└──────────────┘         └─────────────────────────────────┘         └────────────┘
                                          ▲
                                          │  N : 1
                                          │
                         ┌─────────────────────────────────┐
                         │      normas_instituciones       │
                         └─────────────────────────────────┘
                                          │
                                          │  N : 1
                                          ▼
                         ┌─────────────────────────────────┐
                         │         instituciones           │
                         └─────────────────────────────────┘
```

La relación central es **normas ↔ instituciones**, que es muchos-a-muchos: una norma puede aplicar a varias instituciones y una institución puede tener miles de normas. Se resuelve con la tabla pivot `normas_instituciones`.

---

## Tablas

### `tipos_normas`

Catálogo de tipos de normas legales (Ley, Decreto, Resolución, etc.). Se pobla en batch durante la sincronización a partir de los metadatos que retorna la BCN.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `SERIAL` | PK | ID asignado por la BCN al tipo de norma |
| `nombre` | `TEXT` | NOT NULL, UNIQUE | Nombre completo del tipo (ej: "Ley") |
| `abreviatura` | `TEXT` | — | Forma corta usada en la BCN |
| `fecha_creacion` | `TIMESTAMP` | DEFAULT NOW() | Cuando se insertó el registro |
| `fecha_actualizacion` | `TIMESTAMP` | DEFAULT NOW() | Última modificación |

**Índices:** `idx_tipos_normas_nombre` en `nombre`, `idx_tipos_normas_abreviatura` en `abreviatura`.

---

### `instituciones`

Instituciones gubernamentales del sistema de agrupadores de la BCN. El `id` no es autogenerado: es el identificador propio que usa la BCN en sus URLs y servicios web, necesario para las llamadas a la API externa.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | PK | ID de la institución en la BCN |
| `nombre` | `TEXT` | NOT NULL | Nombre oficial de la institución |
| `fecha_agregada` | `TIMESTAMP` | — | Cuando se incorporó al sistema |
| `fecha_actualizada` | `TIMESTAMP` | — | Última actualización del registro |

---

### `normas`

Tabla central del esquema. Almacena cada norma legal descargada, tanto sus metadatos estructurados como el contenido completo.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | PK | ID de la norma en la BCN |
| `id_tipo` | `INTEGER` | FK → `tipos_normas(id)` | Tipo de norma |
| `numero` | `VARCHAR(50)` | — | Número oficial de la norma |
| `titulo` | `TEXT` | — | Título oficial; tiene índice GIN para full-text search |
| `estado` | `VARCHAR(20)` | DEFAULT `'vigente'` | `vigente` o `derogada` |
| `fecha_publicacion` | `DATE` | — | Fecha de publicación en el Diario Oficial |
| `fecha_promulgacion` | `DATE` | — | Fecha de promulgación |
| `organismo` | `TEXT` | — | Organismo que emitió la norma |
| `xml_path` | `TEXT` | — | Ruta relativa al archivo XML en disco |
| `md_path` | `TEXT` | — | Ruta relativa al archivo Markdown generado |
| `contenido_texto` | `TEXT` | — | Texto plano extraído del XML |
| `metadata_json` | `JSONB` | — | Metadatos flexibles: materias, organismos, flags |
| `hash_xml` | `VARCHAR(32)` | — | MD5 del XML descargado, para detectar cambios |
| `fecha_descarga` | `TIMESTAMP` | DEFAULT NOW() | Cuando se descargó originalmente |
| `fecha_actualizacion` | `TIMESTAMP` | — | Última actualización del contenido |

**Índices:**
- `idx_normas_tipo` en `id_tipo`
- `idx_normas_estado` en `estado`
- `idx_normas_titulo` — GIN sobre `to_tsvector('spanish', titulo)` para full-text search
- Índice GIN implícito disponible sobre `metadata_json` para consultas por claves JSONB

---

### `normas_instituciones`

Tabla pivot para la relación muchos-a-muchos entre normas e instituciones. Una norma puede estar asociada a varias instituciones y viceversa.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id_norma` | `INTEGER` | PK (compuesto), FK → `normas(id)` | ID de la norma |
| `id_institucion` | `INTEGER` | PK (compuesto), FK → `instituciones(id)` | ID de la institución |
| `fecha_asociacion` | `TIMESTAMP` | DEFAULT NOW() | Cuando se creó la asociación |

La clave primaria compuesta `(id_norma, id_institucion)` garantiza que no existan duplicados. El `INSERT ... ON CONFLICT DO NOTHING` en el código aprovecha esto para hacer upsert sin errores.

---

### `descargas`

Log de operaciones de descarga y sincronización. Registra cada intento (exitoso o fallido) para permitir trazabilidad y diagnóstico de errores.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | `SERIAL` | PK | ID autogenerado |
| `id_norma` | `INTEGER` | FK → `normas(id)` | Norma involucrada en la operación |
| `tipo_descarga` | `VARCHAR(50)` | — | Tipo de operación (`descarga`, `sincronizacion`) |
| `estado` | `VARCHAR(50)` | — | Resultado: `exitosa` o `error` |
| `fecha_intento` | `TIMESTAMP` | — | Momento de la operación |
| `error_mensaje` | `TEXT` | — | Mensaje de error si el estado es `error`; NULL si fue exitosa |

---

## Decisiones de Diseño

### IDs de la BCN como clave primaria

Las tablas `normas` e `instituciones` usan como PK el ID que asigna la BCN en sus propios servicios, en lugar de generar un `SERIAL` interno. Esto simplifica la lógica de sincronización: al descargar una norma se conoce directamente su ID y se puede hacer un upsert sin necesidad de buscar primero si ya existe por algún otro campo. También facilita la correlación con la fuente original si se necesita re-consultar algo.

### `metadata_json` como JSONB en lugar de columnas separadas

Los metadatos que retorna la BCN no son uniformes en todas las normas. Algunos documentos tienen materias, otros no; algunos son tratados internacionales, otros no. Usar una columna JSONB permite almacenar esta estructura variable sin forzar columnas nullable que en la mayoría de casos estarían vacías. Además, PostgreSQL soporta índices GIN sobre JSONB, por lo que las consultas por claves específicas dentro del campo siguen siendo eficientes.

### Almacenamiento dual: XML en disco, texto en DB

El XML original se guarda en disco (`xml_path`) como archivo de respaldo y fuente de verdad para re-parseo. El texto extraído (`contenido_texto`) y el Markdown generado (`md_path`) se mantienen separados porque sirven a finalidades distintas: el texto plano es para búsqueda, el Markdown es para lectura legible. Guardar el XML completo en la DB aumentaría el tamaño de cada row considerablemente sin beneficio de búsqueda.

### Detección de cambios con hash MD5

Antes de hacer un upsert, el sistema calcula el MD5 del XML descargado y lo compara con el `hash_xml` almacenado. Si son iguales, la operación se aborta con estado `sin_cambios`. Esto evita actualizaciones innecesarias en la DB y reduce el I/O en sincronizaciones masivas donde la mayoría de normas no han cambiado desde la última descarga.

### Tabla de log separada

Se podría haber usado un campo de estado directamente en `normas`, pero eso solo registraría el último intento. La tabla `descargas` mantiene un historial completo de operaciones, lo cual es necesario para diagnosticar problemas intermitentes (por ejemplo, un servicio de la BCN que falla esporádicamente) y para auditoría general del pipeline de extracción.

---

## Full-Text Search

La búsqueda full-text se implementa sobre el campo `titulo` usando la configuración de idioma `spanish` de PostgreSQL:

```sql
-- Índice GIN para búsqueda rápida
CREATE INDEX idx_normas_titulo
  ON normas USING gin(to_tsvector('spanish', titulo));

-- Ejemplo de query (usado en NormsManager.search)
SELECT id, titulo FROM normas
WHERE to_tsvector('spanish', titulo) @@ plainto_tsquery('spanish', 'medio ambiente')
   OR titulo ILIKE '%medio ambiente%';
```

La consulta combina FTS (que maneja stemming y stop words en español) con un fallback `ILIKE` para capturar coincidencias literales que el FTS podría no rankear. El orden de resultados es por `fecha_publicacion DESC`.

---

## Resumen de índices

| Tabla | Índice | Columna(s) | Tipo | Propósito |
|---|---|---|---|---|
| `tipos_normas` | `idx_tipos_normas_nombre` | `nombre` | B-tree | Búsqueda por nombre |
| `tipos_normas` | `idx_tipos_normas_abreviatura` | `abreviatura` | B-tree | Búsqueda por abreviatura |
| `normas` | `idx_normas_tipo` | `id_tipo` | B-tree | JOIN con tipos_normas |
| `normas` | `idx_normas_estado` | `estado` | B-tree | Filtro por vigente/derogada |
| `normas` | `idx_normas_titulo` | `titulo` | GIN (tsvector) | Full-text search |
| `normas` | — | `metadata_json` | GIN (disponible) | Consultas por claves JSONB |