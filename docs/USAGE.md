# Guía de Uso

## Comandos Disponibles

### 1. Gestión de Instituciones

```bash
# Cargar instituciones desde CSV
python cli_instituciones.py load data/instituciones.csv

# Listar instituciones
python cli_instituciones.py list --limit 10

# Buscar institución
python cli_instituciones.py list --search "ministerio"

# Ver estadísticas
python cli_instituciones.py stats

# Obtener detalles de una institución
python cli_instituciones.py get 17
```

### 2. Listar Normas (sin guardar)

```bash
# Listar normas de una institución
python bcn_cli.py list 17

# Limitar resultados
python bcn_cli.py list 17 --limit 10

# Guardar lista como JSON
python bcn_cli.py list 17 --output normas.json

# Modo verbose (más detalles)
python bcn_cli.py list 17 --verbose
```

### 3. Descargar Norma Específica

```bash
# Descargar en XML
python bcn_cli.py get 206396 --output_xml norma.xml

# Descargar en Markdown
python bcn_cli.py get 206396 --output_md norma.md

# Descargar XML completo (default: metadatos)
python bcn_cli.py get 206396 --full --output_md norma.md

# Vista previa (sin guardar)
python bcn_cli.py get 206396
```

### 4. Sincronizar a Base de Datos

```bash
# Sincronizar todas las normas de una institución
python bcn_cli.py sync 17

# Limitar cantidad (útil para testing)
python bcn_cli.py sync 17 --limit 10

# Forzar re-descarga (ignorar caché)
python bcn_cli.py sync 17 --force

# Ejemplo completo
python bcn_cli.py sync 17 --limit 5 --force
```

### 5. Buscar en Base de Datos

```bash
# Búsqueda simple
python bcn_cli.py search "medio ambiente"

# Limitar resultados
python bcn_cli.py search "cinematográfica" --limit 5
```

### 6. Estadísticas del Sistema

```bash
# Ver estadísticas generales
python bcn_cli.py stats

# Incluir errores recientes
python bcn_cli.py stats --errors
```

### 7. Gestionar Caché

```bash
# Ver estadísticas de caché
python bcn_cli.py cache stats

# Limpiar caché (pide confirmación)
python bcn_cli.py cache clear

# Limpiar sin confirmación
python bcn_cli.py cache clear --force
```

## Flujos de Trabajo Comunes

### Workflow 1: Exploración Inicial

```bash
# 1. Ver qué normas tiene una institución
python bcn_cli.py list 17 --limit 5

# 2. Descargar una norma de prueba
python bcn_cli.py get 206396 --output_md test.md

# 3. Ver el markdown generado
cat test.md
```

### Workflow 2: Carga Completa

```bash
# 1. Cargar instituciones
python cli_instituciones.py load data/instituciones.csv

# 2. Sincronizar primera institución (con límite)
python bcn_cli.py sync 17 --limit 20

# 3. Verificar resultados
python bcn_cli.py stats

# 4. Buscar algo específico
python bcn_cli.py search "riego"
```

### Workflow 3: Actualización

```bash
# 1. Ver caché actual
python bcn_cli.py cache stats

# 2. Re-sincronizar forzando descarga
python bcn_cli.py sync 17 --force

# 3. Ver log de operaciones
python bcn_cli.py stats --errors
```

## Formato del CSV de Instituciones

```csv
id,nombre,tipo
17,FIA,pública
1041,Armada de Chile,pública
35,Asociación Chilena de Municipalidades,privada
```

**Campos requeridos:**
- `id` o `institucion`: ID numérico
- `nombre`: Nombre de la institución
- `tipo` (opcional): Tipo de institución

## Tips y Trucos

### 1. Testing con Límites
Siempre usa `--limit` cuando pruebes:
```bash
python bcn_cli.py sync 17 --limit 3
```

### 2. Verificar Antes de Sincronizar
```bash
python bcn_cli.py list 17 --limit 5
# Verificar que sean las normas correctas
python bcn_cli.py sync 17 --limit 5
```

### 3. Buscar ID de Institución
```bash
python cli_instituciones.py list --search "FIA"
```

### 4. Limpiar Caché Periódicamente
El caché puede crecer mucho:
```bash
python bcn_cli.py cache stats
python bcn_cli.py cache clear --force
```

### 5. Monitorear Errores
```bash
python bcn_cli.py stats --errors
```

## Solución de Problemas

### Error: "Institución no encontrada"
```bash
# Verificar que la institución esté cargada
python cli_instituciones.py list --search "nombre"

# Si no está, cargar instituciones
python cli_instituciones.py load data/instituciones.csv
```

### Error: "No se pudo descargar norma"
```bash
# Limpiar caché y reintentar
python bcn_cli.py cache clear --force
python bcn_cli.py get 206396
```

### Error de conexión a PostgreSQL
```bash
# Verificar que Docker esté corriendo
docker-compose ps

# Reiniciar servicios
docker-compose restart
```

### Base de datos vacía
```bash
# Verificar conexión
python bcn_cli.py stats

# Si falla, revisar .env y docker-compose.yml
```