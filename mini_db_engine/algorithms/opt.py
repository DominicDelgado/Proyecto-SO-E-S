"""
Algoritmo de Reemplazo OPT (Óptimo de Belady).

Modelo Formal:
--------------
OPT implementa la política de reemplazo óptima que minimiza los page faults.
Selecciona como víctima la página que será accedida más tarde en el futuro,
o que nunca será accedida de nuevo.

Sea F = [f₁, f₂, ..., fₘ] la secuencia de accesos futuros.
Para cada página pᵢ en memoria, definimos:
- next_use(pᵢ) = min{j : fⱼ = pᵢ} si existe, ∞ en caso contrario

Algoritmo:
víctima = argmax{next_use(pᵢ) : pᵢ ∈ páginas_en_memoria}

Características:
- Algoritmo teóricamente óptimo (mínimo número de page faults posible)
- NO es implementable en la práctica (requiere conocer el futuro)
- Sirve como benchmark para evaluar otros algoritmos
- Garantiza no sufrir anomalía de Belady

Complejidad:
- Selección de víctima: O(n × m) donde n=marcos, m=accesos futuros
- Actualización: O(1)
- Espacio: O(m) para almacenar accesos futuros

Uso en Simulación:
------------------
En este simulador, OPT se implementa aprovechando que conocemos
toda la secuencia de accesos de antemano, lo cual permite calcular
el comportamiento óptimo como referencia.

Autor: Proyecto Académico - Sistemas Operativos
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class OPTAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo OPT (Óptimo de Belady).

    Este algoritmo requiere conocer los accesos futuros, lo cual lo hace
    impracticable en sistemas reales pero invaluable como benchmark.

    Estrategia de implementación:
    - Mantenemos la secuencia completa de accesos futuros
    - Para cada selección de víctima, buscamos la página cuyo
      próximo acceso está más lejos en el futuro

    Attributes:
        _future_accesses: Lista completa de accesos futuros
        _current_index: Índice actual en la secuencia de accesos
        _frame_pages: Mapeo de marcos a IDs de página
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo OPT.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("OPT", num_frames)
        self._future_accesses: List[int] = []
        self._current_index: int = 0
        self._frame_pages: Dict[int, int] = {}

    def set_future_accesses(self, accesses: List[int]) -> None:
        """
        Establece la secuencia de accesos futuros.

        Este método debe llamarse antes de la simulación para que
        OPT pueda calcular el reemplazo óptimo.

        Args:
            accesses: Lista de IDs de página que serán accedidos
        """
        self._future_accesses = accesses.copy()
        self._current_index = 0

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa el estado con las páginas existentes.

        Args:
            frames: Lista de marcos actuales
        """
        self._frame_pages.clear()
        self._current_index = 0

        for frame_idx, page in enumerate(frames):
            if page is not None:
                self._frame_pages[frame_idx] = page.page_id

        self._initialized = True

    def _find_next_use(self, page_id: int, start_index: int) -> int:
        """
        Encuentra el índice del próximo acceso a una página.

        Busca en la secuencia de accesos futuros a partir de start_index
        para encontrar cuándo se accederá nuevamente a page_id.

        Args:
            page_id: ID de la página a buscar
            start_index: Índice desde donde comenzar la búsqueda

        Returns:
            Índice del próximo acceso, o infinito (len + 1) si no hay más accesos
        """
        try:
            # Buscar en la porción futura de la secuencia
            for i in range(start_index, len(self._future_accesses)):
                if self._future_accesses[i] == page_id:
                    return i
            # Si no se encuentra, retornar "infinito"
            return len(self._future_accesses) + 1
        except (IndexError, ValueError):
            return len(self._future_accesses) + 1

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona el marco víctima usando política OPT.

        Examina cada página en memoria y calcula cuándo será
        accedida nuevamente. Selecciona la que será accedida
        más tarde (o nunca).

        Complejidad: O(n × m) donde n=marcos, m=accesos restantes

        Args:
            frames: Lista de marcos actuales
            future_accesses: Accesos futuros (opcional, usa internos si no se provee)

        Returns:
            ReplacementResult con el marco óptimo a reemplazar
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo OPT no inicializado")

        # Usar accesos futuros proporcionados o los internos
        if future_accesses:
            search_list = future_accesses
        else:
            search_list = self._future_accesses[self._current_index:]

        victim_frame = -1
        farthest_use = -1
        victim_page_id = None
        requires_writeback = False

        # Para cada marco ocupado, encontrar el próximo uso
        for frame_idx, page in enumerate(frames):
            if page is None:
                continue

            next_use = self._find_next_use(page.page_id, self._current_index)

            # Si esta página nunca será usada de nuevo, es la víctima ideal
            if next_use > len(self._future_accesses):
                victim_frame = frame_idx
                victim_page_id = page.page_id
                requires_writeback = page.modified_bit
                break

            # Sino, buscar la que será usada más tarde
            if next_use > farthest_use:
                farthest_use = next_use
                victim_frame = frame_idx
                victim_page_id = page.page_id
                requires_writeback = page.modified_bit

        # Si no encontramos víctima, tomar el primer marco ocupado
        if victim_frame == -1:
            for frame_idx, page in enumerate(frames):
                if page is not None:
                    victim_frame = frame_idx
                    victim_page_id = page.page_id
                    requires_writeback = page.modified_bit
                    break

        return ReplacementResult(
            victim_frame=victim_frame,
            victim_page_id=victim_page_id,
            requires_writeback=requires_writeback,
            algorithm_metadata={
                'farthest_use_index': farthest_use if farthest_use >= 0 else 'never',
                'current_index': self._current_index,
                'selection_reason': 'Página con uso más lejano en el futuro'
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
        Actualiza el estado tras un acceso.

        OPT necesita avanzar el índice de acceso actual para
        saber qué accesos son "futuros" en la siguiente selección.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco accedido
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: True si fue page fault
        """
        self._access_count += 1
        self._current_index += 1

        # Actualizar bits
        page.reference_bit = True
        if access_type == AccessType.WRITE:
            page.modified_bit = True

        # Actualizar mapeo interno
        self._frame_pages[frame_index] = page.page_id

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra una nueva página cargada.

        Args:
            frame_index: Índice del marco
            page: Página cargada
        """
        self._frame_pages[frame_index] = page.page_id
        page.reference_bit = True
        page.modified_bit = False

    def reset(self) -> None:
        """
        Reinicia el algoritmo a estado inicial.
        """
        self._future_accesses.clear()
        self._current_index = 0
        self._frame_pages.clear()
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo OPT.

        Returns:
            Diccionario con complejidades
        """
        return {
            'time_select': 'O(n × m) - n marcos, m accesos futuros restantes',
            'time_update': 'O(1) - solo incrementa índice',
            'space': 'O(m) - almacena secuencia de m accesos'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de OPT.
        """
        stats = super().get_statistics()
        stats.update({
            'total_accesses_known': len(self._future_accesses),
            'current_index': self._current_index,
            'remaining_accesses': len(self._future_accesses) - self._current_index
        })
        return stats

    def __str__(self) -> str:
        return f"OPT(frames={self.num_frames}, index={self._current_index})"
