"""Consultas sobre la tabla ``categorias``."""

from __future__ import annotations

import sqlite3

from models.categoria import Categoria


def listar(
    con: sqlite3.Connection,
    tipo: str | None = None,
) -> list[Categoria]:
    """Lista las categorías activas, opcionalmente filtradas por tipo."""

    sql = "SELECT id, nombre, tipo FROM categorias WHERE activa = 1"
    parametros: list[object] = []

    if tipo:
        sql += " AND tipo = ?"
        parametros.append(tipo)

    sql += " ORDER BY nombre COLLATE NOCASE"

    return [
        Categoria(fila["id"], fila["nombre"], fila["tipo"])
        for fila in con.execute(sql, parametros)
    ]


def contar(con: sqlite3.Connection) -> int:
    """Devuelve la cantidad de categorías registradas."""

    return int(con.execute("SELECT COUNT(*) FROM categorias").fetchone()[0])


def insertar(con: sqlite3.Connection, nombre: str, tipo: str) -> int:
    """Inserta una categoría y devuelve su identificador."""

    cursor = con.execute(
        """
        INSERT INTO categorias (nombre, tipo)
        VALUES (?, ?)
        """,
        (nombre, tipo),
    )
    return int(cursor.lastrowid or 0)


def obtener_id_por_nombre(
    con: sqlite3.Connection,
    nombre: str,
    tipo: str | None = None,
) -> int | None:
    """Resuelve el identificador de una categoría activa por su nombre."""

    sql = "SELECT id FROM categorias WHERE nombre = ? AND activa = 1"
    parametros: list[object] = [nombre]

    if tipo:
        sql += " AND tipo = ?"
        parametros.append(tipo)

    sql += " ORDER BY id LIMIT 1"
    fila = con.execute(sql, parametros).fetchone()

    return int(fila["id"]) if fila else None
