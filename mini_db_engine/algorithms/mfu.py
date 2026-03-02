"""
Algoritmo de Reemplazo MFU (Most Frequently Used).

Modelo Formal:
--------------
MFU implementa una política inversa a LFU.
Selecciona como víctima la página con mayor número de accesos.

Sea C = {c(p₁), c(p₂), ..., c(pₙ)} los contadores de frecuencia.
víctima = argmax{c(pᵢ) : pᵢ ∈ páginas_en_memoria}

Fundamento teórico:
La intuición (contra-intuitiva) es que:
1. Páginas muy accedidas probablemente ya completaron su "trabajo"
2. Páginas con pocos accesos pueden estar en medio de una ráfaga
3. En algunos patrones de acceso específicos, MFU puede funcionar mejor

Casos de uso:
- Acceso secuencial único (cada página se usa una vez y no más)
- Procesamiento batch donde cada página se procesa completamente
- Workloads donde frecuencia alta indica "trabajo completado"

Limitaciones:
- Rendimiento pobre en workloads con localidad temporal
- Contra-intuitivo respecto al principio de localidad
- Raramente usado en sistemas de producción

Complejidad:
- Selección de víctima: O(n)
- Actualización: O(1)
- Espacio: O(n)

Autor: Proyecto Académico - Sistemas Operativos
"""

from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from collections import defaultdict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class MFUAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo MFU con desempate por tiempo.

    Estructura de datos idéntica a LFU, pero selección inversa:
    - _frequency: Dict[frame_index -> (frequency, load_time)]

    Política de desempate:
    Cuando múltiples páginas tienen la misma frecuencia máxima,
    se selecciona la más antigua (menor load_time).

    Attributes:
        _frequency: Mapeo de marco a (frecuencia, tiempo_carga)
        _load_order: Contador incremental para orden de carga
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo MFU.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("MFU", num_frames)
        self._frequency: Dict[int, Tuple[int, int]] = {}
        self._load_order: int = 0

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa los contadores de frecuencia.

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
        Selecciona el marco víctima usando política MFU.

        Busca el marco con MAYOR frecuencia de acceso.
        En caso de empate, selecciona el más antiguo.

        Complejidad: O(n) - recorre todos los marcos

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado en MFU

        Returns:
            ReplacementResult con el marco más frecuentemente usado
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo MFU no inicializado")

        if not self._frequency:
            raise RuntimeError("No hay marcos para reemplazar")

        # Encontrar el marco con MAYOR frecuencia
        # Desempate: mayor frecuencia primero, luego más antiguo (menor load_time)
        victim_frame = max(
            self._frequency.keys(),
            key=lambda f: (self._frequency[f][0], -self._frequency[f][1])
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
                'max_frequency': max(f[0] for f in self._frequency.values()),
                'min_frequency': min(f[0] for f in self._frequency.values()),
                'selection_reason': f'Página con mayor frecuencia ({freq} accesos)'
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

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco accedido
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: True si fue page fault
        """
        self._access_count += 1

        page.reference_bit = True
        if access_type == AccessType.WRITE:
            page.modified_bit = True

        # Incrementar frecuencia (no en faults)
        if frame_index in self._frequency and not is_page_fault:
            freq, load_time = self._frequency[frame_index]
            self._frequency[frame_index] = (freq + 1, load_time)

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra una nueva página cargada.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco
            page: Página cargada
        """
        self._frequency[frame_index] = (1, self._load_order)
        self._load_order += 1

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
        Retorna la complejidad del algoritmo MFU.
        """
        return {
            'time_select': 'O(n) - búsqueda del máximo en diccionario',
            'time_update': 'O(1) - actualización de contador',
            'space': 'O(n) - diccionario de frecuencias'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de MFU.
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
        """
        distribution = defaultdict(int)
        for freq, _ in self._frequency.values():
            distribution[freq] += 1
        return dict(distribution)

    def __str__(self) -> str:
        freqs = [f[0] for f in self._frequency.values()]
        max_f = max(freqs) if freqs else 0
        return f"MFU(frames={self.num_frames}, max_freq={max_f})"
