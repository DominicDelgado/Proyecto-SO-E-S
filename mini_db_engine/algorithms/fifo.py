"""
Algoritmo de Reemplazo FIFO (First-In First-Out).

Modelo Formal:
--------------
FIFO implementa una política de reemplazo basada en el orden de llegada.
La página que lleva más tiempo en memoria es seleccionada como víctima.

Sea Q una cola FIFO donde:
- enqueue(pᵢ, t): inserta página pᵢ en tiempo t
- dequeue() → pⱼ: retorna la página más antigua

Algoritmo:
1. Cuando llega página pᵢ y buffer lleno:
   - víctima = dequeue()
   - enqueue(pᵢ, t_actual)

Características:
- No considera el patrón de uso de las páginas
- Sufre de la anomalía de Belady
- Simple pero puede reemplazar páginas frecuentemente usadas

Complejidad:
- Selección de víctima: O(1)
- Actualización: O(1)
- Espacio: O(n) donde n = número de marcos

Anomalía de Belady:
-------------------
FIFO puede exhibir comportamiento anómalo donde aumentar el número
de marcos incrementa los page faults. Esto ocurre porque FIFO no
considera la frecuencia ni recencia de uso.

Ejemplo clásico: secuencia 1,2,3,4,1,2,5,1,2,3,4,5
- Con 3 marcos: 9 faults
- Con 4 marcos: 10 faults (¡más faults con más memoria!)

Autor: Proyecto Académico - Sistemas Operativos
"""

from collections import deque
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import sys
import os

# Agregar directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class FIFOAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo FIFO para reemplazo de páginas.

    Utiliza una cola (deque) para mantener el orden de llegada de las páginas.
    La página al frente de la cola (la más antigua) es seleccionada como víctima.

    Estructura de datos:
    - _queue: deque de (frame_index, page_id) ordenado por tiempo de llegada
    - _frame_to_position: dict para búsqueda rápida O(1)

    Invariantes:
    1. len(_queue) <= num_frames
    2. Cada marco aparece como máximo una vez en _queue
    3. El frente de _queue contiene la página más antigua

    Attributes:
        _queue: Cola FIFO de marcos
        _frame_to_position: Mapeo de marco a posición para validación
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo FIFO.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("FIFO", num_frames)
        self._queue: deque = deque()
        self._frame_in_queue: set = set()

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa la cola FIFO con las páginas existentes.

        Las páginas existentes se agregan a la cola en orden de índice
        de marco, asumiendo que las de menor índice llegaron primero.

        Args:
            frames: Lista de marcos actuales
        """
        self._queue.clear()
        self._frame_in_queue.clear()

        # Agregar marcos ocupados a la cola en orden
        for frame_idx, page in enumerate(frames):
            if page is not None:
                self._queue.append(frame_idx)
                self._frame_in_queue.add(frame_idx)

        self._initialized = True

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona el marco víctima usando política FIFO.

        Retorna el marco al frente de la cola (el más antiguo).
        La página en ese marco será reemplazada.

        Complejidad: O(1) - acceso directo al frente de la cola

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado en FIFO

        Returns:
            ReplacementResult con el marco más antiguo

        Raises:
            RuntimeError: Si el algoritmo no está inicializado
            RuntimeError: Si la cola está vacía (no debería ocurrir si buffer lleno)
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo FIFO no inicializado. Llamar initialize() primero.")

        if not self._queue:
            raise RuntimeError("Cola FIFO vacía - estado inconsistente")

        # El frente de la cola es el marco más antiguo
        victim_frame = self._queue[0]
        victim_page = frames[victim_frame]

        # Verificar si la página fue modificada (necesita writeback)
        requires_writeback = False
        victim_page_id = None

        if victim_page is not None:
            victim_page_id = victim_page.page_id
            requires_writeback = victim_page.modified_bit

        return ReplacementResult(
            victim_frame=victim_frame,
            victim_page_id=victim_page_id,
            requires_writeback=requires_writeback,
            algorithm_metadata={
                'queue_length': len(self._queue),
                'selection_reason': 'Página más antigua en cola FIFO'
            }
        )

    def on_page_access(
        self,
        frame_index: int,
        page: 'Page',
        access_type: AccessType,
        is_page_fault: bool
    ) -> None:
        """
        Actualiza el estado tras un acceso a página.

        En FIFO, un hit no modifica la cola - la página mantiene
        su posición original. Solo actualizamos los bits R y M.

        Nota importante: FIFO no "refresca" páginas en hits, lo cual
        es una de las razones de su comportamiento subóptimo.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco accedido
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: True si fue page fault
        """
        self._access_count += 1

        # Actualizar bit de referencia
        page.reference_bit = True

        # Actualizar bit de modificación si es escritura
        if access_type == AccessType.WRITE:
            page.modified_bit = True

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra una nueva página cargada en el buffer.

        Cuando se carga una página nueva (después de un fault):
        1. Remover el marco del frente de la cola (la víctima)
        2. Agregar el marco al final de la cola (nueva página)

        Complejidad: O(1) con deque

        Args:
            frame_index: Índice del marco donde se cargó la página
            page: Página recién cargada
        """
        # Si el marco ya estaba en la cola (reemplazo), removerlo del frente
        if self._queue and self._queue[0] == frame_index:
            self._queue.popleft()
            self._frame_in_queue.discard(frame_index)

        # Agregar el marco al final de la cola (llegada más reciente)
        if frame_index not in self._frame_in_queue:
            self._queue.append(frame_index)
            self._frame_in_queue.add(frame_index)

        # Inicializar bits de la página
        page.reference_bit = True
        page.modified_bit = False

    def reset(self) -> None:
        """
        Reinicia el algoritmo a su estado inicial.

        Limpia la cola FIFO y todos los contadores.
        """
        self._queue.clear()
        self._frame_in_queue.clear()
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo FIFO.

        Returns:
            Diccionario con complejidades temporales y espaciales
        """
        return {
            'time_select': 'O(1) - acceso directo al frente de deque',
            'time_update': 'O(1) - append/popleft en deque',
            'space': 'O(n) - deque y set de tamaño n marcos'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de FIFO.

        Returns:
            Diccionario con estadísticas del algoritmo
        """
        stats = super().get_statistics()
        stats.update({
            'queue_length': len(self._queue),
            'queue_order': list(self._queue)[:10]  # Primeros 10 para debugging
        })
        return stats

    def __str__(self) -> str:
        return f"FIFO(frames={self.num_frames}, queue_size={len(self._queue)})"
