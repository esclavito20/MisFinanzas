"""Respaldos de la base de datos.

Se utiliza la API de copia en línea de ``sqlite3`` en lugar de una copia de
archivo: la instantánea es consistente aunque la aplicación tenga conexiones
abiertas o existan transacciones pendientes.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

PREFIJO_RESPALDO = "finanzas"


def _ruta_respaldo(directorio: Path) -> Path:
    marca_tiempo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    return directorio / f"{PREFIJO_RESPALDO}_{marca_tiempo}.db"


def copiar_base_de_datos(origen: Path, destino: Path) -> None:
    """Copia una base de datos SQLite de forma consistente."""

    con_origen = sqlite3.connect(origen)

    try:
        con_destino = sqlite3.connect(destino)

        try:
            con_origen.backup(con_destino)
        finally:
            con_destino.close()
    finally:
        con_origen.close()


def crear_respaldo(directorio: Path | None = None) -> Path | None:
    """Crea un respaldo de la base actual y devuelve su ruta.

    Devuelve ``None`` cuando la base no existe o cuando el respaldo no puede
    completarse: la falta de respaldo nunca debe impedir el uso de la
    aplicación.
    """

    if not config.RUTA_BASE_DATOS.exists():
        return None

    directorio_destino = directorio or config.DIRECTORIO_RESPALDOS

    try:
        directorio_destino.mkdir(parents=True, exist_ok=True)
        destino = _ruta_respaldo(directorio_destino)
        copiar_base_de_datos(config.RUTA_BASE_DATOS, destino)
    except (OSError, sqlite3.Error) as error:
        logger.warning("No fue posible crear el respaldo: %s", error)
        return None

    logger.info("Respaldo creado en %s", destino)
    return destino


def _purgar_respaldos(directorio: Path) -> None:
    """Conserva únicamente los respaldos automáticos más recientes."""

    respaldos = sorted(
        directorio.glob(f"{PREFIJO_RESPALDO}_*.db"),
        key=lambda archivo: archivo.stat().st_mtime,
        reverse=True,
    )

    for respaldo_antiguo in respaldos[config.MAX_RESPALDOS_AUTOMATICOS:]:
        try:
            respaldo_antiguo.unlink()
        except OSError:
            pass


def crear_respaldo_automatico() -> Path | None:
    """Respalda la base antes de inicializar o migrar el esquema.

    Se aplica también en ejecución desde código fuente: las migraciones
    reconstruyen tablas y el usuario debe poder revertir cualquier cambio.
    """

    respaldo = crear_respaldo(config.DIRECTORIO_RESPALDOS)

    if respaldo is not None:
        _purgar_respaldos(config.DIRECTORIO_RESPALDOS)

    return respaldo


def crear_respaldo_manual() -> Path | None:
    """Respaldo solicitado explícitamente por el usuario.

    Se almacena en un directorio independiente para que la política de
    retención de los respaldos automáticos no lo elimine.
    """

    return crear_respaldo(config.DIRECTORIO_RESPALDOS_MANUALES)
