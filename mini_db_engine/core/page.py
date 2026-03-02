"""
Modelo de Página de Memoria Virtual.

Este módulo define la estructura de una página en el contexto
de la simulación del subsistema de memoria virtual.

Modelo Formal:
--------------
Una página P se define como una tupla:
P = (id, size, R, M, state, data)

Donde:
- id ∈ ℕ: identificador único de la página
- size ∈ ℕ: tamaño en bytes
- R ∈ {0, 1}: bit de referencia (accedida recientemente)
- M ∈ {0, 1}: bit de modificación (dirty bit)
- state ∈ {ON_DISK, IN_MEMORY, LOADING}: estado actual
- data: contenido de la página (simulado)

Comportamiento de bits:
-----------------------
Bit R (Reference):
- Se establece a 1 cuando la página es accedida
- El SO lo limpia periódicamente (clock interrupt)
- Usado por algoritmos Clock, NRU, Segunda Oportunidad

Bit M (Modified/Dirty):
- Se establece a 1 cuando la página es escrita
- Solo se limpia cuando la página se escribe a disco
- Indica necesidad de writeback antes de reemplazo

Transiciones de estado:
-----------------------
ON_DISK → LOADING: Cuando se inicia carga por page fault
LOADING → IN_MEMORY: Cuando la carga completa
IN_MEMORY → ON_DISK: Cuando la página es reemplazada

Autor: Proyecto Académico - Sistemas Operativos
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Any, Dict
import time


class PageState(Enum):
    """
    Estados posibles de una página.

    ON_DISK: Página reside solo en almacenamiento secundario
    IN_MEMORY: Página cargada en un marco del buffer pool
    LOADING: Página en proceso de carga (I/O pendiente)
    """
    ON_DISK = auto()
    IN_MEMORY = auto()
    LOADING = auto()


@dataclass
class Page:
    """
    Representa una página de memoria virtual.

    En el contexto de base de datos, una página corresponde a un
    bloque de datos de tamaño fijo que puede contener registros,
    índices, o metadatos.

    Modelo de simulación:
    - page_id simula la dirección de la página en el espacio virtual
    - size simula el tamaño del bloque de datos
    - reference_bit y modified_bit simulan bits de hardware
    - state simula las transiciones de página

    Attributes:
        page_id: Identificador único de la página (dirección virtual)
        size: Tamaño de la página en bytes
        reference_bit: Bit R - indica acceso reciente
        modified_bit: Bit M - indica modificación (dirty)
        state: Estado actual de la página
        load_time: Timestamp de cuando fue cargada en memoria
        last_access_time: Timestamp del último acceso
        access_count: Número de accesos a esta página
        data: Datos contenidos (simulados como diccionario)
    """
    page_id: int
    size: int = 4096  # Tamaño típico de página: 4KB

    # Bits de control (hardware simulado)
    reference_bit: bool = False
    modified_bit: bool = False

    # Estado de la página
    state: PageState = PageState.ON_DISK

    # Metadatos de tiempo
    load_time: Optional[float] = None
    last_access_time: Optional[float] = None

    # Estadísticas
    access_count: int = 0

    # Datos simulados
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validación post-inicialización."""
        if self.page_id < 0:
            raise ValueError(f"page_id debe ser >= 0, recibido: {self.page_id}")
        if self.size <= 0:
            raise ValueError(f"size debe ser > 0, recibido: {self.size}")

    def mark_accessed(self, is_write: bool = False) -> None:
        """
        Marca la página como accedida.

        Simula el comportamiento del hardware cuando se accede a una página:
        - Siempre establece R=1
        - Si es escritura, también establece M=1

        Args:
            is_write: True si el acceso es de escritura

        Pre-condición:
            self.state == PageState.IN_MEMORY
        """
        self.reference_bit = True
        self.last_access_time = time.perf_counter()
        self.access_count += 1

        if is_write:
            self.modified_bit = True

    def load_into_memory(self) -> None:
        """
        Simula la carga de la página en memoria.

        Transición: ON_DISK/LOADING → IN_MEMORY

        Efectos:
        - Cambia estado a IN_MEMORY
        - Registra timestamp de carga
        - Inicializa R=1, M=0
        """
        self.state = PageState.IN_MEMORY
        self.load_time = time.perf_counter()
        self.last_access_time = self.load_time
        self.reference_bit = True
        self.modified_bit = False

    def evict_from_memory(self) -> bool:
        """
        Simula la expulsión de la página de memoria.

        Transición: IN_MEMORY → ON_DISK

        Returns:
            True si requiere writeback (M=1), False si no

        Post-condición:
            self.state == PageState.ON_DISK
            self.reference_bit == False
            self.modified_bit == False
        """
        requires_writeback = self.modified_bit

        self.state = PageState.ON_DISK
        self.reference_bit = False
        self.modified_bit = False
        self.load_time = None

        return requires_writeback

    def clear_reference_bit(self) -> None:
        """
        Limpia el bit de referencia.

        Simula la interrupción de reloj del SO que
        periódicamente limpia los bits R.
        """
        self.reference_bit = False

    def is_dirty(self) -> bool:
        """
        Verifica si la página está modificada (dirty).

        Returns:
            True si M=1 (necesita writeback)
        """
        return self.modified_bit

    def is_in_memory(self) -> bool:
        """
        Verifica si la página está en memoria.

        Returns:
            True si está cargada en un marco
        """
        return self.state == PageState.IN_MEMORY

    def get_class_nru(self) -> int:
        """
        Obtiene la clase NRU de la página.

        Returns:
            Clase 0-3 basada en bits R y M
        """
        r = 1 if self.reference_bit else 0
        m = 1 if self.modified_bit else 0
        return 2 * r + m

    def get_metadata(self) -> Dict[str, Any]:
        """
        Retorna metadatos de la página para reportes.

        Returns:
            Diccionario con información de la página
        """
        return {
            'page_id': self.page_id,
            'size': self.size,
            'state': self.state.name,
            'reference_bit': self.reference_bit,
            'modified_bit': self.modified_bit,
            'access_count': self.access_count,
            'nru_class': self.get_class_nru(),
            'load_time': self.load_time,
            'last_access_time': self.last_access_time
        }

    def __hash__(self) -> int:
        """Hash basado en page_id para uso en conjuntos/diccionarios."""
        return hash(self.page_id)

    def __eq__(self, other: object) -> bool:
        """Igualdad basada en page_id."""
        if not isinstance(other, Page):
            return False
        return self.page_id == other.page_id

    def __str__(self) -> str:
        return (f"Page(id={self.page_id}, R={int(self.reference_bit)}, "
                f"M={int(self.modified_bit)}, state={self.state.name})")

    def __repr__(self) -> str:
        return (f"Page(page_id={self.page_id}, size={self.size}, "
                f"R={self.reference_bit}, M={self.modified_bit}, "
                f"state={self.state}, accesses={self.access_count})")


class PageTable:
    """
    Tabla de páginas que mapea IDs de página a objetos Page.

    En un sistema real, la tabla de páginas mapea direcciones virtuales
    a direcciones físicas (marcos). Aquí simulamos este mapeo.

    Attributes:
        _pages: Diccionario de page_id -> Page
        _total_pages: Número total de páginas en el sistema
        _page_size: Tamaño de cada página
    """

    def __init__(self, total_pages: int, page_size: int = 4096):
        """
        Inicializa la tabla de páginas.

        Args:
            total_pages: Número total de páginas virtuales
            page_size: Tamaño de cada página en bytes
        """
        if total_pages <= 0:
            raise ValueError(f"total_pages debe ser > 0: {total_pages}")

        self._total_pages = total_pages
        self._page_size = page_size
        self._pages: Dict[int, Page] = {}

        # Pre-crear todas las páginas (en disco inicialmente)
        for i in range(total_pages):
            self._pages[i] = Page(page_id=i, size=page_size)

    def get_page(self, page_id: int) -> Page:
        """
        Obtiene una página por su ID.

        Args:
            page_id: ID de la página

        Returns:
            Objeto Page correspondiente

        Raises:
            ValueError: Si page_id está fuera de rango
        """
        if page_id < 0 or page_id >= self._total_pages:
            raise ValueError(f"page_id {page_id} fuera de rango [0, {self._total_pages})")

        return self._pages[page_id]

    def get_pages_in_memory(self) -> list:
        """
        Retorna lista de páginas actualmente en memoria.

        Returns:
            Lista de Pages con state == IN_MEMORY
        """
        return [p for p in self._pages.values() if p.is_in_memory()]

    @property
    def total_pages(self) -> int:
        """Número total de páginas."""
        return self._total_pages

    @property
    def page_size(self) -> int:
        """Tamaño de cada página."""
        return self._page_size

    def __len__(self) -> int:
        return self._total_pages

    def __iter__(self):
        return iter(self._pages.values())
