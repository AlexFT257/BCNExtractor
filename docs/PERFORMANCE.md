# Métricas de Performance

> Última actualización: Enero 2025
>
> Sistema de prueba: Ryzen 7 5700x, 32GB RAM DDR4-3200 MHz, SSD NVMe M.2

> [!NOTE]
> Estos benchmarks reflejan el mejor caso (con caché). Para sincronización inicial sin caché, los tiempos de descarga dependen completamente de la API de BCN.

## 📊 Resumen Ejecutivo

| Métrica | Valor | Notas |
|---------|-------|-------|
| **Parseo XML** | ~82µs | Conversión a Markdown |
| **Descarga norma completa** | ~225µs | Desde API BCN |
| **Descarga metadatos** | ~243µs | Solo metadata |
| **Búsqueda FTS** | ~1.1ms | Full-text search |
| **Consulta por ID** | ~459µs | Consulta indexada |


## Operaciones de Extracción (desde BCN)

### Consultas a la API de BCN

| Operación | Media | Min | Max | Throughput |
|-----------|-------|-----|-----|-----------|
| Listar normas institución | 837µs | 722µs | 1,196µs | ~1,194 ops/s |
| Descargar norma completa | 225µs | 214µs | 606µs | ~4,439 ops/s |
| Descargar solo metadatos | 243µs | 216µs | 623µs | ~4,112 ops/s |

**Observaciones:**
- Los tiempos son excepcionalmente rápidos, debido al **sistema de caché**
- Descarga completa vs metadatos tienen tiempos similares (~225µs), indicando que el caché es muy efectivo
- Rate limiting de BCN: ~1 request/segundo (cuando no hay caché)

### Procesamiento Local

| Operación | Media | Min | Max | Throughput |
|-----------|-------|-----|-----|-----------|
| Parsear XML a Markdown | 82µs | 76µs | 422µs | ~12,166 docs/s |

**Observaciones:**
- Parseo extremadamente rápido
- Baja desviación estándar (±18.8µs) indica consistencia
- El throughput teórico de ~12K docs/s es más que suficiente

## Operaciones de Base de Datos

### Lectura

| Operación | Media | Min | Max | Throughput |
|-----------|-------|-----|-----|-----------|
| Obtener norma por ID | 459µs | 389µs | 778µs | ~2,181 ops/s |
| Búsqueda full-text | 1.1ms | 991µs | 1.4ms | ~905 ops/s |
| Obtener estadísticas | 1.4ms | 1.2ms | 2.0ms | ~729 ops/s |

**Observaciones:**
- Consultas por ID muy rápidas gracias a índices
- FTS (Full-Text Search) toma ~1ms, excelente para búsquedas complejas
- Estadísticas son la operación más lenta (~1.4ms) por agregaciones

### Comparación de Performance

```
Operación más rápida:  Parseo XML           (82µs)   ████
Descarga API:          Norma completa       (225µs)  ██████
Consulta DB:           Por ID               (459µs)  ████████████
Búsqueda FTS:          Full-text            (1.1ms)  ████████████████████████████
Estadísticas:          Agregaciones         (1.4ms)  ████████████████████████████████
```

## Análisis de Performance

### Velocidad Relativa (comparado con parseo XML)

| Operación | Factor | Comparación |
|-----------|--------|-------------|
| Parseo XML | 1.0x | Baseline (más rápido) |
| Descarga completa | 2.7x | ~3x más lento |
| Descarga metadatos | 3.0x | Similar a descarga completa |
| Consulta por ID | 5.6x | Razonable para DB |
| Listar normas | 10.2x | Múltiples normas |
| Búsqueda FTS | 13.4x | Búsqueda compleja |
| Estadísticas | 16.7x | Agregaciones pesadas |

### Cuellos de Botella

**No se identificaron cuellos de botella significativos:**
- ✅ Todas las operaciones están por debajo de 2ms
- ✅ El parseo es extremadamente eficiente
- ✅ Las búsquedas FTS son rápidas incluso para corpus grandes
- ✅ El caché funciona perfectamente

### Sistema de Caché

**Efectividad del Caché:**
- Primera descarga (sin caché): ~2-3s (depende de BCN)
- Con caché: ~225µs

El sistema de caché es el componente más crítico para la performance del sistema.

## Proyecciones de Sincronización

### Escenario 1: Con Caché (Datos ya descargados)
| Cantidad | Tiempo Estimado | Operación |
|----------|----------------|-----------|
| 10 normas | ~5ms | Solo procesamiento |
| 100 normas | ~50ms | Solo procesamiento |
| 1,000 normas | ~500ms | Solo procesamiento |
| 10,000 normas | ~5s | Solo procesamiento |

### Escenario 2: Sin Caché (Primera descarga desde BCN)
| Cantidad | Tiempo Estimado | Operación |
|----------|----------------|-----------|
| 10 normas | ~30-40s | Limitado por rate limiting |
| 100 normas | ~5-8min | Limitado por rate limiting |
| 500 normas | ~25-40min | Limitado por rate limiting |
| 1,000 normas | ~50-80min | Limitado por rate limiting |

**Factor limitante:** Rate limiting de la API de BCN (~1 request/segundo)

## Optimizaciones Implementadas

### ✅ Actualmente Implementado

1. **Sistema de Caché Agresivo**
   - Acelera operaciones
   - Reduce carga en API de BCN
   - Detección de cambios por hash MD5

2. **Índices en PostgreSQL**
   - Búsqueda por ID: ~459µs
   - Full-text search optimizado
   - Índices en campos frecuentes

3. **Parser Eficiente**
   - Procesamiento ultra-rápido (~82µs)
   - Bajo uso de memoria
   - Manejo robusto de XML

### Posibles Optimizaciones Futuras

1. **Sincronización Incremental**
   - Solo descargar normas nuevas/modificadas
   - Reducir tiempo de sincronización completa

2. **Procesamiento Paralelo**
   - Workers concurrentes para parseo
   - Queue system (Celery/RQ)
   - Aprovechar CPUs multi-core

3. **Compresión de Caché**
   - Reducir espacio en disco
   - Mantener velocidad de acceso

## Conclusiones

### Fortalezas del Sistema

1. ✅ **Performance Excelente**: Todas las operaciones <2ms
2. ✅ **Caché Efectivo**: Acelera operaciones 
3. ✅ **Búsqueda Rápida**: FTS en ~1ms es muy competitivo
4. ✅ **Escalabilidad**: Puede manejar decenas de miles de normas sin problemas

### Limitaciones

1. ⚠️ **Rate Limiting Externo**: La API de BCN limita throughput
2. ⚠️ **Single-threaded**: No aprovecha paralelismo (por diseño, debido a rate limiting)
3. ℹ️ **Sincronización Inicial Lenta**: Primera carga de institución grande toma tiempo

### Recomendaciones

**Para uso en producción:**
- Ejecutar sincronizaciones en horarios de baja demanda
- Evitar sincronización de todas las instituciones/normas si no es necesario
- Mantener caché persistente entre ejecuciones
- Considerar backup de caché para recovery rápido

**Para desarrollo:**
- Usar `--limit` para pruebas rápidas
- Aprovechar el caché para iteración rápida
- Monitorear uso de memoria en sincronizaciones grandes

## Cómo Replicar estos Benchmarks

```bash
# Instalar dependencia
pip install pytest-benchmark

# Ejecutar benchmarks
pytest tests/test_performance.py --benchmark-only

# Ver benchmarks con estadísticas detalladas
pytest tests/test_performance.py --benchmark-only -v

# Guardar baseline para comparaciones futuras
pytest tests/test_performance.py --benchmark-only --benchmark-save=baseline

# Comparar con baseline después de cambios
pytest tests/test_performance.py --benchmark-only --benchmark-compare=baseline
```

## Detalles Técnicos

### Configuración de Tests
- **Warmup:** Activado (excluye primera ejecución)
- **Rounds:** Variable según operación (94-4808 iteraciones)
- **Outliers:** Detectados y reportados automáticamente
- **Estadísticas:** Min, Max, Mean, StdDev, Median, IQR, Outliers

### Entorno de Prueba
- **PostgreSQL:** 15+ con índices GIN para FTS
- **Python:** 3.9+
- **Conexión DB:** Local (sin latencia de red)
- **Caché:** Activo durante tests

