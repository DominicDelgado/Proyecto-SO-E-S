"""
Módulo de Visualización y Generación de Reportes.

Este módulo genera:
1. Tabla de reemplazo por tiempo (estado de marcos)
2. Gráficas comparativas (matplotlib)
3. Informe automático en Markdown

Visualizaciones generadas:
--------------------------
1. page_faults_comparison.png - Comparación de page faults
2. hit_ratio_comparison.png - Comparación de hit ratio
3. execution_time_comparison.png - Comparación de tiempos
4. combined_metrics.png - Dashboard con múltiples métricas

Informe generado:
-----------------
- simulation_report.md - Informe completo en Markdown

Autor: Proyecto Académico - Sistemas Operativos
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Importación condicional de matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Advertencia: matplotlib no disponible. Las gráficas no se generarán.")

from core.metrics import SimulationMetrics, MetricsComparator


class ReplacementTableGenerator:
    """
    Generador de tablas de reemplazo.

    Crea tablas que muestran el estado de los marcos en cada
    instante de tiempo, similar a las tablas clásicas de
    algoritmos de reemplazo de página.

    Formato de tabla:
    -----------------
    | Tiempo | Página | Marco 0 | Marco 1 | ... | Fault |
    |--------|--------|---------|---------|-----|-------|
    |   1    |   7    |    7    |    -    | ... |   F   |
    |   2    |   0    |    7    |    0    | ... |   F   |
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el generador.

        Args:
            num_frames: Número de marcos a mostrar
        """
        self._num_frames = num_frames
        self._history: List[Dict[str, Any]] = []

    def record_state(
        self,
        time_step: int,
        page_accessed: int,
        frame_state: List[Optional[int]],
        is_fault: bool,
        victim_frame: Optional[int] = None
    ) -> None:
        """
        Registra el estado en un instante de tiempo.

        Args:
            time_step: Número de paso de tiempo
            page_accessed: Página accedida
            frame_state: Estado actual de los marcos [page_id o None]
            is_fault: Si ocurrió page fault
            victim_frame: Marco víctima (si hubo reemplazo)
        """
        self._history.append({
            'time': time_step,
            'page': page_accessed,
            'frames': frame_state.copy(),
            'fault': is_fault,
            'victim': victim_frame
        })

    def generate_table(self, max_rows: Optional[int] = None) -> str:
        """
        Genera la tabla en formato texto.

        Args:
            max_rows: Máximo de filas a mostrar (None = todas)

        Returns:
            Tabla formateada como string
        """
        if not self._history:
            return "No hay datos de reemplazo registrados."

        rows = self._history[:max_rows] if max_rows else self._history

        # Encabezado
        header = ["Tiempo", "Página"]
        for i in range(self._num_frames):
            header.append(f"Marco {i}")
        header.append("Fault")

        # Calcular anchos de columna
        widths = [max(len(h), 6) for h in header]

        # Construir tabla
        lines = []

        # Línea de encabezado
        header_line = " | ".join(h.center(widths[i]) for i, h in enumerate(header))
        lines.append(header_line)
        lines.append("-" * len(header_line))

        # Filas de datos
        for row in rows:
            cells = [
                str(row['time']).center(widths[0]),
                str(row['page']).center(widths[1])
            ]

            for i, frame_val in enumerate(row['frames']):
                if frame_val is None:
                    cell = "-"
                else:
                    cell = str(frame_val)
                    # Marcar víctima con asterisco
                    if row['victim'] == i and row['fault']:
                        cell = f"*{cell}"
                cells.append(cell.center(widths[i + 2]))

            fault_mark = "F" if row['fault'] else ""
            cells.append(fault_mark.center(widths[-1]))

            lines.append(" | ".join(cells))

        if max_rows and len(self._history) > max_rows:
            lines.append(f"... ({len(self._history) - max_rows} filas más)")

        return "\n".join(lines)

    def generate_markdown_table(self, max_rows: Optional[int] = None) -> str:
        """
        Genera la tabla en formato Markdown.

        Args:
            max_rows: Máximo de filas

        Returns:
            Tabla en formato Markdown
        """
        if not self._history:
            return "No hay datos registrados."

        rows = self._history[:max_rows] if max_rows else self._history

        # Encabezado
        header = ["Tiempo", "Página"]
        for i in range(self._num_frames):
            header.append(f"M{i}")
        header.append("Fault")

        lines = []
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")

        for row in rows:
            cells = [str(row['time']), str(row['page'])]

            for i, frame_val in enumerate(row['frames']):
                if frame_val is None:
                    cell = "-"
                else:
                    cell = str(frame_val)
                cells.append(cell)

            cells.append("F" if row['fault'] else "")
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def clear(self) -> None:
        """Limpia el historial."""
        self._history.clear()


class ChartGenerator:
    """
    Generador de gráficas comparativas usando matplotlib.

    Genera gráficas de barras y líneas para comparar
    el rendimiento de diferentes algoritmos.
    """

    def __init__(self, output_dir: str = "reports"):
        """
        Inicializa el generador.

        Args:
            output_dir: Directorio de salida para las gráficas
        """
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_page_faults_chart(
        self,
        results: Dict[str, SimulationMetrics],
        filename: str = "page_faults_comparison.png"
    ) -> Optional[str]:
        """
        Genera gráfica de comparación de page faults.

        Args:
            results: Diccionario de algoritmo -> métricas
            filename: Nombre del archivo de salida

        Returns:
            Ruta del archivo generado, o None si falla
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        algorithms = list(results.keys())
        faults = [results[alg].page_faults for alg in algorithms]

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.cm.Set3(range(len(algorithms)))
        bars = ax.bar(algorithms, faults, color=colors, edgecolor='black')

        ax.set_xlabel('Algoritmo', fontsize=12)
        ax.set_ylabel('Page Faults', fontsize=12)
        ax.set_title('Comparación de Page Faults por Algoritmo', fontsize=14, fontweight='bold')

        # Añadir valores sobre las barras
        for bar, fault in zip(bars, faults):
            height = bar.get_height()
            ax.annotate(f'{fault}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=10)

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        filepath = os.path.join(self._output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filepath

    def generate_hit_ratio_chart(
        self,
        results: Dict[str, SimulationMetrics],
        filename: str = "hit_ratio_comparison.png"
    ) -> Optional[str]:
        """
        Genera gráfica de comparación de hit ratio.

        Args:
            results: Diccionario de algoritmo -> métricas
            filename: Nombre del archivo

        Returns:
            Ruta del archivo
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        algorithms = list(results.keys())
        hit_ratios = [results[alg].hit_ratio * 100 for alg in algorithms]

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.cm.Paired(range(len(algorithms)))
        bars = ax.bar(algorithms, hit_ratios, color=colors, edgecolor='black')

        ax.set_xlabel('Algoritmo', fontsize=12)
        ax.set_ylabel('Hit Ratio (%)', fontsize=12)
        ax.set_title('Comparación de Hit Ratio por Algoritmo', fontsize=14, fontweight='bold')
        ax.set_ylim(0, 100)

        # Añadir valores
        for bar, ratio in zip(bars, hit_ratios):
            height = bar.get_height()
            ax.annotate(f'{ratio:.2f}%',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=10)

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        filepath = os.path.join(self._output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filepath

    def generate_execution_time_chart(
        self,
        results: Dict[str, SimulationMetrics],
        filename: str = "execution_time_comparison.png"
    ) -> Optional[str]:
        """
        Genera gráfica de tiempos de ejecución.

        Args:
            results: Diccionario de algoritmo -> métricas
            filename: Nombre del archivo

        Returns:
            Ruta del archivo
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        algorithms = list(results.keys())
        times = [results[alg].total_time_seconds * 1000 for alg in algorithms]  # ms

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.cm.cool(range(len(algorithms)))
        bars = ax.bar(algorithms, times, color=colors, edgecolor='black')

        ax.set_xlabel('Algoritmo', fontsize=12)
        ax.set_ylabel('Tiempo de Ejecución (ms)', fontsize=12)
        ax.set_title('Comparación de Tiempos de Ejecución', fontsize=14, fontweight='bold')

        for bar, t in zip(bars, times):
            height = bar.get_height()
            ax.annotate(f'{t:.2f}ms',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        filepath = os.path.join(self._output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filepath

    def generate_combined_dashboard(
        self,
        results: Dict[str, SimulationMetrics],
        filename: str = "combined_metrics.png"
    ) -> Optional[str]:
        """
        Genera dashboard combinado con múltiples métricas.

        Args:
            results: Diccionario de algoritmo -> métricas
            filename: Nombre del archivo

        Returns:
            Ruta del archivo
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        algorithms = list(results.keys())

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Page Faults
        ax1 = axes[0, 0]
        faults = [results[alg].page_faults for alg in algorithms]
        colors = plt.cm.Set3(range(len(algorithms)))
        ax1.bar(algorithms, faults, color=colors, edgecolor='black')
        ax1.set_title('Page Faults', fontweight='bold')
        ax1.set_ylabel('Count')
        ax1.tick_params(axis='x', rotation=45)

        # 2. Hit Ratio
        ax2 = axes[0, 1]
        hit_ratios = [results[alg].hit_ratio * 100 for alg in algorithms]
        ax2.bar(algorithms, hit_ratios, color=plt.cm.Paired(range(len(algorithms))), edgecolor='black')
        ax2.set_title('Hit Ratio', fontweight='bold')
        ax2.set_ylabel('Percentage (%)')
        ax2.set_ylim(0, 100)
        ax2.tick_params(axis='x', rotation=45)

        # 3. Disk Writes
        ax3 = axes[1, 0]
        writes = [results[alg].disk_writes for alg in algorithms]
        ax3.bar(algorithms, writes, color=plt.cm.Accent(range(len(algorithms))), edgecolor='black')
        ax3.set_title('Disk Writes (Writebacks)', fontweight='bold')
        ax3.set_ylabel('Count')
        ax3.tick_params(axis='x', rotation=45)

        # 4. Execution Time
        ax4 = axes[1, 1]
        times = [results[alg].total_time_seconds * 1000 for alg in algorithms]
        ax4.bar(algorithms, times, color=plt.cm.cool(range(len(algorithms))), edgecolor='black')
        ax4.set_title('Execution Time', fontweight='bold')
        ax4.set_ylabel('Time (ms)')
        ax4.tick_params(axis='x', rotation=45)

        plt.suptitle('Dashboard Comparativo de Algoritmos de Reemplazo',
                    fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()

        filepath = os.path.join(self._output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return filepath


class ReportGenerator:
    """
    Generador de informes en formato Markdown.

    Crea un informe completo con:
    - Descripción del modelo
    - Explicación de algoritmos
    - Tabla comparativa
    - Gráficas
    - Conclusiones técnicas
    """

    def __init__(self, output_dir: str = "reports"):
        """
        Inicializa el generador.

        Args:
            output_dir: Directorio de salida
        """
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_report(
        self,
        results: Dict[str, SimulationMetrics],
        config: Dict[str, Any],
        chart_paths: Dict[str, str],
        filename: str = "simulation_report.md"
    ) -> str:
        """
        Genera el informe completo en Markdown.

        Args:
            results: Resultados de simulación por algoritmo
            config: Configuración de la simulación
            chart_paths: Rutas a las gráficas generadas
            filename: Nombre del archivo de salida

        Returns:
            Ruta del archivo generado
        """
        lines = []

        # Título
        lines.append("# Informe de Simulación: Algoritmos de Reemplazo de Página")
        lines.append("")
        lines.append(f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Tabla de contenidos
        lines.append("## Tabla de Contenidos")
        lines.append("1. [Descripción del Modelo](#descripción-del-modelo)")
        lines.append("2. [Algoritmos Implementados](#algoritmos-implementados)")
        lines.append("3. [Configuración de Simulación](#configuración-de-simulación)")
        lines.append("4. [Resultados Comparativos](#resultados-comparativos)")
        lines.append("5. [Gráficas](#gráficas)")
        lines.append("6. [Conclusiones Técnicas](#conclusiones-técnicas)")
        lines.append("")

        # Sección 1: Descripción del modelo
        lines.append("## Descripción del Modelo")
        lines.append("")
        lines.append(self._get_model_description())
        lines.append("")

        # Sección 2: Algoritmos
        lines.append("## Algoritmos Implementados")
        lines.append("")
        lines.append(self._get_algorithms_description())
        lines.append("")

        # Sección 3: Configuración
        lines.append("## Configuración de Simulación")
        lines.append("")
        lines.append("| Parámetro | Valor |")
        lines.append("|-----------|-------|")
        for key, value in config.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

        # Sección 4: Resultados
        lines.append("## Resultados Comparativos")
        lines.append("")
        lines.append(self._generate_comparison_table(results))
        lines.append("")

        # Sección 5: Gráficas
        lines.append("## Gráficas")
        lines.append("")
        for name, path in chart_paths.items():
            if path:
                # Usar ruta relativa
                rel_path = os.path.basename(path)
                lines.append(f"### {name}")
                lines.append(f"![{name}]({rel_path})")
                lines.append("")

        # Sección 6: Conclusiones
        lines.append("## Conclusiones Técnicas")
        lines.append("")
        lines.append(self._generate_conclusions(results, config))

        # Escribir archivo
        content = "\n".join(lines)
        filepath = os.path.join(self._output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return filepath

    def _get_model_description(self) -> str:
        """Genera la descripción formal del modelo."""
        return """
### Modelo de Memoria Virtual

El simulador implementa un modelo de memoria virtual con las siguientes características:

**Definición Formal:**
- Sea **P** = {p₀, p₁, ..., pₙ₋₁} el conjunto de páginas virtuales
- Sea **M** = {m₀, m₁, ..., mₖ₋₁} el conjunto de marcos de página (k < n)
- Sea **f: P → M ∪ {∅}** la función de mapeo página-marco

**Eventos del Sistema:**
1. **Page Hit:** La página solicitada está en memoria (f(p) ≠ ∅)
2. **Page Fault:** La página no está en memoria (f(p) = ∅)
   - Genera interrupción de hardware
   - Invoca llamada al sistema para carga

**Bits de Control:**
- **Bit R (Reference):** Indica acceso reciente, limpiado periódicamente
- **Bit M (Modified/Dirty):** Indica escritura, requiere writeback antes de reemplazo
"""

    def _get_algorithms_description(self) -> str:
        """Genera las descripciones de los algoritmos."""
        return """
### FIFO (First-In First-Out)
- **Complejidad:** O(1) selección, O(1) actualización, O(n) espacio
- **Principio:** Reemplaza la página más antigua
- **Limitación:** Anomalía de Belady

### OPT (Óptimo de Belady)
- **Complejidad:** O(n×m) selección (n marcos, m accesos futuros)
- **Principio:** Reemplaza la página que se usará más tarde
- **Nota:** Benchmark teórico, no implementable en práctica

### LRU (Least Recently Used)
- **Complejidad:** O(1) selección y actualización con estructuras adecuadas
- **Principio:** Explota localidad temporal
- **Ventaja:** Buen rendimiento en cargas con localidad

### LFU (Least Frequently Used)
- **Complejidad:** O(n) selección, O(1) actualización
- **Principio:** Reemplaza página con menor frecuencia de acceso
- **Limitación:** Páginas "viejas" con frecuencia histórica alta

### MFU (Most Frequently Used)
- **Complejidad:** O(n) selección, O(1) actualización
- **Principio:** Inverso de LFU
- **Uso:** Patrones donde frecuencia alta indica "trabajo completado"

### Clock (Reloj)
- **Complejidad:** O(1) amortizado, O(n) peor caso
- **Principio:** Aproximación de LRU con bit R
- **Ventaja:** Eficiente en hardware, ampliamente usado

### Segunda Oportunidad
- **Complejidad:** O(2n) peor caso
- **Principio:** Clock mejorado considerando bits R y M
- **Ventaja:** Minimiza I/O prefiriendo páginas limpias

### NRU (Not Recently Used)
- **Complejidad:** O(n) selección
- **Principio:** Clasificación en 4 clases por bits R y M
- **Característica:** Selección aleatoria dentro de clase
"""

    def _generate_comparison_table(self, results: Dict[str, SimulationMetrics]) -> str:
        """Genera la tabla comparativa en Markdown."""
        lines = []
        lines.append("| Algoritmo | Page Faults | Hit Ratio | Fault Rate | Disk Writes | Tiempo (s) | Interrupciones | Syscalls |")
        lines.append("|-----------|-------------|-----------|------------|-------------|------------|----------------|----------|")

        for alg, metrics in results.items():
            lines.append(
                f"| {alg} | {metrics.page_faults} | "
                f"{metrics.hit_ratio*100:.2f}% | {metrics.fault_rate*100:.2f}% | "
                f"{metrics.disk_writes} | {metrics.total_time_seconds:.4f} | "
                f"{metrics.interrupts} | {metrics.syscalls} |"
            )

        return "\n".join(lines)

    def _generate_conclusions(
        self,
        results: Dict[str, SimulationMetrics],
        config: Dict[str, Any]
    ) -> str:
        """Genera las conclusiones técnicas."""
        # Encontrar mejores algoritmos
        best_hit = max(results.items(), key=lambda x: x[1].hit_ratio)
        best_faults = min(results.items(), key=lambda x: x[1].page_faults)
        best_writes = min(results.items(), key=lambda x: x[1].disk_writes)
        best_time = min(results.items(), key=lambda x: x[1].total_time_seconds)

        pattern = config.get('access_pattern', 'desconocido')

        return f"""
### Mejor Rendimiento General

- **Menor Page Faults:** {best_faults[0]} ({best_faults[1].page_faults} faults)
- **Mayor Hit Ratio:** {best_hit[0]} ({best_hit[1].hit_ratio*100:.2f}%)
- **Menos Escrituras a Disco:** {best_writes[0]} ({best_writes[1].disk_writes} writes)
- **Menor Tiempo de Ejecución:** {best_time[0]} ({best_time[1].total_time_seconds:.4f}s)

### Análisis por Patrón de Acceso

**Patrón utilizado:** {pattern}

- Para patrones con **alta localidad**, LRU y sus aproximaciones (Clock, Segunda Oportunidad)
  generalmente superan a FIFO.
- **OPT** sirve como benchmark teórico del mínimo posible de page faults.
- Algoritmos basados en **frecuencia** (LFU/MFU) pueden rendir mal con patrones cambiantes.

### Impacto en Sistemas Reales

1. **Overhead de I/O:** Las escrituras a disco (writebacks) son costosas.
   Algoritmos como Segunda Oportunidad que consideran el bit M reducen este costo.

2. **Complejidad de Implementación:**
   - LRU puro requiere actualizar estructuras en cada acceso
   - Clock y NRU son aproximaciones eficientes usadas en sistemas reales

3. **Anomalía de Belady:** FIFO puede exhibir comportamiento donde más memoria = más faults.

### Recomendaciones

- **Para sistemas de propósito general:** Clock o Segunda Oportunidad
- **Para workloads con alta localidad:** LRU o aproximaciones
- **Para minimizar I/O:** Segunda Oportunidad (considera bit M)
"""


def generate_all_visualizations(
    results: Dict[str, SimulationMetrics],
    config: Dict[str, Any],
    output_dir: str = "reports"
) -> Dict[str, str]:
    """
    Genera todas las visualizaciones y el informe.

    Args:
        results: Resultados de todos los algoritmos
        config: Configuración de la simulación
        output_dir: Directorio de salida

    Returns:
        Diccionario con rutas de archivos generados
    """
    generated_files = {}

    # Generar gráficas
    chart_gen = ChartGenerator(output_dir)

    chart_paths = {}
    chart_paths['Page Faults'] = chart_gen.generate_page_faults_chart(results)
    chart_paths['Hit Ratio'] = chart_gen.generate_hit_ratio_chart(results)
    chart_paths['Tiempo de Ejecución'] = chart_gen.generate_execution_time_chart(results)
    chart_paths['Dashboard Combinado'] = chart_gen.generate_combined_dashboard(results)

    generated_files['charts'] = {k: v for k, v in chart_paths.items() if v}

    # Generar informe
    report_gen = ReportGenerator(output_dir)
    report_path = report_gen.generate_report(results, config, chart_paths)
    generated_files['report'] = report_path

    return generated_files
