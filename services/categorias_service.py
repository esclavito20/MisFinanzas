"""Lógica de negocio de categorías."""

from __future__ import annotations

import sqlite3

from database.conexion import conexion
from models.categoria import Categoria
from repositories import categorias_repo


def obtener_categorias(tipo: str | None = None) -> list[Categoria]:
    """Lista las categorías activas, opcionalmente filtradas por tipo."""

    with conexion() as con:
        return categorias_repo.listar(con, tipo)


def obtener_o_crear_id(
    con: sqlite3.Connection,
    nombre: str,
    tipo: str,
) -> int | None:
    """Resuelve una categoría por nombre y tipo, creándola si no existe.

    La usan los servicios que registran movimientos automáticos —cobros de
    suscripción, rendimientos de inversión y abonos de deuda— para que ninguno
    quede sin categoría si el usuario la eliminó o desactivó desde la interfaz.

    Recibe una conexión abierta en lugar de abrir la suya porque siempre se
    invoca dentro de la transacción que escribe el movimiento: resolver la
    categoría en otra conexión podría crearla y no llegar a usarla.
    """

    categoria_id = categorias_repo.obtener_id_por_nombre(con, nombre, tipo)

    if categoria_id is None:
        categoria_id = categorias_repo.insertar(con, nombre, tipo)

    return categoria_id
