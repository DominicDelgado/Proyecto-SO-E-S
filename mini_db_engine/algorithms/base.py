"""
Clase base abstracta para algoritmos de reemplazo de página.

Este módulo define la interfaz Strategy que todos los algoritmos de reemplazo
deben implementar. Siguiendo el patrón de diseño Strategy, permite intercambiar
algoritmos de reemplazo en tiempo de ejecución sin modificar el código cliente.

Modelo Formal:
--------------
Sea M = {m₁, m₂, ..., mₙ} el conjunto de marcos de página en memoria principal.
Sea P = {p₁, p₂, ..., pₖ} el conjunto de páginas virtuales.
Sea f: P → M ∪ {∅} la función de mapeo de páginas a marcos.

Un algoritmo de reemplazo R define:
- select_victim(M, P, context) → mᵢ ∈ M : selecciona el marco a reemplazar
- update(mᵢ, pⱼ, access_type) : actualiza el estado interno

Complejidad:
- La clase base no impone complejidad; cada implementación la define.

Autor: Proyecto Académico - Sistemas Operativos
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if TYPE_CHECKING:
    from core.page import Page


class AccessType(Enum):
    """
    Tipo de acceso a página.

    READ: Acceso de lectura (solo establece bit R)
    WRITE: Acceso de escritura (establece bits R y M)
    """
    READ = "read"
    WRITE = "write"


@dataclass
class ReplacementResult:
    """
    Resultado de una operación de reemplazo.

    Attributes:
        victim_frame: Índice del marco seleccionado como víctima
        victim_page_id: ID de la página que será reemplazada (None si marco vacío)
        requires_writeback: True si la página víctima fue modificada (M=1)
        algorithm_metadata: Información adicional del algoritmo (para debugging)
    """
    victim_frame: int
    victim_page_id: Optional[int]
    requires_writeback: bool
    algorithm_metadata: Dict[str, Any]


class ReplacementAlgorithm(ABC):
    """
    Interfaz abstracta para algoritmos de reemplazo de página.

    Esta clase define el contrato que todos los algoritmos de reemplazo
    deben cumplir. Implementa el patrón Strategy permitiendo que el
    BufferPool intercambie algoritmos dinámicamente.

    Modelo de Estado:
    -----------------
    Cada algoritmo mantiene su propio estado interno que se actualiza
    con cada acceso a página. Este estado puede incluir:
    - Orden de llegada (FIFO)
    - Tiempo de último acceso (LRU)
    - Contador de frecuencia (LFU/MFU)
    - Bits de referencia y modificación (Clock, NRU)

    Invariantes:
    ------------
    1. select_victim() siempre retorna un marco válido si buffer lleno
    2. El estado se actualiza atómicamente (no hay estados inconsistentes)
    3. reset() restaura el algoritmo a su estado inicial

    Attributes:
        name: Nombre identificador del algoritmo
        num_frames: Número de marcos en el buffer pool
        _initialized: Indica si el algoritmo fue inicializado
    """

    def __init__(self, name: str, num_frames: int):
        """
        Inicializa el algoritmo de reemplazo.

        Args:
            name: Nombre identificador del algoritmo
            num_frames: Número de marcos disponibles en el buffer pool

        Raises:
            ValueError: Si num_frames <= 0
        """
        if num_frames <= 0:
            raise ValueError(f"num_frames debe ser > 0, recibido: {num_frames}")

        self.name = name
        self.num_frames = num_frames
        self._initialized = False
        self._access_count = 0

    @abstractmethod
    def initialize(self, frames: List[Optional['Page']]) -> None:
        """
        Inicializa el estado interno del algoritmo.

        Este método debe llamarse antes de cualquier operación de reemplazo.
        Permite que el algoritmo construya sus estructuras de datos iniciales
        basándose en el estado actual del buffer pool.

        Args:
            frames: Lista de marcos actuales (puede contener None para marcos vacíos)

        Post-condición:
            self._initialized == True
        """
        pass

    @abstractmethod
    def select_victim(
        self,
        frames: List[Optional['Page']],
        future_accesses: Optional[List[int]] = None
    ) -> ReplacementResult:
        """
        Selecciona el marco víctima para reemplazo.

        Este es el método central del algoritmo de reemplazo. Analiza el
        estado actual de los marcos y selecciona cuál debe ser reemplazado
        cuando ocurre un page fault y el buffer está lleno.

        Args:
            frames: Lista de marcos actuales con páginas cargadas
            future_accesses: (Opcional) Lista de futuros accesos para OPT

        Returns:
            ReplacementResult con información del marco víctima

        Raises:
            RuntimeError: Si el algoritmo no fue inicializado

        Pre-condición:
            - self._initialized == True
            - len(frames) == self.num_frames
            - Todos los marcos contienen páginas (buffer lleno)
        """
        pass

    @abstractmethod
    def on_page_access(
        self,
        frame_index: int,
        page: 'Page',
        access_type: AccessType,
        is_page_fault: bool
    ) -> None:
        """
        Actualiza el estado del algoritmo cuando se accede a una página.

        Este método se llama cada vez que ocurre un acceso a página,
        ya sea un hit o después de cargar una página por fault.
        Permite que el algoritmo mantenga su estado actualizado.

        Args:
            frame_index: Índice del marco accedido
            page: Página que fue accedida
            access_type: Tipo de acceso (READ o WRITE)
            is_page_fault: True si el acceso causó un page fault

        Efectos:
            - Actualiza estructuras internas (timestamps, contadores, etc.)
            - Establece bits R y M según corresponda
        """
        pass

    @abstractmethod
    def on_page_load(self, frame_index: int, page: 'Page') -> None:
        """
        Notifica al algoritmo que una página fue cargada en un marco.

        Se llama después de resolver un page fault y cargar la página
        en el marco designado. Permite que el algoritmo registre
        la nueva página en sus estructuras.

        Args:
            frame_index: Índice del marco donde se cargó la página
            page: Página recién cargada
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Reinicia el algoritmo a su estado inicial.

        Limpia todas las estructuras de datos y contadores,
        permitiendo reutilizar el algoritmo para una nueva simulación.

        Post-condición:
            self._initialized == False
            Todas las estructuras internas vacías
        """
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas del algoritmo.

        Returns:
            Diccionario con estadísticas específicas del algoritmo
        """
        return {
            'algorithm_name': self.name,
            'num_frames': self.num_frames,
            'access_count': self._access_count,
            'initialized': self._initialized
        }

    @abstractmethod
    def get_complexity(self) -> Dict[str, str]:
        """
        Retorna la complejidad temporal y espacial del algoritmo.

        Returns:
            Diccionario con:
                - 'time_select': Complejidad de select_victim()
                - 'time_update': Complejidad de on_page_access()
                - 'space': Complejidad espacial
        """
        pass

    def __str__(self) -> str:
        return f"{self.name}(frames={self.num_frames})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', num_frames={self.num_frames})"
