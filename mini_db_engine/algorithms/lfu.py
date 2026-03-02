"""
Algoritmo de Reemplazo LFU (Least Frequently Used).

Modelo Formal:
--------------
LFU implementa una política basada en frecuencia de acceso.
Selecciona como víctima la página con menor número de accesos.

Sea C = {c(p₁), c(p₂), ..., c(pₙ)} los contadores de frecuencia.
víctima = argmin{c(pᵢ) : pᵢ ∈ páginas_en_memoria}

En caso de empate, se puede usar LRU como desempate.

Fundamento teórico:
La intuición es que páginas accedidas frecuentemente tienen
mayor probabilidad de ser accedidas de nuevo. Sin embargo,
LFU tiene problemas con:
- Páginas "calientes" que ya no se usan (frecuencia histórica alta)
- Páginas nuevas que son penalizadas por su baja frecuencia inicial

Variantes:
- LFU con aging: decrementa contadores periódicamente
- LFU con frecuencia mínima inicial
- LFU con ventana de tiempo

Complejidad (implementación con heap):
- Selección de víctima: O(log n) con min-heap, O(n) con lista
- Actualización: O(log n) con heap, O(1) con lista
- Espacio: O(n)

Esta implementación usa diccionario con búsqueda O(n) para
selección y O(1) para actualización, priorizando simplicidad.

Autor: Proyecto Académico - Sistemas Operativos
"""

from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from collections import defaultdict
import heapq
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class LFUAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo LFU con desempate por tiempo.

    Estructura de datos:
    - _frequency: Dict[frame_index -> (frequency, load_time)]
    - _min_freq_frames: Lista de marcos con frecuencia mínima
    - _load_order: Contador para desempatar por orden de carga

    Política de desempate:
    Cuando múltiples páginas tienen la misma frecuencia mínima,
    se selecciona la que llegó primero (FIFO entre iguales).

    Attributes:
        _frequency: Mapeo de marco a (frecuencia, tiempo_carga)
        _load_order: Contador incremental para orden de carga
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo LFU.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("LFU", num_frames)
        self._frequency: Dict[int, Tuple[int, int]] = {}  # frame -> (freq, load_time)
        self._load_order: int = 0

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa los contadores de frecuencia.

        Las páginas existentes reciben frecuencia 1 y orden incremental.

        Args:
            frames: Lista de marcos actuales
        """
        self._frequency.clear()
        self._load_order = 0

        for frame_idx, page in enumerate(frames):
            if page is not None:
                self._frequency[frame_idx] = (1, self._load_order)
                self._load_order += 1

        self._initialized = True

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona el marco víctima usando política LFU.

        Busca el marco con menor frecuencia de acceso.
        En caso de empate, selecciona el más antiguo (menor load_time).

        Complejidad: O(n) - recorre todos los marcos

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado en LFU

        Returns:
            ReplacementResult con el marco menos frecuentemente usado
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo LFU no inicializado")

        if not self._frequency:
            raise RuntimeError("No hay marcos para reemplazar")

        # Encontrar el marco con menor frecuencia
        # Desempate por load_time (menor = más antiguo = víctima preferida)
        victim_frame = min(
            self._frequency.keys(),
            key=lambda f: (self._frequency[f][0], self._frequency[f][1])
        )

        freq, load_time = self._frequency[victim_frame]
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
                'frequency': freq,
                'load_order': load_time,
                'min_frequency': min(f[0] for f in self._frequency.values()),
                'max_frequency': max(f[0] for f in self._frequency.values()),
                'selection_reason': f'Página con menor frecuencia ({freq} accesos)'
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
        Actualiza el contador de frecuencia tras un acceso.

        Incrementa el contador de frecuencia del marco accedido.
        El load_time se mantiene constante (solo cambia en carga).

        Complejidad: O(1) - actualización de diccionario

        Args:
            frame_index: Índice del marco accedido
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: True si fue page fault
        """
        self._access_count += 1

        # Actualizar bits
        page.reference_bit = True
        if access_type == AccessType.WRITE:
            page.modified_bit = True

        # Incrementar frecuencia (solo si no es fault, el fault se maneja en on_page_load)
        if frame_index in self._frequency and not is_page_fault:
            freq, load_time = self._frequency[frame_index]
            self._frequency[frame_index] = (freq + 1, load_time)

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra una nueva página cargada.

        La nueva página inicia con frecuencia 1 y orden de carga actual.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco
            page: Página cargada
        """
        # Nueva página: frecuencia 1, orden de carga actual
        self._frequency[frame_index] = (1, self._load_order)
        self._load_order += 1

        # Inicializar bits
        page.reference_bit = True
        page.modified_bit = False

    def reset(self) -> None:
        """
        Reinicia el algoritmo a estado inicial.
        """
        self._frequency.clear()
        self._load_order = 0
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo LFU.

        Returns:
            Diccionario con complejidades
        """
        return {
            'time_select': 'O(n) - búsqueda del mínimo en diccionario',
            'time_update': 'O(1) - actualización de contador',
            'space': 'O(n) - diccionario de frecuencias'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de LFU.
        """
        stats = super().get_statistics()

        frequencies = [f[0] for f in self._frequency.values()] if self._frequency else [0]

        stats.update({
            'min_frequency': min(frequencies),
            'max_frequency': max(frequencies),
            'avg_frequency': sum(frequencies) / len(frequencies),
            'frequency_distribution': self._get_frequency_distribution()
        })
        return stats

    def _get_frequency_distribution(self) -> Dict[int, int]:
        """
        Calcula la distribución de frecuencias.

        Returns:
            Dict[frecuencia -> número de marcos con esa frecuencia]
        """
        distribution = defaultdict(int)
        for freq, _ in self._frequency.values():
            distribution[freq] += 1
        return dict(distribution)

    def __str__(self) -> str:
        freqs = [f[0] for f in self._frequency.values()]
        min_f = min(freqs) if freqs else 0
        return f"LFU(frames={self.num_frames}, min_freq={min_f})"
