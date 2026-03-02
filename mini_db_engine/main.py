#!/usr/bin/env python3
"""
Mini Motor de Base de Datos con Simulación Avanzada de
Algoritmos de Reemplazo de Página.

Este programa simula el comportamiento del subsistema de memoria virtual
de un sistema operativo aplicado a un entorno de base de datos con
buffer pool limitado.

Autor: Proyecto Académico - Sistemas Operativos
"""

import sys
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum, auto

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from algorithms import (
    ALGORITHMS,
    ReplacementAlgorithm,
    FIFOAlgorithm,
    OPTAlgorithm,
    LRUAlgorithm,
    LFUAlgorithm,
    MFUAlgorithm,
    ClockAlgorithm,
    SegundaOportunidadAlgorithm,
    NRUAlgorithm
)
from algorithms.base import AccessType
from core.page import Page, PageTable
from core.buffer_pool import BufferPool
from core.query_generator import QueryGenerator, AccessPattern
from core.metrics import MetricsCollector, SimulationMetrics


# ============================================================================
# CLASES PARA REGISTRO DETALLADO DE EVENTOS
# ============================================================================

class InterruptType(Enum):
    """Tipos de interrupciones del sistema."""
    PAGE_FAULT = "Page Fault"
    TIMER = "Timer (Clock Tick)"
    IO_COMPLETE = "I/O Completado"


class SyscallType(Enum):
    """Tipos de llamadas al sistema."""
    READ_PAGE = "read_page()"
    WRITE_PAGE = "write_page()"
    ALLOCATE_FRAME = "allocate_frame()"
    FREE_FRAME = "free_frame()"


@dataclass
class PageFaultEvent:
    """Registro detallado de un page fault."""
    time_step: int
    page_requested: int
    frame_used: int
    page_evicted: Optional[int]  # None si el marco estaba vacío
    required_writeback: bool
    frame_state_before: List[Optional[int]]
    frame_state_after: List[Optional[int]]


@dataclass
class PageHitEvent:
    """Registro detallado de un page hit."""
    time_step: int
    page_accessed: int
    frame_index: int
    access_type: str  # "READ" o "WRITE"


@dataclass
class InterruptEvent:
    """Registro de una interrupción."""
    time_step: int
    interrupt_type: InterruptType
    description: str
    handler_action: str


@dataclass
class SyscallEvent:
    """Registro de una llamada al sistema."""
    time_step: int
    syscall_type: SyscallType
    parameters: Dict[str, Any]
    result: str


@dataclass
class ReplacementTableEntry:
    """Entrada para la tabla de reemplazo clásica."""
    time_step: int
    page_requested: int
    frame_states: List[Optional[int]]  # Estado de cada marco después del acceso
    is_fault: bool
    victim_page: Optional[int]  # Página que fue reemplazada (si hubo)


@dataclass
class DetailedMetrics:
    """Métricas detalladas con todos los eventos."""
    page_faults: List[PageFaultEvent] = field(default_factory=list)
    page_hits: List[PageHitEvent] = field(default_factory=list)
    interrupts: List[InterruptEvent] = field(default_factory=list)
    syscalls: List[SyscallEvent] = field(default_factory=list)

    # Historial para tabla de reemplazo clásica
    replacement_history: List[ReplacementTableEntry] = field(default_factory=list)

    # Contadores
    total_accesses: int = 0
    total_faults: int = 0
    total_hits: int = 0
    total_writebacks: int = 0

    # Contadores por tipo de syscall
    syscall_counts: Dict[str, int] = field(default_factory=dict)
    interrupt_counts: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# SIMULADOR MEJORADO
# ============================================================================

class EnhancedSimulator:
    """
    Simulador mejorado con registro detallado de eventos.
    """

    def __init__(self, num_frames: int, total_pages: int, page_size: int = 4096):
        self.num_frames = num_frames
        self.total_pages = total_pages
        self.page_size = page_size
        self.detailed_metrics = DetailedMetrics()

        # Inicializar contadores de syscalls
        for syscall in SyscallType:
            self.detailed_metrics.syscall_counts[syscall.value] = 0
        for interrupt in InterruptType:
            self.detailed_metrics.interrupt_counts[interrupt.value] = 0

    def run_simulation(
        self,
        algorithm_name: str,
        access_sequence: List[int],
        write_ratio: float = 0.3
    ) -> DetailedMetrics:
        """
        Ejecuta la simulación con registro detallado.
        """
        import random
        random.seed(42)

        # Reiniciar métricas
        self.detailed_metrics = DetailedMetrics()
        for syscall in SyscallType:
            self.detailed_metrics.syscall_counts[syscall.value] = 0
        for interrupt in InterruptType:
            self.detailed_metrics.interrupt_counts[interrupt.value] = 0

        # Crear tabla de páginas
        page_table = PageTable(self.total_pages, self.page_size)

        # Crear algoritmo
        algorithm_class = ALGORITHMS[algorithm_name.lower()]
        algorithm = algorithm_class(self.num_frames)

        # Para OPT, configurar accesos futuros
        if algorithm_name.lower() == 'opt':
            algorithm.set_future_accesses(access_sequence)

        # Crear métricas básicas
        metrics_collector = MetricsCollector()

        # Crear buffer pool
        buffer_pool = BufferPool(
            num_frames=self.num_frames,
            algorithm=algorithm,
            page_table=page_table,
            metrics=metrics_collector
        )

        # Estado de los marcos (para registro)
        frames_state = [None] * self.num_frames
        page_to_frame = {}

        # Inicializar algoritmo
        algorithm.initialize([None] * self.num_frames)

        # Ejecutar simulación
        for time_step, page_id in enumerate(access_sequence, 1):
            self.detailed_metrics.total_accesses += 1

            # Determinar tipo de acceso
            is_write = random.random() < write_ratio
            access_type = AccessType.WRITE if is_write else AccessType.READ

            # Verificar si es hit o fault
            if page_id in page_to_frame:
                # PAGE HIT
                self._handle_page_hit(
                    time_step, page_id, page_to_frame[page_id],
                    "WRITE" if is_write else "READ"
                )
                self.detailed_metrics.total_hits += 1

                # Actualizar algoritmo
                frame_idx = page_to_frame[page_id]
                page = page_table.get_page(page_id)
                algorithm.on_page_access(frame_idx, page, access_type, False)

                # Registrar en historial de reemplazo (HIT)
                self._record_replacement_entry(
                    time_step, page_id, frames_state.copy(), False, None
                )

            else:
                # PAGE FAULT
                self.detailed_metrics.total_faults += 1

                # Registrar interrupción de page fault
                self._record_interrupt(
                    time_step,
                    InterruptType.PAGE_FAULT,
                    f"Página {page_id} no encontrada en memoria",
                    "Invocar manejador de page fault del kernel"
                )

                # Buscar marco libre o seleccionar víctima
                frame_idx = None
                for i in range(self.num_frames):
                    if frames_state[i] is None:
                        frame_idx = i
                        break

                page_evicted = None
                required_writeback = False

                if frame_idx is None:
                    # Necesitamos reemplazar - obtener víctima del algoritmo
                    frames_for_algorithm = []
                    for i in range(self.num_frames):
                        if frames_state[i] is not None:
                            frames_for_algorithm.append(page_table.get_page(frames_state[i]))
                        else:
                            frames_for_algorithm.append(None)

                    future = access_sequence[time_step:] if algorithm_name.lower() == 'opt' else None
                    result = algorithm.select_victim(frames_for_algorithm, future)
                    frame_idx = result.victim_frame

                    page_evicted = frames_state[frame_idx]
                    required_writeback = result.requires_writeback

                    # Registrar syscall de liberación
                    self._record_syscall(
                        time_step,
                        SyscallType.FREE_FRAME,
                        {"frame": frame_idx, "page": page_evicted},
                        f"Marco {frame_idx} liberado"
                    )

                    if required_writeback:
                        self.detailed_metrics.total_writebacks += 1
                        # Registrar syscall de escritura
                        self._record_syscall(
                            time_step,
                            SyscallType.WRITE_PAGE,
                            {"page": page_evicted, "frame": frame_idx},
                            f"Página {page_evicted} escrita a disco (dirty)"
                        )
                        # Registrar interrupción de I/O completado
                        self._record_interrupt(
                            time_step,
                            InterruptType.IO_COMPLETE,
                            f"Escritura de página {page_evicted} completada",
                            "Continuar con carga de nueva página"
                        )

                    # Actualizar mapeos
                    if page_evicted in page_to_frame:
                        del page_to_frame[page_evicted]

                # Registrar estado antes
                state_before = frames_state.copy()

                # Registrar syscall de asignación de marco
                self._record_syscall(
                    time_step,
                    SyscallType.ALLOCATE_FRAME,
                    {"frame": frame_idx, "page": page_id},
                    f"Marco {frame_idx} asignado a página {page_id}"
                )

                # Registrar syscall de lectura de página
                self._record_syscall(
                    time_step,
                    SyscallType.READ_PAGE,
                    {"page": page_id, "frame": frame_idx},
                    f"Página {page_id} cargada desde disco al marco {frame_idx}"
                )

                # Registrar interrupción de I/O completado
                self._record_interrupt(
                    time_step,
                    InterruptType.IO_COMPLETE,
                    f"Lectura de página {page_id} completada",
                    "Página disponible en memoria, continuar proceso"
                )

                # Actualizar estado
                frames_state[frame_idx] = page_id
                page_to_frame[page_id] = frame_idx

                # Registrar estado después
                state_after = frames_state.copy()

                # Registrar evento de page fault
                self._record_page_fault(
                    time_step, page_id, frame_idx,
                    page_evicted, required_writeback,
                    state_before, state_after
                )

                # Actualizar algoritmo
                page = page_table.get_page(page_id)
                page.load_into_memory()
                algorithm.on_page_load(frame_idx, page)
                algorithm.on_page_access(frame_idx, page, access_type, True)

                # Registrar en historial de reemplazo (FAULT)
                self._record_replacement_entry(
                    time_step, page_id, frames_state.copy(), True, page_evicted
                )

            # Simular timer interrupt periódico (cada 100 accesos)
            if time_step % 100 == 0:
                self._record_interrupt(
                    time_step,
                    InterruptType.TIMER,
                    "Interrupción de reloj del sistema",
                    "Actualizar contadores, verificar bits R para NRU"
                )

        return self.detailed_metrics

    def _handle_page_hit(self, time_step: int, page_id: int, frame_idx: int, access_type: str):
        """Registra un page hit."""
        event = PageHitEvent(
            time_step=time_step,
            page_accessed=page_id,
            frame_index=frame_idx,
            access_type=access_type
        )
        self.detailed_metrics.page_hits.append(event)

    def _record_page_fault(
        self, time_step: int, page_requested: int, frame_used: int,
        page_evicted: Optional[int], required_writeback: bool,
        state_before: List, state_after: List
    ):
        """Registra un page fault."""
        event = PageFaultEvent(
            time_step=time_step,
            page_requested=page_requested,
            frame_used=frame_used,
            page_evicted=page_evicted,
            required_writeback=required_writeback,
            frame_state_before=state_before,
            frame_state_after=state_after
        )
        self.detailed_metrics.page_faults.append(event)

    def _record_interrupt(
        self, time_step: int, interrupt_type: InterruptType,
        description: str, handler_action: str
    ):
        """Registra una interrupción."""
        event = InterruptEvent(
            time_step=time_step,
            interrupt_type=interrupt_type,
            description=description,
            handler_action=handler_action
        )
        self.detailed_metrics.interrupts.append(event)
        self.detailed_metrics.interrupt_counts[interrupt_type.value] += 1

    def _record_syscall(
        self, time_step: int, syscall_type: SyscallType,
        parameters: Dict, result: str
    ):
        """Registra una llamada al sistema."""
        event = SyscallEvent(
            time_step=time_step,
            syscall_type=syscall_type,
            parameters=parameters,
            result=result
        )
        self.detailed_metrics.syscalls.append(event)
        self.detailed_metrics.syscall_counts[syscall_type.value] += 1

    def _record_replacement_entry(
        self, time_step: int, page_requested: int,
        frame_states: List[Optional[int]], is_fault: bool,
        victim_page: Optional[int]
    ):
        """Registra una entrada en el historial de reemplazo."""
        entry = ReplacementTableEntry(
            time_step=time_step,
            page_requested=page_requested,
            frame_states=frame_states,
            is_fault=is_fault,
            victim_page=victim_page
        )
        self.detailed_metrics.replacement_history.append(entry)


# ============================================================================
# FUNCIONES DE VISUALIZACIÓN
# ============================================================================

def print_header():
    """Imprime el encabezado del programa."""
    print("\n" + "=" * 80)
    print("║" + " " * 78 + "║")
    print("║" + "MINI MOTOR DE BASE DE DATOS".center(78) + "║")
    print("║" + "Simulación de Algoritmos de Reemplazo de Página".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("=" * 80)


def print_menu():
    """Imprime el menú de selección de algoritmo."""
    print("\n" + "─" * 80)
    print("SELECCIONE EL ALGORITMO DE REEMPLAZO DE PÁGINA:")
    print("─" * 80)

    algorithms_info = [
        ("1", "FIFO", "First-In First-Out", "Reemplaza la página más antigua"),
        ("2", "OPT", "Óptimo de Belady", "Reemplaza la página que se usará más tarde (teórico)"),
        ("3", "LRU", "Least Recently Used", "Reemplaza la página menos recientemente usada"),
        ("4", "LFU", "Least Frequently Used", "Reemplaza la página menos frecuentemente usada"),
        ("5", "MFU", "Most Frequently Used", "Reemplaza la página más frecuentemente usada"),
        ("6", "CLOCK", "Algoritmo del Reloj", "Aproximación de LRU con bit de referencia"),
        ("7", "SEGUNDA OPORTUNIDAD", "Second Chance Mejorado", "Clock con bits R y M"),
        ("8", "NRU", "Not Recently Used", "Clasificación en 4 clases por bits R y M"),
    ]

    for num, name, full_name, description in algorithms_info:
        print(f"\n  [{num}] {name}")
        print(f"      Nombre completo: {full_name}")
        print(f"      Descripción: {description}")

    print("\n  [0] SALIR")
    print("─" * 80)


def print_pattern_menu():
    """Imprime el menú de selección de patrón de acceso."""
    print("\n" + "─" * 80)
    print("SELECCIONE EL PATRÓN DE ACCESO:")
    print("─" * 80)

    patterns_info = [
        ("1", "LOCALITY", "Localidad 80-20", "80% de accesos al 20% de páginas (realista)"),
        ("2", "UNIFORM", "Distribución Uniforme", "Todas las páginas con igual probabilidad"),
        ("3", "SEQUENTIAL", "Acceso Secuencial", "Páginas en orden consecutivo"),
        ("4", "ZIPF", "Distribución Zipfiana", "Pocas páginas muy populares (web)"),
        ("5", "WORKING_SET", "Conjunto de Trabajo", "Subconjunto que cambia gradualmente"),
        ("6", "RANDOM", "Aleatorio Puro", "Completamente aleatorio"),
    ]

    for num, name, full_name, description in patterns_info:
        print(f"\n  [{num}] {name}")
        print(f"      Descripción: {full_name}")
        print(f"      Uso típico: {description}")

    print("─" * 80)


def get_user_config() -> Dict[str, Any]:
    """Obtiene la configuración del usuario de forma interactiva."""

    print_header()

    # Seleccionar algoritmo
    print_menu()

    algorithm_map = {
        '1': 'fifo',
        '2': 'opt',
        '3': 'lru',
        '4': 'lfu',
        '5': 'mfu',
        '6': 'clock',
        '7': 'segunda_oportunidad',
        '8': 'nru'
    }

    while True:
        choice = input("\n  Ingrese su opción [1-8, 0 para salir]: ").strip()
        if choice == '0':
            print("\n¡Hasta luego!")
            sys.exit(0)
        if choice in algorithm_map:
            algorithm = algorithm_map[choice]
            break
        print("  ⚠ Opción inválida. Intente de nuevo.")

    # Seleccionar patrón de acceso
    print_pattern_menu()

    pattern_map = {
        '1': 'locality',
        '2': 'uniform',
        '3': 'sequential',
        '4': 'zipf',
        '5': 'working_set',
        '6': 'random'
    }

    while True:
        choice = input("\n  Ingrese su opción [1-6]: ").strip()
        if choice in pattern_map:
            pattern = pattern_map[choice]
            break
        print("  ⚠ Opción inválida. Intente de nuevo.")

    # Obtener parámetros numéricos
    print("\n" + "─" * 80)
    print("CONFIGURACIÓN DE PARÁMETROS:")
    print("─" * 80)

    # Número de marcos
    while True:
        try:
            frames = input("\n  Número de marcos en el buffer pool [default=4]: ").strip()
            frames = int(frames) if frames else 4
            if frames > 0:
                break
            print("  ⚠ Debe ser mayor que 0.")
        except ValueError:
            print("  ⚠ Ingrese un número válido.")

    # Número de páginas
    while True:
        try:
            pages = input(f"  Número total de páginas [default=20, mínimo={frames+1}]: ").strip()
            pages = int(pages) if pages else 20
            if pages > frames:
                break
            print(f"  ⚠ Debe ser mayor que el número de marcos ({frames}).")
        except ValueError:
            print("  ⚠ Ingrese un número válido.")

    # Número de accesos
    while True:
        try:
            accesses = input("  Número de accesos a simular [default=100]: ").strip()
            accesses = int(accesses) if accesses else 100
            if accesses > 0:
                break
            print("  ⚠ Debe ser mayor que 0.")
        except ValueError:
            print("  ⚠ Ingrese un número válido.")

    return {
        'algorithm': algorithm,
        'pattern': pattern,
        'num_frames': frames,
        'total_pages': pages,
        'num_accesses': accesses
    }


def print_replacement_table(metrics: DetailedMetrics, num_frames: int, max_columns: int = 20):
    """
    Imprime la tabla de reemplazo clásica.

    Formato:
    - Filas: Marcos (M0, M1, M2, ...)
    - Columnas: Páginas solicitadas en secuencia
    - Última fila: indica si fue Fault (F) o Hit (H)
    """
    print("\n" + "=" * 100)
    print(" TABLA DE REEMPLAZO DE PÁGINAS (FORMATO CLÁSICO) ".center(100, "="))
    print("=" * 100)

    if not metrics.replacement_history:
        print("\n  No hay historial de reemplazo.")
        return

    # Limitar columnas si hay muchos accesos
    history = metrics.replacement_history[:max_columns]
    total_entries = len(metrics.replacement_history)
    showing_limited = total_entries > max_columns

    # Calcular ancho de columna (mínimo 4 para que quepa "P##")
    col_width = 5

    # Calcular ancho total de la tabla
    label_width = 12  # Para "Marco X" o "Página Sol."
    table_width = label_width + (col_width * len(history)) + len(history) + 1

    print(f"\n  Algoritmo: {metrics.replacement_history[0].time_step if history else 'N/A'}")
    if showing_limited:
        print(f"  Mostrando primeros {max_columns} de {total_entries} accesos")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # LÍNEA SUPERIOR
    # ═══════════════════════════════════════════════════════════════════
    print("  ┌" + "─" * label_width + "┬" + ("─" * col_width + "┬") * (len(history) - 1) + "─" * col_width + "┐")

    # ═══════════════════════════════════════════════════════════════════
    # FILA DE PÁGINAS SOLICITADAS
    # ═══════════════════════════════════════════════════════════════════
    header_row = f"  │{'Pág. Solic.':^{label_width}}│"
    for entry in history:
        header_row += f"{'P' + str(entry.page_requested):^{col_width}}│"
    print(header_row)

    # Línea separadora
    print("  ├" + "─" * label_width + "┼" + ("─" * col_width + "┼") * (len(history) - 1) + "─" * col_width + "┤")

    # ═══════════════════════════════════════════════════════════════════
    # FILAS DE MARCOS
    # ═══════════════════════════════════════════════════════════════════
    for frame_idx in range(num_frames):
        row = f"  │{'Marco ' + str(frame_idx):^{label_width}}│"

        for entry in history:
            page_in_frame = entry.frame_states[frame_idx]
            if page_in_frame is not None:
                cell = f"P{page_in_frame}"
            else:
                cell = "---"
            row += f"{cell:^{col_width}}│"

        print(row)

    # Línea separadora antes de Fault/Hit
    print("  ├" + "─" * label_width + "┼" + ("─" * col_width + "┼") * (len(history) - 1) + "─" * col_width + "┤")

    # ═══════════════════════════════════════════════════════════════════
    # FILA DE FAULT/HIT
    # ═══════════════════════════════════════════════════════════════════
    fault_row = f"  │{'¿Fault?':^{label_width}}│"
    for entry in history:
        if entry.is_fault:
            cell = "F"
        else:
            cell = "H"
        fault_row += f"{cell:^{col_width}}│"
    print(fault_row)

    # ═══════════════════════════════════════════════════════════════════
    # FILA DE PÁGINA EXPULSADA (solo si hubo reemplazo)
    # ═══════════════════════════════════════════════════════════════════
    evict_row = f"  │{'Pág. Sale':^{label_width}}│"
    for entry in history:
        if entry.victim_page is not None:
            cell = f"P{entry.victim_page}"
        else:
            cell = "---"
        evict_row += f"{cell:^{col_width}}│"
    print(evict_row)

    # LÍNEA INFERIOR
    print("  └" + "─" * label_width + "┴" + ("─" * col_width + "┴") * (len(history) - 1) + "─" * col_width + "┘")

    # ═══════════════════════════════════════════════════════════════════
    # LEYENDA
    # ═══════════════════════════════════════════════════════════════════
    print("\n  LEYENDA:")
    print("  ─────────")
    print("  • Pág. Solic. = Página solicitada en ese instante")
    print("  • Marco X     = Contenido del marco X después del acceso")
    print("  • F           = Fault (página no estaba en memoria, se cargó)")
    print("  • H           = Hit (página ya estaba en memoria)")
    print("  • Pág. Sale   = Página que fue expulsada para hacer espacio (si aplica)")
    print("  • ---         = Marco vacío o sin expulsión")

    # Resumen
    faults = sum(1 for e in history if e.is_fault)
    hits = sum(1 for e in history if not e.is_fault)
    print(f"\n  RESUMEN (primeros {len(history)} accesos):")
    print(f"  • Page Faults: {faults}")
    print(f"  • Page Hits: {hits}")
    print(f"  • Hit Ratio: {(hits/len(history)*100):.2f}%" if history else "N/A")


def print_page_faults_table(metrics: DetailedMetrics, max_rows: int = 50):
    """Imprime la tabla detallada de page faults."""
    print("\n" + "=" * 100)
    print(" TABLA DETALLADA DE PAGE FAULTS ".center(100, "="))
    print("=" * 100)

    if not metrics.page_faults:
        print("\n  No hubo page faults durante la simulación.")
        return

    # Encabezado
    print("\n┌" + "─" * 8 + "┬" + "─" * 12 + "┬" + "─" * 12 + "┬" + "─" * 15 + "┬" + "─" * 12 + "┬" + "─" * 35 + "┐")
    print(f"│{'Tiempo':^8}│{'Página':^12}│{'Marco':^12}│{'Pág. Expulsada':^15}│{'Writeback':^12}│{'Estado del Buffer':^35}│")
    print("│" + " " * 8 + "│" + "Solicitada".center(12) + "│" + "Asignado".center(12) + "│" + "(si aplica)".center(15) + "│" + "(Dirty)".center(12) + "│" + "(después del fault)".center(35) + "│")
    print("├" + "─" * 8 + "┼" + "─" * 12 + "┼" + "─" * 12 + "┼" + "─" * 15 + "┼" + "─" * 12 + "┼" + "─" * 35 + "┤")

    faults_to_show = metrics.page_faults[:max_rows]

    for fault in faults_to_show:
        evicted_str = str(fault.page_evicted) if fault.page_evicted is not None else "---"
        writeback_str = "SÍ" if fault.required_writeback else "NO"

        # Formatear estado del buffer
        state_str = "["
        for i, p in enumerate(fault.frame_state_after):
            if p is not None:
                state_str += f"M{i}:P{p}"
            else:
                state_str += f"M{i}:---"
            if i < len(fault.frame_state_after) - 1:
                state_str += ", "
        state_str += "]"

        # Truncar si es muy largo
        if len(state_str) > 33:
            state_str = state_str[:30] + "..."

        print(f"│{fault.time_step:^8}│{fault.page_requested:^12}│{fault.frame_used:^12}│{evicted_str:^15}│{writeback_str:^12}│{state_str:^35}│")

    print("└" + "─" * 8 + "┴" + "─" * 12 + "┴" + "─" * 12 + "┴" + "─" * 15 + "┴" + "─" * 12 + "┴" + "─" * 35 + "┘")

    if len(metrics.page_faults) > max_rows:
        print(f"\n  ... y {len(metrics.page_faults) - max_rows} page faults más (mostrando primeros {max_rows})")

    print(f"\n  TOTAL PAGE FAULTS: {len(metrics.page_faults)}")
    print(f"  TOTAL WRITEBACKS (páginas sucias escritas a disco): {metrics.total_writebacks}")


def print_page_hits_table(metrics: DetailedMetrics, max_rows: int = 30):
    """Imprime la tabla detallada de page hits."""
    print("\n" + "=" * 80)
    print(" TABLA DETALLADA DE PAGE HITS (ACIERTOS) ".center(80, "="))
    print("=" * 80)

    if not metrics.page_hits:
        print("\n  No hubo page hits durante la simulación.")
        return

    # Encabezado
    print("\n┌" + "─" * 10 + "┬" + "─" * 15 + "┬" + "─" * 15 + "┬" + "─" * 15 + "┬" + "─" * 20 + "┐")
    print(f"│{'Tiempo':^10}│{'Página':^15}│{'Marco':^15}│{'Tipo Acceso':^15}│{'Descripción':^20}│")
    print("├" + "─" * 10 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┼" + "─" * 15 + "┼" + "─" * 20 + "┤")

    hits_to_show = metrics.page_hits[:max_rows]

    for hit in hits_to_show:
        desc = "Lectura de datos" if hit.access_type == "READ" else "Escritura (dirty)"
        print(f"│{hit.time_step:^10}│{hit.page_accessed:^15}│{hit.frame_index:^15}│{hit.access_type:^15}│{desc:^20}│")

    print("└" + "─" * 10 + "┴" + "─" * 15 + "┴" + "─" * 15 + "┴" + "─" * 15 + "┴" + "─" * 20 + "┘")

    if len(metrics.page_hits) > max_rows:
        print(f"\n  ... y {len(metrics.page_hits) - max_rows} page hits más (mostrando primeros {max_rows})")

    print(f"\n  TOTAL PAGE HITS: {len(metrics.page_hits)}")


def print_interrupts_detail(metrics: DetailedMetrics, max_rows: int = 30):
    """Imprime el detalle de interrupciones simuladas."""
    print("\n" + "=" * 110)
    print(" DETALLE DE INTERRUPCIONES SIMULADAS ".center(110, "="))
    print("=" * 110)

    # Descripción de tipos de interrupción
    print("\n┌" + "─" * 108 + "┐")
    print("│" + " TIPOS DE INTERRUPCIONES EN EL SISTEMA ".center(108) + "│")
    print("├" + "─" * 108 + "┤")

    interrupt_descriptions = [
        ("Page Fault", "INT 14 (x86)", "Se genera cuando el proceso accede a una página que no está en memoria física.",
         "El kernel suspende el proceso, localiza la página en disco y la carga en un marco."),
        ("Timer", "INT 0 (x86)", "Interrupción periódica del reloj del sistema (típicamente cada 10-20ms).",
         "Actualiza contadores de tiempo, puede limpiar bits R para algoritmos como NRU."),
        ("I/O Complete", "IRQ específico", "Se genera cuando una operación de I/O de disco termina.",
         "El kernel desbloquea procesos esperando esa operación y actualiza estructuras.")
    ]

    for name, vector, desc, action in interrupt_descriptions:
        print(f"│  • {name:<20} [{vector}]" + " " * (108 - 27 - len(vector) - len(name)) + "│")
        print(f"│    Descripción: {desc:<89}│")
        print(f"│    Acción del kernel: {action:<83}│")
        print("│" + " " * 108 + "│")

    print("└" + "─" * 108 + "┘")

    # Resumen de interrupciones
    print("\n┌" + "─" * 50 + "┐")
    print("│" + " RESUMEN DE INTERRUPCIONES ".center(50) + "│")
    print("├" + "─" * 30 + "┬" + "─" * 19 + "┤")
    print(f"│{'Tipo de Interrupción':^30}│{'Cantidad':^19}│")
    print("├" + "─" * 30 + "┼" + "─" * 19 + "┤")

    for int_type, count in metrics.interrupt_counts.items():
        print(f"│{int_type:^30}│{count:^19}│")

    total_ints = sum(metrics.interrupt_counts.values())
    print("├" + "─" * 30 + "┼" + "─" * 19 + "┤")
    print(f"│{'TOTAL':^30}│{total_ints:^19}│")
    print("└" + "─" * 30 + "┴" + "─" * 19 + "┘")

    # Detalle de algunas interrupciones
    if metrics.interrupts:
        print("\n  Primeras interrupciones registradas:")
        print("  " + "─" * 100)

        for i, intr in enumerate(metrics.interrupts[:max_rows]):
            print(f"  [{intr.time_step:>5}] {intr.interrupt_type.value:<20} | {intr.description}")
            print(f"         Acción: {intr.handler_action}")
            if i < min(len(metrics.interrupts), max_rows) - 1:
                print("  " + "─" * 100)

        if len(metrics.interrupts) > max_rows:
            print(f"\n  ... y {len(metrics.interrupts) - max_rows} interrupciones más")


def print_syscalls_detail(metrics: DetailedMetrics, max_rows: int = 30):
    """Imprime el detalle de llamadas al sistema."""
    print("\n" + "=" * 120)
    print(" DETALLE DE LLAMADAS AL SISTEMA (SYSCALLS) ".center(120, "="))
    print("=" * 120)

    # Descripción de tipos de syscalls
    print("\n┌" + "─" * 118 + "┐")
    print("│" + " TIPOS DE LLAMADAS AL SISTEMA UTILIZADAS ".center(118) + "│")
    print("├" + "─" * 118 + "┤")

    syscall_descriptions = [
        ("read_page()", "Lee una página desde el almacenamiento secundario (disco/SSD) a memoria RAM.",
         "Parámetros: page_id (identificador de página), frame (marco destino)",
         "Latencia típica: 5-10ms (SSD) o 10-15ms (HDD)"),
        ("write_page()", "Escribe una página modificada (dirty) desde memoria RAM al almacenamiento.",
         "Parámetros: page_id (identificador de página), frame (marco origen)",
         "Se ejecuta antes de reemplazar una página con bit M=1"),
        ("allocate_frame()", "Asigna un marco de página libre para cargar una nueva página.",
         "Parámetros: frame (índice del marco), page (página a cargar)",
         "El kernel actualiza las tablas de páginas y estructuras de control"),
        ("free_frame()", "Libera un marco de página para ser reutilizado.",
         "Parámetros: frame (índice del marco), page (página que ocupaba)",
         "Se invalida la entrada en la tabla de páginas del proceso")
    ]

    for name, desc, params, extra in syscall_descriptions:
        print(f"│  • {name:<20}" + " " * (118 - 24 - len(name)) + "│")
        print(f"│    {desc:<114}│")
        print(f"│    {params:<114}│")
        print(f"│    {extra:<114}│")
        print("│" + " " * 118 + "│")

    print("└" + "─" * 118 + "┘")

    # Resumen de syscalls
    print("\n┌" + "─" * 50 + "┐")
    print("│" + " RESUMEN DE LLAMADAS AL SISTEMA ".center(50) + "│")
    print("├" + "─" * 30 + "┬" + "─" * 19 + "┤")
    print(f"│{'Tipo de Syscall':^30}│{'Cantidad':^19}│")
    print("├" + "─" * 30 + "┼" + "─" * 19 + "┤")

    for syscall_type, count in metrics.syscall_counts.items():
        print(f"│{syscall_type:^30}│{count:^19}│")

    total_syscalls = sum(metrics.syscall_counts.values())
    print("├" + "─" * 30 + "┼" + "─" * 19 + "┤")
    print(f"│{'TOTAL':^30}│{total_syscalls:^19}│")
    print("└" + "─" * 30 + "┴" + "─" * 19 + "┘")

    # Detalle de algunas syscalls
    if metrics.syscalls:
        print("\n  Primeras llamadas al sistema registradas:")
        print("  " + "─" * 110)

        for i, syscall in enumerate(metrics.syscalls[:max_rows]):
            params_str = ", ".join(f"{k}={v}" for k, v in syscall.parameters.items())
            print(f"  [{syscall.time_step:>5}] {syscall.syscall_type.value:<20} | Params: {params_str}")
            print(f"         Resultado: {syscall.result}")
            if i < min(len(metrics.syscalls), max_rows) - 1:
                print("  " + "─" * 110)

        if len(metrics.syscalls) > max_rows:
            print(f"\n  ... y {len(metrics.syscalls) - max_rows} syscalls más")


def print_summary(metrics: DetailedMetrics, config: Dict[str, Any], execution_time: float):
    """Imprime el resumen final de la simulación."""
    print("\n" + "=" * 80)
    print(" RESUMEN FINAL DE LA SIMULACIÓN ".center(80, "="))
    print("=" * 80)

    hit_ratio = (metrics.total_hits / metrics.total_accesses * 100) if metrics.total_accesses > 0 else 0
    fault_rate = (metrics.total_faults / metrics.total_accesses * 100) if metrics.total_accesses > 0 else 0

    print(f"""
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CONFIGURACIÓN                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│  Algoritmo:              {config['algorithm'].upper():<52}│
│  Patrón de acceso:       {config['pattern'].upper():<52}│
│  Número de marcos:       {config['num_frames']:<52}│
│  Número de páginas:      {config['total_pages']:<52}│
│  Número de accesos:      {config['num_accesses']:<52}│
├──────────────────────────────────────────────────────────────────────────────┤
│                           RESULTADOS                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  Total de accesos:              {metrics.total_accesses:<45}│
│  Page Faults:                   {metrics.total_faults:<45}│
│  Page Hits:                     {metrics.total_hits:<45}│
│  Hit Ratio:                     {hit_ratio:.2f}%{' ':<42}│
│  Fault Rate:                    {fault_rate:.2f}%{' ':<42}│
│  Tiempo de ejecución:           {execution_time:.4f} segundos{' ':<34}│
├──────────────────────────────────────────────────────────────────────────────┤
│                           EVENTOS DEL SISTEMA                                │
├──────────────────────────────────────────────────────────────────────────────┤
│  Interrupciones simuladas:      {sum(metrics.interrupt_counts.values()):<45}│
│    - Page Fault:                {metrics.interrupt_counts.get('Page Fault', 0):<45}│
│    - Timer:                     {metrics.interrupt_counts.get('Timer (Clock Tick)', 0):<45}│
│    - I/O Complete:              {metrics.interrupt_counts.get('I/O Completado', 0):<45}│
│  Llamadas al sistema:           {sum(metrics.syscall_counts.values()):<45}│
│    - read_page():               {metrics.syscall_counts.get('read_page()', 0):<45}│
│    - write_page():              {metrics.syscall_counts.get('write_page()', 0):<45}│
│    - allocate_frame():          {metrics.syscall_counts.get('allocate_frame()', 0):<45}│
│    - free_frame():              {metrics.syscall_counts.get('free_frame()', 0):<45}│
│  Escrituras a disco:            {metrics.total_writebacks:<45}│
└──────────────────────────────────────────────────────────────────────────────┘
""")


def get_pattern_enum(pattern_name: str) -> AccessPattern:
    """Convierte nombre de patrón a enum."""
    patterns = {
        'uniform': AccessPattern.UNIFORM,
        'locality': AccessPattern.LOCALITY,
        'sequential': AccessPattern.SEQUENTIAL,
        'random': AccessPattern.RANDOM,
        'zipf': AccessPattern.ZIPF,
        'working_set': AccessPattern.WORKING_SET
    }
    return patterns.get(pattern_name, AccessPattern.LOCALITY)


def main():
    """Función principal del programa."""

    # Obtener configuración del usuario
    config = get_user_config()

    print("\n" + "=" * 80)
    print(" INICIANDO SIMULACIÓN ".center(80, "="))
    print("=" * 80)

    print(f"\n  Configuración seleccionada:")
    print(f"    • Algoritmo: {config['algorithm'].upper()}")
    print(f"    • Patrón: {config['pattern']}")
    print(f"    • Marcos: {config['num_frames']}")
    print(f"    • Páginas: {config['total_pages']}")
    print(f"    • Accesos: {config['num_accesses']}")

    # Generar secuencia de accesos
    print(f"\n  Generando secuencia de accesos ({config['pattern']})...")

    query_gen = QueryGenerator(
        total_pages=config['total_pages'],
        write_ratio=0.3,
        seed=42
    )

    pattern = get_pattern_enum(config['pattern'])
    access_sequence = query_gen.generate_page_ids(pattern, config['num_accesses'])

    print(f"  ✓ Secuencia generada: {len(access_sequence)} accesos")
    if len(access_sequence) <= 30:
        print(f"    Secuencia: {access_sequence}")
    else:
        print(f"    Primeros 30: {access_sequence[:30]}...")

    # Crear y ejecutar simulador
    print(f"\n  Ejecutando simulación con {config['algorithm'].upper()}...")

    simulator = EnhancedSimulator(
        num_frames=config['num_frames'],
        total_pages=config['total_pages']
    )

    start_time = time.perf_counter()

    detailed_metrics = simulator.run_simulation(
        algorithm_name=config['algorithm'],
        access_sequence=access_sequence,
        write_ratio=0.3
    )

    execution_time = time.perf_counter() - start_time

    print(f"  ✓ Simulación completada en {execution_time:.4f} segundos")

    # Mostrar resultados detallados
    # Tabla de reemplazo clásica (primeras 20 columnas)
    print_replacement_table(detailed_metrics, config['num_frames'], max_columns=20)

    print_page_faults_table(detailed_metrics)
    print_page_hits_table(detailed_metrics)
    print_interrupts_detail(detailed_metrics)
    print_syscalls_detail(detailed_metrics)
    print_summary(detailed_metrics, config, execution_time)

    # Preguntar si desea ejecutar otra simulación
    print("\n" + "─" * 80)
    another = input("  ¿Desea ejecutar otra simulación? [s/n]: ").strip().lower()

    if another == 's':
        main()
    else:
        print("\n  ¡Gracias por usar el simulador!")
        print("  Proyecto Académico - Sistemas Operativos")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
