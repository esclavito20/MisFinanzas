"""Acceso a la base de datos SQLite.

Toda la aplicación obtiene sus conexiones a través de los gestores de contexto
de este módulo, lo que garantiza cierre determinista, activación de claves
foráneas y límites de transacción explícitos.

Se mantiene el modo de diario por defecto (``delete``) en lugar de WAL para que
los respaldos por copia de archivo (incluido ``RESPALDAR_DATOS.bat``) sigan
siendo instantáneas coherentes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import config


def _configurar(conexion: sqlite3.Connection) -> None:
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute("PRAGMA busy_timeout = 5000")


@contextmanager
def conexion() -> Iterator[sqlite3.Connection]:
    """Entrega una conexión configurada en modo autocommit.

    ``isolation_level=None`` desactiva las transacciones implícitas de
    ``sqlite3``; el control transaccional queda exclusivamente en
    :func:`transaccion` y en las migraciones de esquema.
    """

    config.asegurar_directorios()
    con = sqlite3.connect(
        config.RUTA_BASE_DATOS,
        timeout=15,
        isolation_level=None,
    )

    try:
        _configurar(con)
        yield con
    finally:
        con.close()


@contextmanager
def transaccion() -> Iterator[sqlite3.Connection]:
    """Ejecuta un bloque dentro de una transacción atómica.

    Confirma al salir del bloque y revierte ante cualquier excepción, de modo
    que operaciones compuestas (registrar un abono y su gasto asociado, eliminar
    una deuda y sus movimientos) nunca queden a medias.
    """

    with conexion() as con:
        con.execute("BEGIN IMMEDIATE")

        try:
            yield con
        except BaseException:
            con.execute("ROLLBACK")
            raise

        con.execute("COMMIT")
