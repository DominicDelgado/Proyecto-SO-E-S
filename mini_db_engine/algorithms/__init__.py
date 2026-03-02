"""
Módulo de algoritmos de reemplazo de página.

Este módulo implementa el patrón Strategy para los algoritmos de reemplazo
de página utilizados en el subsistema de memoria virtual del simulador
de base de datos.

Algoritmos implementados:
- FIFO (First-In First-Out)
- OPT (Óptimo de Belady)
- LRU (Least Recently Used)
- LFU (Least Frequently Used)
- MFU (Most Frequently Used)
- Clock (Reloj)
- Segunda Oportunidad
- NRU (Not Recently Used)

Autor: Proyecto Académico - Sistemas Operativos
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.base import ReplacementAlgorithm
from algorithms.fifo import FIFOAlgorithm
from algorithms.opt import OPTAlgorithm
from algorithms.lru import LRUAlgorithm
from algorithms.lfu import LFUAlgorithm
from algorithms.mfu import MFUAlgorithm
from algorithms.clock import ClockAlgorithm
from algorithms.segunda_oportunidad import SegundaOportunidadAlgorithm
from algorithms.nru import NRUAlgorithm

__all__ = [
    'ReplacementAlgorithm',
    'FIFOAlgorithm',
    'OPTAlgorithm',
    'LRUAlgorithm',
    'LFUAlgorithm',
    'MFUAlgorithm',
    'ClockAlgorithm',
    'SegundaOportunidadAlgorithm',
    'NRUAlgorithm'
]

# Diccionario de algoritmos disponibles para fácil acceso
ALGORITHMS = {
    'fifo': FIFOAlgorithm,
    'opt': OPTAlgorithm,
    'lru': LRUAlgorithm,
    'lfu': LFUAlgorithm,
    'mfu': MFUAlgorithm,
    'clock': ClockAlgorithm,
    'segunda_oportunidad': SegundaOportunidadAlgorithm,
    'nru': NRUAlgorithm
}
