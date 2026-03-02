"""
Buffer Pool - Administrador del Pool de Buffers en Memoria.

Este módulo implementa el buffer pool que simula la memoria principal
disponible para almacenar páginas de la base de datos.

Modelo Formal:
--------------
El Buffer Pool B se define como:
B = (F, n, A, PT)

Donde:
- F = {f₀, f₁, ..., fₙ₋₁}: conjunto de marcos de página
- n: número de marcos (capacidad del buffer)
- A: algoritmo de reemplazo
- PT: tabla de páginas

Cada marco fᵢ puede contener:
- Una página p ∈ P
- Vacío (∅)

Operaciones principales:
1. access(page_id) → (page, is_fault)
2. load(page_id, frame_idx) → page
3. evict(frame_idx) → writeback_required

Eventos simulados:
------------------
1. Page Fault (interrupción):
   - Ocurre cuando se accede a página no en memoria
   - Genera llamada al sistema para cargar página

2. Llamada al sistema (syscall):
   - read_page(): carga página desde disco
   - write_page(): escribe página modificada a disco

3. Cambio de contexto (simulado):
   - Ocurre durante I/O de disco
   - El proceso se bloquea mientras espera

Autor: Proyecto Académico - Sistemas Operativos
"""

from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum, auto
import time
import copy
import sys
import os

# Agregar el directorio padre al path para importaciones
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.page import Page, PageState, PageTable
from core.metrics import MetricsCollector
from algorithms.base import AccessType

if TYPE_CHECKING:
    from algorithms.base import ReplacementAlgorithm


class DiskIOType(Enum):
    """Tipo de operación de I/O de disco."""
    READ = auto()
    WRITE = auto()


@dataclass
class DiskOperation:
    """
    Representa una operación de I/O de disco.

    Attributes:
        io_type: Tipo de operación (READ/WRITE)
        page_id: ID de la página involucrada
        duration_ms: Duración simulada en milisegundos
        timestamp: Momento de la operación
    """
    io_type: DiskIOType
    page_id: int
    duration_ms: float
    timestamp: float


class BufferPool:
    """
    Administrador del buffer pool con simulación de eventos de SO.

    El buffer pool mantiene un conjunto fijo de marcos de página
    en memoria principal. Cuando se solicita una página que no
    está en memoria (page fault), el buffer pool:

    1. Genera una interrupción de page fault
    2. Selecciona un marco víctima usando el algoritmo de reemplazo
    3. Si la página víctima está modificada, la escribe a disco
    4. Carga la nueva página desde disco
    5. Actualiza la tabla de páginas

    Modelo de disco simulado:
    - Latencia de lectura: ~10ms (configurable)
    - Latencia de escritura: ~10ms (configurable)
    - No se simula seek time ni rotational delay

    Attributes:
        _frames: Lista de marcos (pueden contener Page o None)
        _num_frames: Número de marcos disponibles
        _algorithm: Algoritmo de reemplazo activo
        _page_table: Tabla de páginas del sistema
        _metrics: Recolector de métricas
        _frame_to_page: Mapeo rápido de marco a página
    """

    # Constantes de simulación
    DISK_READ_LATENCY_MS = 10.0   # Latencia de lectura en ms
    DISK_WRITE_LATENCY_MS = 10.0  # Latencia de escritura en ms

    def __init__(
        self,
        num_frames: int,
        algorithm: 'ReplacementAlgorithm',
        page_table: PageTable,
        metrics: MetricsCollector
    ):
        """
        Inicializa el buffer pool.

        Args:
            num_frames: Número de marcos de página disponibles
            algorithm: Algoritmo de reemplazo a utilizar
            page_table: Tabla de páginas del sistema
            metrics: Recolector de métricas

        Raises:
            ValueError: Si num_frames <= 0
        """
        if num_frames <= 0:
            raise ValueError(f"num_frames debe ser > 0: {num_frames}")

        self._num_frames = num_frames
        self._frames: List[Optional[Page]] = [None] * num_frames
        self._algorithm = algorithm
        self._page_table = page_table
        self._metrics = metrics

        # Mapeo inverso: page_id -> frame_index (para búsqueda O(1))
        self._page_to_frame: Dict[int, int] = {}

        # Historial de operaciones (para visualización)
        self._operation_history: List[Dict[str, Any]] = []

        # Estado de simulación
        self._total_accesses = 0
        self._disk_operations: List[DiskOperation] = []

        # Inicializar el algoritmo
        self._algorithm.initialize(self._frames)

    def access_page(
        self,
        page_id: int,
        access_type: 'AccessType',
        future_accesses: Optional[List[int]] = None
    ) -> Tuple[Page, bool]:
        """
        Accede a una página, manejando page faults si es necesario.

        Este método simula el comportamiento completo de un acceso
        a memoria virtual, incluyendo:
        - Verificación en buffer (hit/miss)
        - Interrupción por page fault
        - Selección de víctima
        - Writeback si necesario
        - Carga de página desde disco

        Args:
            page_id: ID de la página a acceder
            access_type: Tipo de acceso (READ/WRITE)
            future_accesses: Accesos futuros (para algoritmo OPT)

        Returns:
            Tupla (page, is_page_fault)

        Raises:
            ValueError: Si page_id es inválido
        """
        self._total_accesses += 1
        self._metrics.record_access()

        # Verificar si la página está en el buffer
        if page_id in self._page_to_frame:
            # PAGE HIT
            frame_idx = self._page_to_frame[page_id]
            page = self._frames[frame_idx]

            self._metrics.record_hit()

            # Notificar al algoritmo del acceso
            self._algorithm.on_page_access(
                frame_idx, page, access_type, is_page_fault=False
            )

            # Actualizar bits de la página
            page.mark_accessed(is_write=(access_type == AccessType.WRITE))

            # Registrar operación
            self._record_operation('HIT', page_id, frame_idx)

            return page, False

        # PAGE FAULT
        return self._handle_page_fault(page_id, access_type, future_accesses)

    def _handle_page_fault(
        self,
        page_id: int,
        access_type: 'AccessType',
        future_accesses: Optional[List[int]] = None
    ) -> Tuple[Page, bool]:
        """
        Maneja un page fault completo.

        Secuencia de eventos:
        1. Interrupción de page fault (trap)
        2. Buscar marco libre o seleccionar víctima
        3. Si víctima está modificada, escribir a disco
        4. Cargar nueva página desde disco
        5. Actualizar estructuras

        Args:
            page_id: ID de la página solicitada
            access_type: Tipo de acceso
            future_accesses: Para algoritmo OPT

        Returns:
            Tupla (page, True) indicando fault
        """
        # Registrar el fault
        self._metrics.record_page_fault()
        self._metrics.record_interrupt()  # Interrupción de page fault

        # Obtener la página de la tabla de páginas
        page = self._page_table.get_page(page_id)

        # Buscar marco libre
        frame_idx = self._find_free_frame()

        if frame_idx is None:
            # No hay marco libre - necesitamos reemplazar
            frame_idx = self._select_and_evict_victim(future_accesses)

        # Simular llamada al sistema para cargar página
        self._metrics.record_syscall()
        self._simulate_disk_read(page_id)

        # Cargar la página en el marco
        self._load_page_into_frame(page, frame_idx)

        # Notificar al algoritmo
        self._algorithm.on_page_load(frame_idx, page)
        self._algorithm.on_page_access(
            frame_idx, page, access_type, is_page_fault=True
        )

        # Actualizar bits
        page.mark_accessed(is_write=(access_type == AccessType.WRITE))

        # Registrar operación
        self._record_operation('FAULT', page_id, frame_idx)

        return page, True

    def _find_free_frame(self) -> Optional[int]:
        """
        Busca un marco libre en el buffer.

        Returns:
            Índice del marco libre, o None si todos ocupados
        """
        for i, frame in enumerate(self._frames):
            if frame is None:
                return i
        return None

    def _select_and_evict_victim(
        self,
        future_accesses: Optional[List[int]] = None
    ) -> int:
        """
        Selecciona y expulsa la página víctima.

        Args:
            future_accesses: Para algoritmo OPT

        Returns:
            Índice del marco liberado
        """
        # Usar el algoritmo de reemplazo para seleccionar víctima
        result = self._algorithm.select_victim(self._frames, future_accesses)

        victim_frame = result.victim_frame
        victim_page = self._frames[victim_frame]

        if victim_page is not None:
            # Si la página está modificada, escribir a disco
            if result.requires_writeback:
                self._metrics.record_syscall()
                self._metrics.record_disk_write()
                self._simulate_disk_write(victim_page.page_id)

            # Expulsar la página
            victim_page.evict_from_memory()

            # Actualizar mapeo
            del self._page_to_frame[victim_page.page_id]

            # Registrar operación
            self._record_operation(
                'EVICT',
                victim_page.page_id,
                victim_frame,
                writeback=result.requires_writeback
            )

        return victim_frame

    def _load_page_into_frame(self, page: Page, frame_idx: int) -> None:
        """
        Carga una página en un marco específico.

        Args:
            page: Página a cargar
            frame_idx: Índice del marco destino
        """
        # Actualizar estado de la página
        page.load_into_memory()

        # Colocar en el marco
        self._frames[frame_idx] = page

        # Actualizar mapeo
        self._page_to_frame[page.page_id] = frame_idx

    def _simulate_disk_read(self, page_id: int) -> None:
        """
        Simula una operación de lectura de disco.

        Registra la operación para métricas y agrega latencia simulada.

        Args:
            page_id: ID de la página leída
        """
        op = DiskOperation(
            io_type=DiskIOType.READ,
            page_id=page_id,
            duration_ms=self.DISK_READ_LATENCY_MS,
            timestamp=time.perf_counter()
        )
        self._disk_operations.append(op)

    def _simulate_disk_write(self, page_id: int) -> None:
        """
        Simula una operación de escritura a disco.

        Args:
            page_id: ID de la página escrita
        """
        op = DiskOperation(
            io_type=DiskIOType.WRITE,
            page_id=page_id,
            duration_ms=self.DISK_WRITE_LATENCY_MS,
            timestamp=time.perf_counter()
        )
        self._disk_operations.append(op)

    def _record_operation(
        self,
        op_type: str,
        page_id: int,
        frame_idx: int,
        writeback: bool = False
    ) -> None:
        """
        Registra una operación para el historial.

        Args:
            op_type: Tipo de operación (HIT, FAULT, EVICT)
            page_id: ID de la página
            frame_idx: Índice del marco
            writeback: Si hubo writeback
        """
        # Capturar estado actual del buffer para visualización
        frame_state = []
        for i, frame in enumerate(self._frames):
            if frame is not None:
                frame_state.append({
                    'frame': i,
                    'page_id': frame.page_id,
                    'R': frame.reference_bit,
                    'M': frame.modified_bit
                })
            else:
                frame_state.append({
                    'frame': i,
                    'page_id': None,
                    'R': None,
                    'M': None
                })

        self._operation_history.append({
            'access_num': self._total_accesses,
            'type': op_type,
            'page_id': page_id,
            'frame_idx': frame_idx,
            'writeback': writeback,
            'frame_state': frame_state,
            'timestamp': time.perf_counter()
        })

    def get_frame_state(self) -> List[Dict[str, Any]]:
        """
        Retorna el estado actual de todos los marcos.

        Returns:
            Lista de diccionarios con estado de cada marco
        """
        state = []
        for i, frame in enumerate(self._frames):
            if frame is not None:
                state.append({
                    'frame_index': i,
                    'page_id': frame.page_id,
                    'reference_bit': frame.reference_bit,
                    'modified_bit': frame.modified_bit,
                    'access_count': frame.access_count,
                    'nru_class': frame.get_class_nru()
                })
            else:
                state.append({
                    'frame_index': i,
                    'page_id': None,
                    'empty': True
                })
        return state

    def get_operation_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retorna el historial de operaciones.

        Args:
            limit: Número máximo de operaciones a retornar

        Returns:
            Lista de operaciones (más recientes primero si hay límite)
        """
        if limit:
            return self._operation_history[-limit:]
        return self._operation_history

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas del buffer pool.

        Returns:
            Diccionario con estadísticas
        """
        frames_used = sum(1 for f in self._frames if f is not None)
        disk_reads = sum(1 for op in self._disk_operations if op.io_type == DiskIOType.READ)
        disk_writes = sum(1 for op in self._disk_operations if op.io_type == DiskIOType.WRITE)

        return {
            'num_frames': self._num_frames,
            'frames_used': frames_used,
            'frames_free': self._num_frames - frames_used,
            'total_accesses': self._total_accesses,
            'disk_reads': disk_reads,
            'disk_writes': disk_writes,
            'algorithm': self._algorithm.name,
            'pages_in_memory': list(self._page_to_frame.keys())
        }

    def reset(self) -> None:
        """
        Reinicia el buffer pool a su estado inicial.

        Limpia todos los marcos y reinicia contadores.
        """
        # Limpiar marcos
        self._frames = [None] * self._num_frames
        self._page_to_frame.clear()

        # Limpiar historial
        self._operation_history.clear()
        self._disk_operations.clear()

        # Reiniciar contadores
        self._total_accesses = 0

        # Reiniciar algoritmo
        self._algorithm.reset()
        self._algorithm.initialize(self._frames)

    def periodic_maintenance(self) -> None:
        """
        Realiza mantenimiento periódico.

        Llama a operaciones como el reset de bits R en NRU.
        Debe llamarse periódicamente durante la simulación.
        """
        # Para NRU, verificar si es momento de resetear bits R
        from algorithms.nru import NRUAlgorithm

        if isinstance(self._algorithm, NRUAlgorithm):
            self._algorithm.periodic_r_reset(self._frames)

    @property
    def num_frames(self) -> int:
        """Número de marcos del buffer pool."""
        return self._num_frames

    @property
    def algorithm(self) -> 'ReplacementAlgorithm':
        """Algoritmo de reemplazo activo."""
        return self._algorithm

    def __str__(self) -> str:
        used = sum(1 for f in self._frames if f is not None)
        return (f"BufferPool(frames={self._num_frames}, used={used}, "
                f"algorithm={self._algorithm.name})")

    def __repr__(self) -> str:
        return self.__str__()
