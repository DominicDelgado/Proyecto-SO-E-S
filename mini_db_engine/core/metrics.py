"""
Recolector y Analizador de Métricas.

Este módulo implementa la recolección exhaustiva de métricas
de rendimiento para la simulación del sistema de memoria virtual.

Métricas obligatorias:
----------------------
1. Total de accesos
2. Total de page faults
3. Page fault rate (faults / accesos)
4. Hit ratio (hits / accesos)
5. Tiempo total de ejecución
6. Tiempo promedio por acceso
7. Uso de memoria
8. Estimación de uso de CPU
9. Cantidad de interrupciones simuladas
10. Cantidad de llamadas al sistema
11. Número total de escrituras a disco

Modelo de métricas:
-------------------
Las métricas se organizan en categorías:
- Rendimiento: hit ratio, fault rate, tiempos
- I/O: lecturas/escrituras de disco
- Sistema: interrupciones, syscalls
- Recursos: memoria, CPU estimado

Fórmulas:
---------
- Hit Ratio = (total_accesses - page_faults) / total_accesses
- Page Fault Rate = page_faults / total_accesses
- Avg Time per Access = total_time / total_accesses
- Estimated CPU Usage = (non_io_time / total_time) * 100

Autor: Proyecto Académico - Sistemas Operativos
"""

import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum, auto
import statistics


class MetricCategory(Enum):
    """Categorías de métricas."""
    PERFORMANCE = auto()
    IO = auto()
    SYSTEM = auto()
    RESOURCES = auto()


@dataclass
class SimulationMetrics:
    """
    Estructura que almacena todas las métricas de una simulación.

    Esta clase se serializa para generar reportes y comparaciones.

    Attributes:
        algorithm_name: Nombre del algoritmo usado
        num_frames: Número de marcos del buffer pool
        total_pages: Número total de páginas
        num_accesses: Número de accesos realizados
        access_pattern: Patrón de acceso utilizado

        # Métricas de rendimiento
        page_faults: Total de page faults
        page_hits: Total de page hits
        hit_ratio: Ratio de hits (0.0 - 1.0)
        fault_rate: Ratio de faults (0.0 - 1.0)

        # Métricas de tiempo
        total_time_seconds: Tiempo total de simulación
        avg_time_per_access_us: Tiempo promedio por acceso (microsegundos)

        # Métricas de I/O
        disk_reads: Total de lecturas de disco
        disk_writes: Total de escrituras de disco (writebacks)

        # Métricas de sistema
        interrupts: Interrupciones de page fault
        syscalls: Llamadas al sistema

        # Métricas de recursos
        memory_peak_mb: Pico de uso de memoria (MB)
        memory_current_mb: Uso actual de memoria (MB)
        estimated_cpu_percent: Estimación de uso de CPU
    """
    # Identificación
    algorithm_name: str = ""
    num_frames: int = 0
    total_pages: int = 0
    num_accesses: int = 0
    access_pattern: str = ""

    # Rendimiento
    page_faults: int = 0
    page_hits: int = 0
    hit_ratio: float = 0.0
    fault_rate: float = 0.0

    # Tiempos
    total_time_seconds: float = 0.0
    avg_time_per_access_us: float = 0.0

    # I/O
    disk_reads: int = 0
    disk_writes: int = 0

    # Sistema
    interrupts: int = 0
    syscalls: int = 0

    # Recursos
    memory_peak_mb: float = 0.0
    memory_current_mb: float = 0.0
    estimated_cpu_percent: float = 0.0

    # Metadatos adicionales
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para serialización."""
        return {
            'algorithm_name': self.algorithm_name,
            'num_frames': self.num_frames,
            'total_pages': self.total_pages,
            'num_accesses': self.num_accesses,
            'access_pattern': self.access_pattern,
            'page_faults': self.page_faults,
            'page_hits': self.page_hits,
            'hit_ratio': self.hit_ratio,
            'fault_rate': self.fault_rate,
            'total_time_seconds': self.total_time_seconds,
            'avg_time_per_access_us': self.avg_time_per_access_us,
            'disk_reads': self.disk_reads,
            'disk_writes': self.disk_writes,
            'interrupts': self.interrupts,
            'syscalls': self.syscalls,
            'memory_peak_mb': self.memory_peak_mb,
            'memory_current_mb': self.memory_current_mb,
            'estimated_cpu_percent': self.estimated_cpu_percent,
            'metadata': self.metadata
        }


class MetricsCollector:
    """
    Recolector de métricas en tiempo real.

    Acumula métricas durante la simulación y calcula
    estadísticas derivadas al finalizar.

    Uso:
    1. Crear instancia al inicio de simulación
    2. Llamar record_*() durante la simulación
    3. Llamar finalize() al terminar
    4. Obtener métricas con get_metrics()

    Tracking de memoria:
    - Usa tracemalloc para medir uso de memoria
    - Captura pico y uso actual

    Attributes:
        _start_time: Timestamp de inicio
        _end_time: Timestamp de fin
        _metrics: Métricas acumuladas
        _access_times: Tiempos individuales de acceso
    """

    def __init__(self):
        """Inicializa el recolector de métricas."""
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

        # Contadores
        self._total_accesses: int = 0
        self._page_faults: int = 0
        self._page_hits: int = 0
        self._disk_reads: int = 0
        self._disk_writes: int = 0
        self._interrupts: int = 0
        self._syscalls: int = 0

        # Tiempos de acceso individuales
        self._access_times: List[float] = []
        self._last_access_start: Optional[float] = None

        # Estado de tracking de memoria
        self._memory_tracking_enabled: bool = False

        # Identificación
        self._algorithm_name: str = ""
        self._num_frames: int = 0
        self._total_pages: int = 0
        self._access_pattern: str = ""

    def start(
        self,
        algorithm_name: str,
        num_frames: int,
        total_pages: int,
        access_pattern: str
    ) -> None:
        """
        Inicia la recolección de métricas.

        Debe llamarse antes de comenzar la simulación.

        Args:
            algorithm_name: Nombre del algoritmo
            num_frames: Número de marcos
            total_pages: Total de páginas
            access_pattern: Patrón de acceso
        """
        # Guardar identificación
        self._algorithm_name = algorithm_name
        self._num_frames = num_frames
        self._total_pages = total_pages
        self._access_pattern = access_pattern

        # Reiniciar contadores
        self._total_accesses = 0
        self._page_faults = 0
        self._page_hits = 0
        self._disk_reads = 0
        self._disk_writes = 0
        self._interrupts = 0
        self._syscalls = 0
        self._access_times.clear()

        # Iniciar tracking de memoria
        try:
            tracemalloc.start()
            self._memory_tracking_enabled = True
        except Exception:
            self._memory_tracking_enabled = False

        # Registrar inicio
        self._start_time = time.perf_counter()
        self._end_time = None

    def record_access(self) -> None:
        """Registra un acceso a página."""
        self._total_accesses += 1
        self._last_access_start = time.perf_counter()

    def record_access_complete(self) -> None:
        """Registra finalización de un acceso."""
        if self._last_access_start is not None:
            elapsed = time.perf_counter() - self._last_access_start
            self._access_times.append(elapsed)
            self._last_access_start = None

    def record_page_fault(self) -> None:
        """Registra un page fault."""
        self._page_faults += 1
        self._disk_reads += 1  # Cada fault implica lectura de disco

    def record_hit(self) -> None:
        """Registra un page hit."""
        self._page_hits += 1

    def record_disk_write(self) -> None:
        """Registra una escritura a disco (writeback)."""
        self._disk_writes += 1

    def record_interrupt(self) -> None:
        """Registra una interrupción de page fault."""
        self._interrupts += 1

    def record_syscall(self) -> None:
        """Registra una llamada al sistema."""
        self._syscalls += 1

    def finalize(self) -> SimulationMetrics:
        """
        Finaliza la recolección y calcula métricas derivadas.

        Returns:
            SimulationMetrics con todas las métricas calculadas
        """
        self._end_time = time.perf_counter()

        # Calcular métricas derivadas
        total_time = self._end_time - self._start_time if self._start_time else 0

        hit_ratio = 0.0
        fault_rate = 0.0
        avg_time_per_access = 0.0

        if self._total_accesses > 0:
            hit_ratio = self._page_hits / self._total_accesses
            fault_rate = self._page_faults / self._total_accesses
            avg_time_per_access = (total_time / self._total_accesses) * 1_000_000  # microsegundos

        # Obtener uso de memoria
        memory_current = 0.0
        memory_peak = 0.0

        if self._memory_tracking_enabled:
            try:
                current, peak = tracemalloc.get_traced_memory()
                memory_current = current / (1024 * 1024)  # MB
                memory_peak = peak / (1024 * 1024)  # MB
                tracemalloc.stop()
            except Exception:
                pass

        # Estimar uso de CPU
        # Asumimos que el tiempo no-I/O es ~90% CPU
        # (simplificación para simulación)
        estimated_cpu = 90.0 if total_time > 0 else 0.0

        # Construir métricas
        metrics = SimulationMetrics(
            algorithm_name=self._algorithm_name,
            num_frames=self._num_frames,
            total_pages=self._total_pages,
            num_accesses=self._total_accesses,
            access_pattern=self._access_pattern,
            page_faults=self._page_faults,
            page_hits=self._page_hits,
            hit_ratio=hit_ratio,
            fault_rate=fault_rate,
            total_time_seconds=total_time,
            avg_time_per_access_us=avg_time_per_access,
            disk_reads=self._disk_reads,
            disk_writes=self._disk_writes,
            interrupts=self._interrupts,
            syscalls=self._syscalls,
            memory_peak_mb=memory_peak,
            memory_current_mb=memory_current,
            estimated_cpu_percent=estimated_cpu
        )

        return metrics

    def get_current_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas actuales (sin finalizar).

        Returns:
            Diccionario con estadísticas parciales
        """
        elapsed = 0.0
        if self._start_time:
            elapsed = time.perf_counter() - self._start_time

        return {
            'total_accesses': self._total_accesses,
            'page_faults': self._page_faults,
            'page_hits': self._page_hits,
            'disk_reads': self._disk_reads,
            'disk_writes': self._disk_writes,
            'interrupts': self._interrupts,
            'syscalls': self._syscalls,
            'elapsed_time': elapsed,
            'hit_ratio': self._page_hits / self._total_accesses if self._total_accesses > 0 else 0
        }

    def reset(self) -> None:
        """Reinicia todos los contadores."""
        self._start_time = None
        self._end_time = None
        self._total_accesses = 0
        self._page_faults = 0
        self._page_hits = 0
        self._disk_reads = 0
        self._disk_writes = 0
        self._interrupts = 0
        self._syscalls = 0
        self._access_times.clear()

        if self._memory_tracking_enabled:
            try:
                tracemalloc.stop()
            except Exception:
                pass
            self._memory_tracking_enabled = False


class MetricsComparator:
    """
    Comparador de métricas entre múltiples algoritmos.

    Facilita la comparación y análisis de resultados
    de diferentes algoritmos sobre los mismos datos.
    """

    def __init__(self):
        """Inicializa el comparador."""
        self._results: Dict[str, SimulationMetrics] = {}

    def add_result(self, metrics: SimulationMetrics) -> None:
        """
        Agrega un resultado de simulación.

        Args:
            metrics: Métricas a agregar
        """
        self._results[metrics.algorithm_name] = metrics

    def get_comparison_table(self) -> List[Dict[str, Any]]:
        """
        Genera tabla comparativa de todos los algoritmos.

        Returns:
            Lista de diccionarios con métricas por algoritmo
        """
        table = []
        for name, metrics in self._results.items():
            table.append({
                'algorithm': name,
                'page_faults': metrics.page_faults,
                'hit_ratio': f"{metrics.hit_ratio * 100:.2f}%",
                'fault_rate': f"{metrics.fault_rate * 100:.2f}%",
                'disk_writes': metrics.disk_writes,
                'time_seconds': f"{metrics.total_time_seconds:.4f}",
                'interrupts': metrics.interrupts,
                'syscalls': metrics.syscalls
            })
        return table

    def get_best_algorithm(self, metric: str = 'hit_ratio') -> str:
        """
        Determina el mejor algoritmo según una métrica.

        Args:
            metric: Métrica a comparar (hit_ratio, fault_rate, etc.)

        Returns:
            Nombre del mejor algoritmo
        """
        if not self._results:
            return ""

        if metric in ['hit_ratio']:
            # Mayor es mejor
            return max(self._results.keys(),
                      key=lambda k: getattr(self._results[k], metric, 0))
        else:
            # Menor es mejor (faults, time, etc.)
            return min(self._results.keys(),
                      key=lambda k: getattr(self._results[k], metric, float('inf')))

    def get_ranking(self, metric: str = 'hit_ratio') -> List[Tuple[str, float]]:
        """
        Genera ranking de algoritmos por métrica.

        Args:
            metric: Métrica para ordenar

        Returns:
            Lista de (algoritmo, valor) ordenada
        """
        items = [
            (name, getattr(metrics, metric, 0))
            for name, metrics in self._results.items()
        ]

        # Mayor es mejor para hit_ratio, menor para el resto
        reverse = metric == 'hit_ratio'
        return sorted(items, key=lambda x: x[1], reverse=reverse)

    def get_all_results(self) -> Dict[str, SimulationMetrics]:
        """Retorna todos los resultados."""
        return self._results.copy()

    def clear(self) -> None:
        """Limpia todos los resultados."""
        self._results.clear()


# Tipo auxiliar para type hints
from typing import Tuple
