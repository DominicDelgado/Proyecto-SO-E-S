"""
Algoritmo de Reemplazo LRU (Least Recently Used).

Modelo Formal:
--------------
LRU implementa una política basada en localidad temporal.
Selecciona como víctima la página que no ha sido usada por más tiempo.

Sea T = {t(p₁), t(p₂), ..., t(pₙ)} los tiempos de último acceso.
víctima = argmin{t(pᵢ) : pᵢ ∈ páginas_en_memoria}

Fundamento teórico (Localidad Temporal):
La localidad temporal establece que una página accedida recientemente
tiene alta probabilidad de ser accedida nuevamente pronto. Por tanto,
la página menos recientemente usada es la mejor candidata a reemplazo.

Características:
- Aproximación práctica al algoritmo óptimo
- No sufre anomalía de Belady
- Rendimiento cercano a OPT en cargas con buena localidad
- Implementación costosa en hardware real (requiere timestamps)

Implementaciones comunes:
1. Contadores de tiempo (usada aquí)
2. Stack/Lista con reordenamiento
3. Matriz de bits (hardware)
4. Aproximación por bits de referencia (Second Chance)

Complejidad (implementación con ordenamiento):
- Selección de víctima: O(n) para encontrar mínimo
- Actualización: O(1) para actualizar timestamp
- Espacio: O(n) para timestamps

Autor: Proyecto Académico - Sistemas Operativos
"""

from collections import OrderedDict
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class LRUAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo LRU usando OrderedDict.

    Utilizamos OrderedDict de Python que mantiene el orden de inserción
    y permite move_to_end en O(1), proporcionando una implementación
    eficiente de LRU.

    Estructura de datos:
    - _access_order: OrderedDict[frame_index -> page_id]
      El elemento al frente es el LRU (menos recientemente usado)
      El elemento al final es el MRU (más recientemente usado)

    Invariantes:
    1. len(_access_order) <= num_frames
    2. El primer elemento es siempre el LRU
    3. Cada acceso mueve el marco al final

    Attributes:
        _access_order: OrderedDict manteniendo orden de acceso
        _logical_time: Contador lógico de tiempo para debugging
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo LRU.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("LRU", num_frames)
        self._access_order: OrderedDict = OrderedDict()
        self._logical_time: int = 0

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa el orden de acceso con las páginas existentes.

        Las páginas existentes se agregan en orden de índice,
        asumiendo que las de menor índice fueron accedidas antes.

        Args:
            frames: Lista de marcos actuales
        """
        self._access_order.clear()
        self._logical_time = 0

        for frame_idx, page in enumerate(frames):
            if page is not None:
                self._access_order[frame_idx] = {
                    'page_id': page.page_id,
                    'last_access': self._logical_time
                }
                self._logical_time += 1

        self._initialized = True

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona el marco víctima usando política LRU.

        Retorna el marco al frente del OrderedDict, que corresponde
        al marco accedido menos recientemente.

        Complejidad: O(1) - acceso directo al frente del OrderedDict

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado en LRU

        Returns:
            ReplacementResult con el marco LRU
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo LRU no inicializado")

        if not self._access_order:
            raise RuntimeError("No hay marcos para reemplazar")

        # El primer elemento en OrderedDict es el LRU
        victim_frame = next(iter(self._access_order))
        victim_info = self._access_order[victim_frame]

        page = frames[victim_frame]
        requires_writeback = False
        victim_page_id = None

        if page is not None:
            victim_page_id = page.page_id
            requires_writeback = page.modified_bit

        return ReplacementResult(
            victim_frame=victim_frame,
            victim_page_id=victim_page_id,
            requires_writeback=requires_writeback,
            algorithm_metadata={
                'last_access_time': victim_info['last_access'],
                'current_time': self._logical_time,
                'age': self._logical_time - victim_info['last_access'],
                'selection_reason': 'Página menos recientemente usada'
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

        En LRU, cada acceso (hit o fault) mueve el marco al final
        del OrderedDict, marcándolo como el más recientemente usado.

        Complejidad: O(1) - move_to_end es O(1) en OrderedDict

        Args:
            frame_index: Índice del marco accedido
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: True si fue page fault
        """
        self._access_count += 1
        self._logical_time += 1

        # Actualizar bits de la página
        page.reference_bit = True
        if access_type == AccessType.WRITE:
            page.modified_bit = True

        # Si es un hit, mover al final (MRU)
        if frame_index in self._access_order:
            self._access_order.move_to_end(frame_index)
            self._access_order[frame_index] = {
                'page_id': page.page_id,
                'last_access': self._logical_time
            }

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra una nueva página cargada en el buffer.

        Cuando se carga una página nueva:
        1. Remover el marco víctima (si existe en el orden)
        2. Agregar el nuevo marco al final (MRU)

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco donde se cargó
            page: Página recién cargada
        """
        self._logical_time += 1

        # Remover si ya existe (reemplazo)
        if frame_index in self._access_order:
            del self._access_order[frame_index]

        # Agregar al final como MRU
        self._access_order[frame_index] = {
            'page_id': page.page_id,
            'last_access': self._logical_time
        }

        # Inicializar bits
        page.reference_bit = True
        page.modified_bit = False

    def reset(self) -> None:
        """
        Reinicia el algoritmo a estado inicial.
        """
        self._access_order.clear()
        self._logical_time = 0
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo LRU.

        Returns:
            Diccionario con complejidades
        """
        return {
            'time_select': 'O(1) - acceso al frente de OrderedDict',
            'time_update': 'O(1) - move_to_end es O(1) amortizado',
            'space': 'O(n) - OrderedDict de tamaño n marcos'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de LRU.
        """
        stats = super().get_statistics()

        # Calcular edad promedio de las páginas
        ages = []
        for frame_idx, info in self._access_order.items():
            ages.append(self._logical_time - info['last_access'])

        stats.update({
            'logical_time': self._logical_time,
            'pages_tracked': len(self._access_order),
            'avg_page_age': sum(ages) / len(ages) if ages else 0,
            'oldest_page_age': max(ages) if ages else 0,
            'newest_page_age': min(ages) if ages else 0
        })
        return stats

    def get_lru_stack(self) -> List[int]:
        """
        Retorna el stack LRU actual (para visualización).

        Returns:
            Lista de frame_index ordenada de LRU a MRU
        """
        return list(self._access_order.keys())

    def __str__(self) -> str:
        return f"LRU(frames={self.num_frames}, time={self._logical_time})"
