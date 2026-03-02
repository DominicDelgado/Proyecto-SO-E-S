"""
Algoritmo de Reemplazo Segunda Oportunidad (Second Chance Mejorado).

Modelo Formal:
--------------
Segunda Oportunidad Mejorado extiende el algoritmo Clock considerando
tanto el bit de referencia (R) como el bit de modificación (M).

Clasificación de páginas en 4 clases:
- Clase 0: R=0, M=0 - No usada, no modificada (mejor candidata)
- Clase 1: R=0, M=1 - No usada, modificada
- Clase 2: R=1, M=0 - Usada, no modificada
- Clase 3: R=1, M=1 - Usada, modificada (peor candidata)

Algoritmo:
1. Buscar víctima de clase 0 (no limpia R en esta pasada)
2. Si no hay, buscar clase 1 (limpiando R de clase 2 y 3)
3. Si no hay, volver a buscar clase 0 (ahora hay por limpieza de R)
4. Si no hay, buscar clase 1

La preferencia por páginas no modificadas (M=0) reduce escrituras a disco.

Características:
- Mejora sobre Clock simple al considerar costo de I/O
- Minimiza escrituras a disco (prefiere páginas limpias)
- Implementado en variantes de sistemas Unix
- Balance entre recencia de uso y costo de reemplazo

Complejidad:
- Selección de víctima: O(2n) peor caso (dos pasadas máximo)
- Actualización: O(1)
- Espacio: O(1) adicional

Autor: Proyecto Académico - Sistemas Operativos
"""

from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from enum import IntEnum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class PageClass(IntEnum):
    """
    Clasificación de páginas según bits R y M.

    Menor valor = mejor candidata para reemplazo.
    """
    NOT_REFERENCED_NOT_MODIFIED = 0  # R=0, M=0
    NOT_REFERENCED_MODIFIED = 1       # R=0, M=1
    REFERENCED_NOT_MODIFIED = 2       # R=1, M=0
    REFERENCED_MODIFIED = 3           # R=1, M=1


class SegundaOportunidadAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo Segunda Oportunidad Mejorado.

    Utiliza el algoritmo del reloj con clasificación de páginas
    basada en bits R y M. Busca víctimas en orden de preferencia
    de clase (0 → 1 → 2 → 3).

    Diferencia con Clock básico:
    - Clock: solo considera R
    - Segunda Oportunidad Mejorado: considera R y M

    Esto reduce I/O al preferir páginas limpias.

    Attributes:
        _clock_hand: Posición actual de la manecilla
        _current_pass: Pasada actual (1-4)
        _pages_examined: Páginas examinadas en búsqueda actual
    """

    def __init__(self, num_frames: int):
        """
        Inicializa el algoritmo Segunda Oportunidad.

        Args:
            num_frames: Número de marcos en el buffer pool
        """
        super().__init__("Segunda Oportunidad", num_frames)
        self._clock_hand: int = 0
        self._current_pass: int = 0
        self._pages_examined: int = 0
        self._total_passes: int = 0

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa el algoritmo.

        Args:
            frames: Lista de marcos actuales
        """
        self._clock_hand = 0
        self._current_pass = 0
        self._pages_examined = 0
        self._total_passes = 0
        self._initialized = True

    def _classify_page(self, page: 'Page') -> PageClass:
        """
        Clasifica una página según sus bits R y M.

        Args:
            page: Página a clasificar

        Returns:
            PageClass correspondiente
        """
        r = page.reference_bit
        m = page.modified_bit

        if not r and not m:
            return PageClass.NOT_REFERENCED_NOT_MODIFIED
        elif not r and m:
            return PageClass.NOT_REFERENCED_MODIFIED
        elif r and not m:
            return PageClass.REFERENCED_NOT_MODIFIED
        else:
            return PageClass.REFERENCED_MODIFIED

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona víctima usando Segunda Oportunidad Mejorado.

        Realiza hasta 4 pasadas buscando víctimas:
        1. Busca clase 0 sin modificar bits
        2. Busca clase 1, limpiando R de páginas vistas
        3. Busca clase 0 (tras limpiar R en pasada 2)
        4. Busca clase 1 (última opción)

        Complejidad: O(2n) - máximo 2 vueltas completas

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado

        Returns:
            ReplacementResult con la víctima seleccionada
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo no inicializado")

        self._pages_examined = 0

        # Buscar por clases en orden de preferencia
        for pass_num in range(4):
            self._current_pass = pass_num + 1
            target_class = pass_num % 2  # 0, 1, 0, 1
            clear_r = pass_num >= 1  # Limpiar R en pasadas 2, 3, 4

            result = self._scan_for_class(frames, target_class, clear_r)

            if result is not None:
                self._total_passes += pass_num + 1
                return result

        # Fallback: no debería llegar aquí si hay marcos ocupados
        raise RuntimeError("No se encontró víctima - estado inconsistente")

    def _scan_for_class(
        self,
        frames: List[Optional['Page']],
        target_class: int,
        clear_reference_bit: bool
    ) -> Optional[ReplacementResult]:
        """
        Realiza una pasada buscando páginas de una clase específica.

        Args:
            frames: Lista de marcos
            target_class: Clase objetivo (0 o 1)
            clear_reference_bit: Si True, limpia R de páginas vistas

        Returns:
            ReplacementResult si encuentra víctima, None si no
        """
        start_hand = self._clock_hand
        checked = 0

        while checked < self.num_frames:
            page = frames[self._clock_hand]
            self._pages_examined += 1

            if page is not None:
                current_class = self._classify_page(page)

                # ¿Encontramos víctima de la clase buscada?
                if current_class.value == target_class:
                    victim_frame = self._clock_hand
                    victim_page_id = page.page_id
                    requires_writeback = page.modified_bit

                    self._advance_hand()

                    return ReplacementResult(
                        victim_frame=victim_frame,
                        victim_page_id=victim_page_id,
                        requires_writeback=requires_writeback,
                        algorithm_metadata={
                            'page_class': current_class.name,
                            'pass_number': self._current_pass,
                            'pages_examined': self._pages_examined,
                            'selection_reason': f'Clase {target_class} (R={page.reference_bit}, M={page.modified_bit})'
                        }
                    )

                # Limpiar bit R si corresponde
                if clear_reference_bit:
                    page.reference_bit = False

            self._advance_hand()
            checked += 1

        return None

    def _advance_hand(self) -> None:
        """
        Avanza la manecilla del reloj.
        """
        self._clock_hand = (self._clock_hand + 1) % self.num_frames

    def on_page_access(
        self,
        frame_index: int,
        page: 'Page',
        access_type: AccessType,
        is_page_fault: bool
    ) -> None:
        """
        Actualiza bits tras acceso.

        Complejidad: O(1)

        Args:
            frame_index: Índice del marco
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: Si fue fault
        """
        self._access_count += 1

        page.reference_bit = True

        if access_type == AccessType.WRITE:
            page.modified_bit = True

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra página nueva cargada.

        Args:
            frame_index: Índice del marco
            page: Página cargada
        """
        page.reference_bit = True
        page.modified_bit = False

    def reset(self) -> None:
        """
        Reinicia el algoritmo.
        """
        self._clock_hand = 0
        self._current_pass = 0
        self._pages_examined = 0
        self._total_passes = 0
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo.
        """
        return {
            'time_select': 'O(2n) peor caso - máximo 2 vueltas completas',
            'time_update': 'O(1) - actualización de bits',
            'space': 'O(1) adicional - solo puntero y contadores'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas.
        """
        stats = super().get_statistics()
        stats.update({
            'clock_hand': self._clock_hand,
            'last_pass': self._current_pass,
            'last_pages_examined': self._pages_examined,
            'total_passes': self._total_passes
        })
        return stats

    def get_class_distribution(self, frames: List[Optional['Page']]) -> Dict[str, int]:
        """
        Retorna la distribución actual de clases de páginas.

        Args:
            frames: Lista de marcos

        Returns:
            Diccionario con conteo por clase
        """
        distribution = {cls.name: 0 for cls in PageClass}

        for page in frames:
            if page is not None:
                cls = self._classify_page(page)
                distribution[cls.name] += 1

        return distribution

    def __str__(self) -> str:
        return f"SegundaOportunidad(frames={self.num_frames}, hand={self._clock_hand})"
