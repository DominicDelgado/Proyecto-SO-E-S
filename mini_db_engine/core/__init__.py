"""
Módulo core del Mini Motor de Base de Datos.

Este módulo contiene los componentes fundamentales del simulador:
- Page: Modelo de página de memoria virtual
- BufferPool: Administrador del buffer pool
- QueryGenerator: Generador de patrones de acceso
- MetricsCollector: Recolector y analizador de métricas

Autor: Proyecto Académico - Sistemas Operativos
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.page import Page, PageState
from core.buffer_pool import BufferPool
from core.query_generator import QueryGenerator, AccessPattern
from core.metrics import MetricsCollector, SimulationMetrics

__all__ = [
    'Page',
    'PageState',
    'BufferPool',
    'QueryGenerator',
    'AccessPattern',
    'MetricsCollector',
    'SimulationMetrics'
]
