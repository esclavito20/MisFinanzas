"""Categorías iniciales de la aplicación.

La lista es idempotente: solo se inserta cuando la tabla está vacía. Incluye
las categorías que la lógica de negocio resuelve por nombre (abonos de deudas,
cobro de suscripciones y rendimientos financieros), de modo que ningún literal
quede duplicado en los servicios.
"""

from __future__ import annotations

import logging

from database.conexion import transaccion
from models.movimiento import TIPO_GASTO, TIPO_INGRESO
from repositories import categorias_repo

logger = logging.getLogger(__name__)

CATEGORIA_DEUDAS = "Deudas"
CATEGORIA_SUSCRIPCIONES = "Suscripciones"
CATEGORIA_RENDIMIENTOS = "Rendimientos"

CATEGORIAS_INICIALES: tuple[tuple[str, str], ...] = (
    ("Sueldo", TIPO_INGRESO),
    ("Otros ingresos", TIPO_INGRESO),
    (CATEGORIA_RENDIMIENTOS, TIPO_INGRESO),
    ("Alimentación", TIPO_GASTO),
    ("Transporte", TIPO_GASTO),
    ("Vivienda", TIPO_GASTO),
    ("Servicios", TIPO_GASTO),
    ("Entretenimiento", TIPO_GASTO),
    ("Compras", TIPO_GASTO),
    ("Salud", TIPO_GASTO),
    ("Educación", TIPO_GASTO),
    (CATEGORIA_SUSCRIPCIONES, TIPO_GASTO),
    (CATEGORIA_DEUDAS, TIPO_GASTO),
    ("Otros", TIPO_GASTO),
)


def crear_categorias_iniciales() -> int:
    """Inserta las categorías base si la tabla está vacía.

    Devuelve el número de categorías creadas.
    """

    with transaccion() as con:
        if categorias_repo.contar(con) > 0:
            return 0

        for nombre, tipo in CATEGORIAS_INICIALES:
            categorias_repo.insertar(con, nombre, tipo)

    logger.info("Categorías iniciales creadas: %s", len(CATEGORIAS_INICIALES))
    return len(CATEGORIAS_INICIALES)
