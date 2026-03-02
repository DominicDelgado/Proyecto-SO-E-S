# Mini Motor de Base de Datos con Simulación Avanzada de Algoritmos de Reemplazo de Página

## Descripción

Este proyecto académico implementa un simulador completo del subsistema de memoria virtual de un sistema operativo, aplicado a un entorno de base de datos con buffer pool limitado. El simulador permite comparar el rendimiento de 8 algoritmos clásicos de reemplazo de página bajo diferentes patrones de acceso.

## Características

- **8 Algoritmos de Reemplazo**: FIFO, OPT, LRU, LFU, MFU, Clock, Segunda Oportunidad, NRU
- **6 Patrones de Acceso**: Uniforme, Localidad 80-20, Secuencial, Aleatorio, Zipf, Working Set
- **Métricas Exhaustivas**: Page faults, hit ratio, tiempo de ejecución, I/O, interrupciones, syscalls
- **Visualizaciones**: Gráficas comparativas con matplotlib
- **Reportes Automáticos**: Informe en Markdown con análisis técnico

## Estructura del Proyecto

```
mini_db_engine/
│
├── algorithms/                 # Implementación de algoritmos
│   ├── __init__.py
│   ├── base.py                # Clase base (Strategy pattern)
│   ├── fifo.py                # First-In First-Out
│   ├── opt.py                 # Óptimo de Belady
│   ├── lru.py                 # Least Recently Used
│   ├── lfu.py                 # Least Frequently Used
│   ├── mfu.py                 # Most Frequently Used
│   ├── clock.py               # Algoritmo del Reloj
│   ├── segunda_oportunidad.py # Segunda Oportunidad Mejorado
│   └── nru.py                 # Not Recently Used
│
├── core/                      # Componentes del núcleo
│   ├── __init__.py
│   ├── page.py               # Modelo de página
│   ├── buffer_pool.py        # Administrador del buffer pool
│   ├── query_generator.py    # Generador de patrones de acceso
│   └── metrics.py            # Recolector de métricas
│
├── reports/                   # Directorio de salida (generado)
│
├── visualization.py           # Generación de gráficas e informes
├── main.py                    # Programa principal
└── README.md                  # Este archivo
```

## Requisitos

- Python 3.8 o superior
- matplotlib (opcional, para gráficas)

### Instalación de dependencias

```bash
pip install matplotlib
```

## Uso

### Ejecución básica

```bash
python main.py
```

### Opciones de línea de comandos

```bash
python main.py [opciones]

Opciones:
  --frames, -f      Número de marcos en el buffer pool (default: 4)
  --pages, -p       Número total de páginas (default: 20)
  --accesses, -a    Número de accesos a simular (default: 100)
  --page-size       Tamaño de página en bytes (default: 4096)
  --algorithm       Algoritmo de reemplazo (default: lru)
  --all-algorithms  Ejecutar todos los algoritmos
  --pattern         Patrón de acceso (default: locality)
  --seed            Semilla para reproducibilidad (default: 42)
  --write-ratio     Proporción de escrituras (default: 0.3)
  --output-dir      Directorio de salida (default: reports)
  --show-table      Mostrar tabla de reemplazo
  --table-rows      Filas a mostrar en tabla (default: 20)
  --no-charts       No generar gráficas
  --quiet, -q       Modo silencioso
```

### Ejemplos

```bash
# Simulación con todos los algoritmos y patrón de localidad
python main.py --all-algorithms --pattern locality --accesses 1000

# Simulación con LRU y patrón Zipf
python main.py --algorithm lru --pattern zipf --frames 8 --pages 100

# Simulación detallada con tabla de reemplazo
python main.py --frames 4 --pages 10 --accesses 20 --show-table

# Simulación grande para benchmark
python main.py --all-algorithms --frames 16 --pages 1000 --accesses 10000
```

## Algoritmos Implementados

### 1. FIFO (First-In First-Out)
- **Complejidad**: O(1) selección, O(1) actualización
- **Principio**: Reemplaza la página que llegó primero
- **Limitación**: Anomalía de Belady

### 2. OPT (Óptimo de Belady)
- **Complejidad**: O(n×m) selección
- **Principio**: Reemplaza la página que se usará más tarde
- **Nota**: Benchmark teórico, requiere conocer el futuro

### 3. LRU (Least Recently Used)
- **Complejidad**: O(1) con estructuras adecuadas
- **Principio**: Explota localidad temporal
- **Implementación**: OrderedDict de Python

### 4. LFU (Least Frequently Used)
- **Complejidad**: O(n) selección, O(1) actualización
- **Principio**: Reemplaza la página menos accedida

### 5. MFU (Most Frequently Used)
- **Complejidad**: O(n) selección, O(1) actualización
- **Principio**: Inverso de LFU

### 6. Clock (Reloj)
- **Complejidad**: O(1) amortizado
- **Principio**: Aproximación de LRU con bit R
- **Implementación**: Estructura circular simulada

### 7. Segunda Oportunidad Mejorado
- **Complejidad**: O(2n) peor caso
- **Principio**: Clock con bits R y M
- **Ventaja**: Minimiza escrituras a disco

### 8. NRU (Not Recently Used)
- **Complejidad**: O(n) selección
- **Principio**: Clasificación en 4 clases
- **Característica**: Selección aleatoria

## Patrones de Acceso

| Patrón | Descripción | Caso de Uso |
|--------|-------------|-------------|
| `uniform` | Distribución uniforme | Peor caso para LRU |
| `locality` | 80-20 (Pareto) | Bases de datos reales |
| `sequential` | Acceso consecutivo | Table scans |
| `random` | Aleatorio puro | Testing |
| `zipf` | Distribución Zipfiana | Sistemas web |
| `working_set` | Conjunto de trabajo dinámico | Programas reales |

## Métricas Reportadas

1. **Total de accesos**
2. **Total de page faults**
3. **Page fault rate**
4. **Hit ratio**
5. **Tiempo total de ejecución**
6. **Tiempo promedio por acceso**
7. **Uso de memoria**
8. **Estimación de uso de CPU**
9. **Interrupciones simuladas**
10. **Llamadas al sistema**
11. **Escrituras a disco (writebacks)**

## Salida Esperada

```
======================================================================
                      RESUMEN DE SIMULACIÓN
======================================================================

──────────────────────────────────────────────────────────────────────
Algoritmo: LRU
──────────────────────────────────────────────────────────────────────
  Marcos:                    4
  Accesos totales:           10000
  Page Faults:               2345
  Page Hits:                 7655
  Hit Ratio:                 76.55%
  Fault Rate:                23.45%
  Tiempo ejecución:          0.2450 segundos
  Tiempo promedio/acceso:    24.50 μs
  Interrupciones simuladas:  2345
  Llamadas al sistema:       2857
  Escrituras a disco:        512
  Memoria pico:              15.32 MB
```

## Archivos Generados

El programa genera automáticamente:

- `reports/page_faults_comparison.png` - Gráfica de page faults
- `reports/hit_ratio_comparison.png` - Gráfica de hit ratio
- `reports/execution_time_comparison.png` - Gráfica de tiempos
- `reports/combined_metrics.png` - Dashboard combinado
- `reports/simulation_report.md` - Informe completo

## Modelo Teórico

### Memoria Virtual

```
Sea M = {m₀, m₁, ..., mₖ₋₁} el conjunto de marcos de página
Sea P = {p₀, p₁, ..., pₙ₋₁} el conjunto de páginas virtuales (k < n)
Sea f: P → M ∪ {∅} la función de mapeo página-marco
```

### Bits de Control

- **Bit R (Reference)**: Indica acceso reciente, limpiado periódicamente
- **Bit M (Modified)**: Indica página modificada, requiere writeback

### Eventos Simulados

1. **Page Fault**: Interrupción cuando f(p) = ∅
2. **Syscall**: Llamada al sistema para I/O
3. **Context Switch**: Cambio de contexto durante I/O (simulado)

## Principios de Diseño

- **Patrón Strategy**: Algoritmos intercambiables
- **Programación Orientada a Objetos**: Modularidad y extensibilidad
- **Documentación Formal**: Docstrings con descripción matemática
- **Métricas Exhaustivas**: Cobertura completa de indicadores

## Extensión del Proyecto

Para agregar un nuevo algoritmo:

1. Crear archivo en `algorithms/nuevo_algoritmo.py`
2. Heredar de `ReplacementAlgorithm`
3. Implementar métodos abstractos:
   - `initialize()`
   - `select_victim()`
   - `on_page_access()`
   - `on_page_load()`
   - `reset()`
   - `get_complexity()`
4. Registrar en `algorithms/__init__.py`

## Referencias Teóricas

- Tanenbaum, A. S. - "Modern Operating Systems"
- Silberschatz, A. - "Operating System Concepts"
- Denning, P. J. - "The Working Set Model for Program Behavior"
- Belady, L. A. - "A Study of Replacement Algorithms for Virtual Storage Computers"

## Licencia

Proyecto académico para fines educativos.

## Autor

Proyecto Académico - Sistemas Operativos
Universidad - Ingeniería de Sistemas / Computación
