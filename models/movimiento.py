"""Modelo de un movimiento financiero."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

TIPO_INGRESO = "ingreso"
TIPO_GASTO = "gasto"
TIPOS_VALIDOS = (TIPO_INGRESO, TIPO_GASTO)


@dataclass
class Movimiento:
    """Movimiento de ingreso o gasto.

    ``categoria_nombre`` es una proyección de lectura resuelta por la consulta
    (JOIN con ``categorias``); no se persiste en la tabla ``movimientos``.
    """

    fecha: date
    tipo: str
    valor: float
    categoria_id: int | None = None
    descripcion: str = ""
    abono_id: int | None = None
    suscripcion_id: int | None = None
    id: int | None = None
    categoria_nombre: str = ""

    @property
    def es_ingreso(self) -> bool:
        return self.tipo == TIPO_INGRESO

    @property
    def es_abono(self) -> bool:
        """Indica si el movimiento es el reflejo de un abono a una deuda.

        Un abono devuelve un compromiso ya contraído: no es un consumo nuevo,
        aunque sí sea una salida real de dinero. La columna ``abono_id`` es la
        que lo distingue de un gasto ordinario.
        """

        return self.abono_id is not None

    @property
    def categoria_mostrada(self) -> str:
        if self.es_abono:
            return "Abono a deuda"

        return self.categoria_nombre or "Sin categoría"

    @property
    def descripcion_mostrada(self) -> str:
        return self.descripcion or "Sin descripción"
