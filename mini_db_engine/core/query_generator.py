"""
Generador de Consultas Sintéticas.

Este módulo genera secuencias de acceso a páginas que simulan
diferentes patrones de uso en bases de datos y aplicaciones.

Modelo Formal:
--------------
Un generador de consultas G se define como:
G = (P, D, params)

Donde:
- P = {0, 1, ..., n-1}: conjunto de IDs de página
- D: distribución de probabilidad sobre P
- params: parámetros específicos del patrón

Patrones implementados:
-----------------------
1. UNIFORM (Distribución Uniforme):
   - P(página i) = 1/n para todo i
   - Modela acceso completamente aleatorio
   - No exhibe localidad

2. LOCALITY (Localidad 80-20):
   - 80% de accesos al 20% de páginas "calientes"
   - 20% de accesos al 80% de páginas "frías"
   - Modela el principio de Pareto en bases de datos

3. SEQUENTIAL (Acceso Secuencial):
   - Páginas accedidas en orden consecutivo
   - Modela table scans y procesamiento batch
   - Alta localidad espacial

4. RANDOM (Aleatorio Puro):
   - Similar a UNIFORM pero con seed configurable
   - Para reproducibilidad de experimentos

5. ZIPF (Distribución Zipfiana):
   - P(página k) ∝ 1/k^s donde s es el exponente
   - Modela popularidad en sistemas web
   - Muy alta localidad

6. WORKING_SET (Conjunto de Trabajo):
   - Accede a un subconjunto que cambia gradualmente
   - Modela comportamiento real de programas
   - Combinación de localidad temporal y espacial

Principios de localidad:
------------------------
- Localidad temporal: páginas accedidas recientemente
  tienen alta probabilidad de ser accedidas de nuevo.

- Localidad espacial: si una página es accedida, páginas
  cercanas tienen alta probabilidad de ser accedidas.

Autor: Proyecto Académico - Sistemas Operativos
"""

import random
import math
from typing import List, Optional, Generator, Dict, Any, Tuple
from enum import Enum, auto
from dataclasses import dataclass


class AccessPattern(Enum):
    """
    Patrones de acceso disponibles.

    Cada patrón modela un comportamiento diferente de acceso
    a datos en sistemas reales.
    """
    UNIFORM = auto()      # Distribución uniforme
    LOCALITY = auto()     # Localidad 80-20
    SEQUENTIAL = auto()   # Acceso secuencial
    RANDOM = auto()       # Aleatorio con seed
    ZIPF = auto()         # Distribución Zipfiana
    WORKING_SET = auto()  # Conjunto de trabajo dinámico


@dataclass
class AccessEvent:
    """
    Representa un evento de acceso a página.

    Attributes:
        page_id: ID de la página accedida
        is_write: True si es acceso de escritura
        timestamp: Número de secuencia del acceso
    """
    page_id: int
    is_write: bool
    timestamp: int


class QueryGenerator:
    """
    Generador de secuencias de acceso a páginas.

    Genera secuencias de accesos según diferentes patrones
    de distribución, simulando comportamiento de consultas
    en bases de datos.

    Atributos configurables:
    - total_pages: Número total de páginas en el sistema
    - write_ratio: Proporción de accesos de escritura (0.0 - 1.0)
    - seed: Semilla para reproducibilidad

    Attributes:
        _total_pages: Número total de páginas
        _write_ratio: Proporción de escrituras
        _rng: Generador de números aleatorios
        _access_count: Contador de accesos generados
    """

    def __init__(
        self,
        total_pages: int,
        write_ratio: float = 0.3,
        seed: Optional[int] = None
    ):
        """
        Inicializa el generador de consultas.

        Args:
            total_pages: Número total de páginas disponibles
            write_ratio: Proporción de accesos de escritura (default 30%)
            seed: Semilla para el generador aleatorio

        Raises:
            ValueError: Si parámetros fuera de rango
        """
        if total_pages <= 0:
            raise ValueError(f"total_pages debe ser > 0: {total_pages}")
        if not 0.0 <= write_ratio <= 1.0:
            raise ValueError(f"write_ratio debe estar en [0, 1]: {write_ratio}")

        self._total_pages = total_pages
        self._write_ratio = write_ratio
        self._seed = seed
        self._rng = random.Random(seed)
        self._access_count = 0

        # Cache para distribución Zipf
        self._zipf_weights: Optional[List[float]] = None
        self._zipf_cumulative: Optional[List[float]] = None

    def generate(
        self,
        pattern: AccessPattern,
        num_accesses: int,
        **kwargs
    ) -> List[AccessEvent]:
        """
        Genera una secuencia de accesos según el patrón especificado.

        Args:
            pattern: Patrón de acceso a utilizar
            num_accesses: Número de accesos a generar
            **kwargs: Parámetros específicos del patrón

        Returns:
            Lista de AccessEvent

        Raises:
            ValueError: Si el patrón no es reconocido
        """
        generators = {
            AccessPattern.UNIFORM: self._generate_uniform,
            AccessPattern.LOCALITY: self._generate_locality,
            AccessPattern.SEQUENTIAL: self._generate_sequential,
            AccessPattern.RANDOM: self._generate_random,
            AccessPattern.ZIPF: self._generate_zipf,
            AccessPattern.WORKING_SET: self._generate_working_set
        }

        if pattern not in generators:
            raise ValueError(f"Patrón no reconocido: {pattern}")

        return list(generators[pattern](num_accesses, **kwargs))

    def generate_page_ids(
        self,
        pattern: AccessPattern,
        num_accesses: int,
        **kwargs
    ) -> List[int]:
        """
        Genera solo los IDs de página (sin metadatos de acceso).

        Útil para el algoritmo OPT que necesita conocer los accesos futuros.

        Args:
            pattern: Patrón de acceso
            num_accesses: Número de accesos
            **kwargs: Parámetros del patrón

        Returns:
            Lista de page_ids
        """
        events = self.generate(pattern, num_accesses, **kwargs)
        return [event.page_id for event in events]

    def _generate_uniform(
        self,
        num_accesses: int,
        **kwargs
    ) -> Generator[AccessEvent, None, None]:
        """
        Genera accesos con distribución uniforme.

        Cada página tiene la misma probabilidad de ser seleccionada.
        No exhibe localidad - peor caso para algoritmos LRU/Clock.

        Complejidad: O(1) por acceso

        Yields:
            AccessEvent con página seleccionada uniformemente
        """
        for i in range(num_accesses):
            page_id = self._rng.randint(0, self._total_pages - 1)
            is_write = self._rng.random() < self._write_ratio

            self._access_count += 1
            yield AccessEvent(
                page_id=page_id,
                is_write=is_write,
                timestamp=self._access_count
            )

    def _generate_locality(
        self,
        num_accesses: int,
        hot_ratio: float = 0.2,
        hot_access_ratio: float = 0.8,
        **kwargs
    ) -> Generator[AccessEvent, None, None]:
        """
        Genera accesos con localidad 80-20 (principio de Pareto).

        El 20% de las páginas ("calientes") recibe el 80% de los accesos.
        Este patrón es común en bases de datos reales.

        Args:
            hot_ratio: Proporción de páginas "calientes" (default 20%)
            hot_access_ratio: Proporción de accesos a páginas calientes (default 80%)

        Yields:
            AccessEvent siguiendo distribución 80-20
        """
        # Calcular páginas calientes
        num_hot = max(1, int(self._total_pages * hot_ratio))
        hot_pages = list(range(num_hot))
        cold_pages = list(range(num_hot, self._total_pages))

        for i in range(num_accesses):
            # Decidir si acceder a página caliente o fría
            if self._rng.random() < hot_access_ratio:
                # Acceso a página caliente
                page_id = self._rng.choice(hot_pages)
            else:
                # Acceso a página fría
                if cold_pages:
                    page_id = self._rng.choice(cold_pages)
                else:
                    page_id = self._rng.choice(hot_pages)

            is_write = self._rng.random() < self._write_ratio

            self._access_count += 1
            yield AccessEvent(
                page_id=page_id,
                is_write=is_write,
                timestamp=self._access_count
            )

    def _generate_sequential(
        self,
        num_accesses: int,
        start_page: int = 0,
        wrap_around: bool = True,
        **kwargs
    ) -> Generator[AccessEvent, None, None]:
        """
        Genera accesos secuenciales.

        Simula operaciones como table scans donde las páginas
        se acceden en orden consecutivo.

        Alta localidad espacial - óptimo para prefetching.

        Args:
            start_page: Página inicial (default 0)
            wrap_around: Si True, vuelve al inicio al llegar al final

        Yields:
            AccessEvent en orden secuencial
        """
        current_page = start_page % self._total_pages

        for i in range(num_accesses):
            page_id = current_page
            is_write = self._rng.random() < self._write_ratio

            self._access_count += 1
            yield AccessEvent(
                page_id=page_id,
                is_write=is_write,
                timestamp=self._access_count
            )

            # Avanzar a siguiente página
            current_page += 1
            if wrap_around:
                current_page %= self._total_pages
            else:
                current_page = min(current_page, self._total_pages - 1)

    def _generate_random(
        self,
        num_accesses: int,
        **kwargs
    ) -> Generator[AccessEvent, None, None]:
        """
        Genera accesos aleatorios puros.

        Similar a uniform pero usa la semilla del generador
        para reproducibilidad exacta.

        Yields:
            AccessEvent aleatorio
        """
        # Idéntico a uniform, pero documentado como patrón explícito
        yield from self._generate_uniform(num_accesses, **kwargs)

    def _generate_zipf(
        self,
        num_accesses: int,
        alpha: float = 1.0,
        **kwargs
    ) -> Generator[AccessEvent, None, None]:
        """
        Genera accesos con distribución Zipfiana.

        La distribución Zipf modela fenómenos donde unos pocos
        elementos son extremadamente populares:
        - P(k) ∝ 1/k^α donde k es el rango

        Con α=1.0: la página más popular tiene probabilidad ~1/H_n
        donde H_n es el n-ésimo número armónico.

        Args:
            alpha: Exponente de Zipf (default 1.0)
                   Mayor α = distribución más sesgada

        Yields:
            AccessEvent siguiendo ley de Zipf
        """
        # Construir distribución acumulativa (una vez)
        if self._zipf_weights is None or len(self._zipf_weights) != self._total_pages:
            self._build_zipf_distribution(alpha)

        for i in range(num_accesses):
            # Muestrear usando búsqueda binaria
            r = self._rng.random()
            page_id = self._sample_from_cumulative(r)

            is_write = self._rng.random() < self._write_ratio

            self._access_count += 1
            yield AccessEvent(
                page_id=page_id,
                is_write=is_write,
                timestamp=self._access_count
            )

    def _build_zipf_distribution(self, alpha: float) -> None:
        """
        Construye la distribución Zipf acumulativa.

        Args:
            alpha: Exponente de Zipf
        """
        # Pesos Zipf: w[k] = 1/(k+1)^α
        weights = [1.0 / ((k + 1) ** alpha) for k in range(self._total_pages)]

        # Normalizar
        total = sum(weights)
        self._zipf_weights = [w / total for w in weights]

        # Construir distribución acumulativa
        cumulative = []
        acc = 0.0
        for w in self._zipf_weights:
            acc += w
            cumulative.append(acc)
        self._zipf_cumulative = cumulative

    def _sample_from_cumulative(self, r: float) -> int:
        """
        Muestrea un índice de la distribución acumulativa.

        Usa búsqueda binaria para eficiencia O(log n).

        Args:
            r: Valor aleatorio en [0, 1)

        Returns:
            Índice muestreado
        """
        # Búsqueda binaria
        lo, hi = 0, len(self._zipf_cumulative) - 1

        while lo < hi:
            mid = (lo + hi) // 2
            if self._zipf_cumulative[mid] < r:
                lo = mid + 1
            else:
                hi = mid

        return lo

    def _generate_working_set(
        self,
        num_accesses: int,
        working_set_size: int = 10,
        shift_interval: int = 100,
        shift_amount: int = 2,
        **kwargs
    ) -> Generator[AccessEvent, None, None]:
        """
        Genera accesos con modelo de conjunto de trabajo dinámico.

        El conjunto de trabajo es un subconjunto de páginas que
        se accede frecuentemente. Este conjunto "se desplaza"
        gradualmente, simulando cambios de fase en un programa.

        Modelo:
        1. Mantener un conjunto de trabajo de tamaño fijo
        2. La mayoría de accesos (90%) van al working set
        3. Periódicamente, el working set se desplaza

        Args:
            working_set_size: Tamaño del conjunto de trabajo
            shift_interval: Accesos entre desplazamientos
            shift_amount: Páginas a desplazar cada vez

        Yields:
            AccessEvent siguiendo modelo de working set
        """
        ws_size = min(working_set_size, self._total_pages)
        shift = min(shift_amount, self._total_pages - ws_size)

        # Conjunto de trabajo inicial
        ws_start = 0
        working_set = list(range(ws_start, ws_start + ws_size))

        for i in range(num_accesses):
            # 90% de accesos al working set
            if self._rng.random() < 0.9:
                page_id = self._rng.choice(working_set)
            else:
                # 10% accesos fuera del working set
                outside = [p for p in range(self._total_pages) if p not in working_set]
                if outside:
                    page_id = self._rng.choice(outside)
                else:
                    page_id = self._rng.choice(working_set)

            is_write = self._rng.random() < self._write_ratio

            self._access_count += 1
            yield AccessEvent(
                page_id=page_id,
                is_write=is_write,
                timestamp=self._access_count
            )

            # Desplazar working set periódicamente
            if (i + 1) % shift_interval == 0:
                ws_start = (ws_start + shift) % self._total_pages
                working_set = [
                    (ws_start + j) % self._total_pages
                    for j in range(ws_size)
                ]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estadísticas del generador.

        Returns:
            Diccionario con estadísticas
        """
        return {
            'total_pages': self._total_pages,
            'write_ratio': self._write_ratio,
            'seed': self._seed,
            'accesses_generated': self._access_count
        }

    def reset(self, seed: Optional[int] = None) -> None:
        """
        Reinicia el generador.

        Args:
            seed: Nueva semilla (usa la original si None)
        """
        if seed is not None:
            self._seed = seed

        self._rng = random.Random(self._seed)
        self._access_count = 0
        self._zipf_weights = None
        self._zipf_cumulative = None

    def __str__(self) -> str:
        return (f"QueryGenerator(pages={self._total_pages}, "
                f"write_ratio={self._write_ratio:.2f})")
