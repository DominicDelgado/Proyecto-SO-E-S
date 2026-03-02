"""
Algoritmo de Reemplazo NRU (Not Recently Used).

Modelo Formal:
--------------
NRU clasifica páginas usando bits R (referencia) y M (modificación)
en 4 clases, y selecciona una página aleatoria de la clase más baja
no vacía.

Clasificación:
- Clase 0: R=0, M=0 - No referenciada, no modificada
- Clase 1: R=0, M=1 - No referenciada, modificada
- Clase 2: R=1, M=0 - Referenciada, no modificada
- Clase 3: R=1, M=1 - Referenciada, modificada

Algoritmo:
1. Clasificar todas las páginas en memoria
2. Seleccionar aleatoriamente de la clase más baja no vacía
3. Periódicamente limpiar todos los bits R (clock interrupt)

Reset periódico de R:
El bit R se limpia periódicamente (en cada interrupción de reloj
del sistema, típicamente cada 20ms). Esto permite distinguir
entre páginas usadas "recientemente" vs "hace tiempo".

Nota: M no se limpia porque indica página sucia que debe
escribirse a disco antes de ser reemplazada.

Características:
- Simple de implementar en hardware
- Buen balance entre rendimiento y overhead
- Usado en sistemas como MINIX
- Aleatorización evita patrones desfavorables

Complejidad:
- Selección de víctima: O(n) - clasificar todas las páginas
- Actualización: O(1) - modificar bits
- Reset periódico: O(n) - limpiar todos los bits R
- Espacio: O(1) adicional

Autor: Proyecto Académico - Sistemas Operativos
"""

import random
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from enum import IntEnum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm, ReplacementResult, AccessType

if TYPE_CHECKING:
    from core.page import Page


class NRUClass(IntEnum):
    """
    Clases NRU ordenadas por preferencia de reemplazo.

    Menor valor = mejor candidata para reemplazo.
    """
    CLASS_0 = 0  # R=0, M=0 - Mejor candidata
    CLASS_1 = 1  # R=0, M=1
    CLASS_2 = 2  # R=1, M=0
    CLASS_3 = 3  # R=1, M=1 - Peor candidata


class NRUAlgorithm(ReplacementAlgorithm):
    """
    Implementación del algoritmo NRU.

    Diferencias con Segunda Oportunidad:
    - NRU selecciona ALEATORIAMENTE dentro de la clase más baja
    - NRU simula reset periódico del bit R

    La aleatorización es importante porque:
    - Evita siempre reemplazar la misma página
    - Distribuye el "desgaste" uniformemente
    - Más justo con páginas de la misma clase

    Attributes:
        _clock_ticks: Contador de ticks de reloj simulados
        _r_reset_interval: Intervalo de accesos para reset de R
        _last_selected_class: Última clase de donde se seleccionó
        _random_seed: Semilla para reproducibilidad (opcional)
    """

    def __init__(self, num_frames: int, r_reset_interval: int = 100, seed: Optional[int] = None):
        """
        Inicializa el algoritmo NRU.

        Args:
            num_frames: Número de marcos en el buffer pool
            r_reset_interval: Accesos entre resets del bit R
            seed: Semilla para el generador aleatorio (reproducibilidad)
        """
        super().__init__("NRU", num_frames)
        self._clock_ticks: int = 0
        self._r_reset_interval: int = r_reset_interval
        self._r_resets: int = 0
        self._last_selected_class: Optional[NRUClass] = None
        self._rng = random.Random(seed)

    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa el algoritmo.

        Args:
            frames: Lista de marcos actuales
        """
        self._clock_ticks = 0
        self._r_resets = 0
        self._last_selected_class = None
        self._initialized = True

    def _classify_page(self, page: 'Page') -> NRUClass:
        """
        Clasifica una página según sus bits R y M.

        Args:
            page: Página a clasificar

        Returns:
            NRUClass correspondiente
        """
        r = 1 if page.reference_bit else 0
        m = 1 if page.modified_bit else 0

        # Clase = 2*R + M
        class_num = 2 * r + m
        return NRUClass(class_num)

    def _classify_all_pages(
        self,
        frames: List[Optional['Page']]
    ) -> Dict[NRUClass, List[int]]:
        """
        Clasifica todas las páginas en sus respectivas clases.

        Args:
            frames: Lista de marcos

        Returns:
            Diccionario de clase -> lista de índices de marco
        """
        classes: Dict[NRUClass, List[int]] = {
            NRUClass.CLASS_0: [],
            NRUClass.CLASS_1: [],
            NRUClass.CLASS_2: [],
            NRUClass.CLASS_3: []
        }

        for frame_idx, page in enumerate(frames):
            if page is not None:
                cls = self._classify_page(page)
                classes[cls].append(frame_idx)

        return classes

    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona víctima usando política NRU.

        Clasifica todas las páginas y selecciona aleatoriamente
        de la clase más baja no vacía.

        Complejidad: O(n) - clasificar todas las páginas

        Args:
            frames: Lista de marcos actuales
            future_accesses: No utilizado

        Returns:
            ReplacementResult con la víctima seleccionada
        """
        if not self._initialized:
            raise RuntimeError("Algoritmo NRU no inicializado")

        # Clasificar todas las páginas
        classes = self._classify_all_pages(frames)

        # Buscar la clase más baja no vacía
        victim_frame = -1
        selected_class = None

        for cls in [NRUClass.CLASS_0, NRUClass.CLASS_1,
                    NRUClass.CLASS_2, NRUClass.CLASS_3]:
            if classes[cls]:
                # Seleccionar aleatoriamente de esta clase
                victim_frame = self._rng.choice(classes[cls])
                selected_class = cls
                break

        if victim_frame == -1:
            raise RuntimeError("No se encontró víctima - estado inconsistente")

        self._last_selected_class = selected_class

        page = frames[victim_frame]
        victim_page_id = page.page_id
        requires_writeback = page.modified_bit

        return ReplacementResult(
            victim_frame=victim_frame,
            victim_page_id=victim_page_id,
            requires_writeback=requires_writeback,
            algorithm_metadata={
                'selected_class': selected_class.name,
                'class_size': len(classes[selected_class]),
                'class_distribution': {c.name: len(v) for c, v in classes.items()},
                'r_bit': page.reference_bit,
                'm_bit': page.modified_bit,
                'selection_reason': f'Aleatorio de clase {selected_class.value} ({len(classes[selected_class])} candidatas)'
            }
        )

    def _check_r_reset(self, frames: List[Optional['Page']]) -> bool:
        """
        Verifica si es momento de resetear los bits R.

        Simula la interrupción de reloj del sistema operativo
        que periódicamente limpia los bits R.

        Args:
            frames: Lista de marcos

        Returns:
            True si se realizó reset
        """
        if self._clock_ticks > 0 and self._clock_ticks % self._r_reset_interval == 0:
            # Limpiar todos los bits R
            for page in frames:
                if page is not None:
                    page.reference_bit = False
            self._r_resets += 1
            return True
        return False

    def on_page_access(
        self,
        frame_index: int,
        page: 'Page',
        access_type: AccessType,
        is_page_fault: bool
    ) -> None:
        """
        Actualiza estado tras acceso.

        Incluye verificación de reset periódico del bit R.

        Complejidad: O(1) normal, O(n) si hay reset

        Args:
            frame_index: Índice del marco
            page: Página accedida
            access_type: Tipo de acceso
            is_page_fault: Si fue fault
        """
        self._access_count += 1
        self._clock_ticks += 1

        # Actualizar bits
        page.reference_bit = True
        if access_type == AccessType.WRITE:
            page.modified_bit = True

    def periodic_r_reset(self, frames: List[Optional['Page']]) -> bool:
        """
        Realiza reset periódico de bits R (llamar desde BufferPool).

        Este método simula la interrupción de reloj del SO.
        Debe llamarse periódicamente durante la simulación.

        Args:
            frames: Lista de marcos

        Returns:
            True si se realizó reset
        """
        return self._check_r_reset(frames)

    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Registra página nueva.

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
        self._clock_ticks = 0
        self._r_resets = 0
        self._last_selected_class = None
        self._access_count = 0
        self._initialized = False

    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad del algoritmo NRU.
        """
        return {
            'time_select': 'O(n) - clasificar todas las páginas',
            'time_update': 'O(1) normal, O(n) en reset periódico',
            'space': 'O(1) adicional - solo contadores',
            'note': f'Reset de R cada {self._r_reset_interval} accesos'
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas específicas de NRU.
        """
        stats = super().get_statistics()
        stats.update({
            'clock_ticks': self._clock_ticks,
            'r_resets': self._r_resets,
            'r_reset_interval': self._r_reset_interval,
            'last_selected_class': self._last_selected_class.name if self._last_selected_class else None
        })
        return stats

    def __str__(self) -> str:
        return f"NRU(frames={self.num_frames}, ticks={self._clock_ticks})"
