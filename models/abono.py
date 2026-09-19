"""Modelo de un abono aplicado a una deuda."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Abono:
    """Pago parcial o total registrado sobre una deuda."""

    fecha: date
    valor: float
    deuda_id: int | None = None
    descripcion: str = ""
    id: int | None = None

    @property
    def descripcion_mostrada(self) -> str:
        return self.descripcion or "Sin descripción"
