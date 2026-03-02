"""
Algoritmo de Reemplazo Clock (Reloj).

Modelo Formal:
--------------
El algoritmo Clock es una aproximación eficiente de LRU que utiliza
un bit de referencia (R) para cada marco, organizados en una estructura
circular (reloj).

Sea M = {m₀, m₁, ..., mₙ₋₁} los marcos organizados circularmente.
Sea R[mᵢ] ∈ {0, 1} el bit de referencia del marco mᵢ.
Sea ptr el puntero del reloj (índice actual).

Algoritmo para seleccionar víctima:
    while True:
        if R[M[ptr]] == 0:
            return M[ptr]  # víctima encontrada
        else:
            R[M[ptr]] = 0  # dar segunda oportunidad
            ptr = (ptr + 1) mod n  # avanzar manecilla

Características:
- Aproximación de LRU con complejidad O(1) amortizada
- Utiliza solo 1 bit por marco (eficiente en hardware)
- También llamado "Second-Chance básico"
- Ampliamente usado en sistemas reales (ej: variantes en Linux)

Comportamiento:
- Páginas accedidas recientemente tienen R=1 y reciben "segunda oportunidad"
- La manecilla avanza hasta encontrar R=0
- En el peor caso, da vuelta completa (todos con R=1)

Variantes:
- Clock mejorado: considera también bit M
- WSClock: combina con working set
- Clock-Pro: tres "manecillas"

Complejidad:
- Selección de víctima: O(n) peor caso, O(1) amortizado
- Actualización: O(1) - solo modificar bit R
- Espacio: O(1) adicional (solo el puntero)

Autor: Proyecto Académico - Sistemas Operativos
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class ClockAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo Clock (Reloj).

    Simula una estructura circular donde los marcos se recorren
    como las horas de un reloj. El puntero (manecilla) avanza
    buscando un marco con R=0.

    Estructura de datos:
    - Los marcos forman implícitamente el "reloj"
    - _clock_hand: índice del marco actual (puntero)
    - Los bits R se almacenan en las páginas

    Invariantes:
    1. 0 <= _clock_hand < num_frames
    2. El puntero avanza circularmente

    Attributes:
        _clock_hand: Posición actual de la manecilla del reloj
        _rotations: Contador de vueltas completas (para estadísticas)
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo Clock.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("Clock", num_frames)
        self._clock_hand: int = 0
        self._rotations: int = 0
        self._steps_in_current_search: int = 0

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa el reloj.

        El puntero se coloca en la posición 0.
        Los bits R de las páginas existentes se mantienen.

        Args:
            frames: Lista de marcos actuales
        """
        self._clock_hand = 0
        self._rotations = 0
        self._steps_in_current_search = 0
        self._initialized = True

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona el marco víctima usando política Clock.

        Recorre los marcos circularmente desde _clock_hand:
        - Si R=0: seleccionar como víctima
        - Si R=1: poner R=0 y avanzar (segunda oportunidad)

        Complejidad: O(n) peor caso (una vuelta completa),
                     O(1) amortizado

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado en Clock

        Returns:
            ReplacementResult con el marco víctima
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo Clock no inicializado")

        self._steps_in_current_search = 0
        initial_hand = self._clock_hand

        while True:
            page = frames[self._clock_hand]

            # Marco vacío: seleccionar directamente
            if page is None:
                victim_frame = self._clock_hand
                self._advance_hand()
                return ReplacementResult(
                    victim_frame=victim_frame,
                    victim_page_id=None,
                    requires_writeback=False,
                    algorithm_metadata={
                        'steps_taken': self._steps_in_current_search,
                        'selection_reason': 'Marco vacío encontrado'
                    }
                )

            # Verificar bit de referencia
            if not page.reference_bit:
                # R=0: seleccionar como víctima
                victim_frame = self._clock_hand
                victim_page_id = page.page_id
                requires_writeback = page.modified_bit

                self._advance_hand()

                return ReplacementResult(
                    victim_frame=victim_frame,
                    victim_page_id=victim_page_id,
                    requires_writeback=requires_writeback,
                    algorithm_metadata={
                        'steps_taken': self._steps_in_current_search,
                        'clock_position': self._clock_hand,
                        'selection_reason': 'R=0, página sin referencia reciente'
                    }
                )
            else:
                # R=1: dar segunda oportunidad
                page.reference_bit = False
                self._advance_hand()

            # Verificar vuelta completa
            if self._clock_hand == initial_hand:
                self._rotations += 1
                # Si volvimos al inicio, todos tenían R=1
                # En la siguiente iteración encontraremos R=0

    def _advance_hand(self) -> None:
        """
        Avanza la manecilla del reloj circularmente.

        Post-condición:
            _clock_hand = (_clock_hand + 1) mod num_frames
        """
        self._clock_hand = (self._clock_hand + 1) % self.num_frames
        self._steps_in_current_search += 1

    def on_page_access(
        self,
        frame_index: int,
        page: 'Page',
        access_type: AccessType,
        is_page_fault: bool
    ) -> None:
        """
        Actualiza el estado tras un acceso.

        En Clock, cada acceso establece R=1 para la página,
        dándole protección contra reemplazo.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco accedido
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: True si fue page fault
        """
        self._access_count += 1

        # Establecer bit de referencia (protección)
        page.reference_bit = True

        # Actualizar bit de modificación si es escritura
        if access_type == AccessType.WRITE:
            page.modified_bit = True

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra una nueva página cargada.

        La página nueva inicia con R=1, M=0.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco
            page: Página cargada
        """
        page.reference_bit = True
        page.modified_bit = False

    def reset(self) -> None:
        """
        Reinicia el algoritmo a estado inicial.
        """
        self._clock_hand = 0
        self._rotations = 0
        self._steps_in_current_search = 0
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo Clock.
        """
        return {
            'time_select': 'O(n) peor caso, O(1) amortizado',
            'time_update': 'O(1) - solo modificar bit R',
            'space': 'O(1) adicional - solo el puntero'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de Clock.
        """
        stats = super().get_statistics()
        stats.update({
            'clock_hand_position': self._clock_hand,
            'total_rotations': self._rotations,
            'last_search_steps': self._steps_in_current_search
        })
        return stats

    def get_clock_state(self, frames: List[Optional['Page']]) -> List[Dict]:
        """
        Retorna el estado actual del reloj (para visualización).

        Args:
            frames: Lista de marcos actuales

        Returns:
            Lista de estados de cada marco
        """
        state = []
        for i, page in enumerate(frames):
            state.append({
                'frame': i,
                'page_id': page.page_id if page else None,
                'R': page.reference_bit if page else None,
                'M': page.modified_bit if page else None,
                'is_hand': i == self._clock_hand
            })
        return state

    def __str__(self) -> str:
        return f"Clock(frames={self.num_frames}, hand={self._clock_hand})"
