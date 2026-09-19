"""Modelo de categoría de movimiento."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    """Categoría activa asociada a ingresos o gastos."""

    id: int
    nombre: str
    tipo: str
