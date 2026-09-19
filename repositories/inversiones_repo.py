"""Consultas sobre la tabla ``inversiones``."""

from __future__ import annotations

import sqlite3
from datetime import date

from models.inversion import ESTADO_ACTIVA, ESTADO_FINALIZADA, Inversion
from utils.dinero import redondear
from utils.fechas import a_iso, desde_iso

_COLUMNAS = """
    id,
    tipo,
    COALESCE(entidad, '') AS entidad,
    capital,
    tasa_ea,
    plazo_dias,
    fecha_inicio,
    fecha_vencimiento,
    retencion_porcentaje,
    estado,
    COALESCE(descripcion, '') AS descripcion
"""


def _a_inversion(fila: sqlite3.Row) -> Inversion:
    return Inversion(
        id=fila["id"],
        tipo=fila["tipo"],
        capital=redondear(fila["capital"]),
        tasa_ea=float(fila["tasa_ea"]),
        fecha_inicio=desde_iso(fila["fecha_inicio"]) or date.today(),
        entidad=fila["entidad"] or "",
        plazo_dias=fila["plazo_dias"],
        fecha_vencimiento=desde_iso(fila["fecha_vencimiento"]),
        retencion_porcentaje=float(fila["retencion_porcentaje"]),
        estado=fila["estado"],
        descripcion=fila["descripcion"] or "",
    )


def listar(
    con: sqlite3.Connection,
    solo_activas: bool = False,
) -> list[Inversion]:
    """Lista las inversiones, opcionalmente restringidas a las vigentes."""

    sql = f"SELECT {_COLUMNAS} FROM inversiones"

    if solo_activas:
        sql += " WHERE estado = ?"

    sql += " ORDER BY fecha_inicio DESC, id DESC"

    parametros = (ESTADO_ACTIVA,) if solo_activas else ()

    return [_a_inversion(fila) for fila in con.execute(sql, parametros)]


def obtener(
    con: sqlite3.Connection,
    inversion_id: int,
) -> Inversion | None:
    """Recupera una inversión por su identificador."""

    fila = con.execute(
        f"SELECT {_COLUMNAS} FROM inversiones WHERE id = ?",
        (inversion_id,),
    ).fetchone()

    return _a_inversion(fila) if fila else None


def insertar(con: sqlite3.Connection, inversion: Inversion) -> int:
    """Inserta una inversión activa y devuelve su identificador."""

    cursor = con.execute(
        """
        INSERT INTO inversiones (
            tipo,
            entidad,
            capital,
            tasa_ea,
            plazo_dias,
            fecha_inicio,
            fecha_vencimiento,
            retencion_porcentaje,
            estado,
            descripcion
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            inversion.tipo,
            inversion.entidad,
            redondear(inversion.capital),
            float(inversion.tasa_ea),
            inversion.plazo_dias,
            a_iso(inversion.fecha_inicio),
            (
                a_iso(inversion.fecha_vencimiento)
                if inversion.fecha_vencimiento
                else None
            ),
            float(inversion.retencion_porcentaje),
            inversion.estado,
            inversion.descripcion,
        ),
    )

    return int(cursor.lastrowid or 0)


def total_capital_activo(con: sqlite3.Connection) -> float:
    """Capital vigente, agregado en una única consulta."""

    fila = con.execute(
        """
        SELECT COALESCE(SUM(capital), 0)
        FROM inversiones
        WHERE estado = ?
        """,
        (ESTADO_ACTIVA,),
    ).fetchone()

    return redondear(fila[0])


def marcar_finalizada(
    con: sqlite3.Connection,
    inversion_id: int,
) -> bool:
    """Cierra una inversión.

    Su capital deja de computar como invertido y vuelve al efectivo disponible.
    """

    cursor = con.execute(
        "UPDATE inversiones SET estado = ? WHERE id = ?",
        (ESTADO_FINALIZADA, inversion_id),
    )

    return cursor.rowcount > 0


def eliminar(con: sqlite3.Connection, inversion_id: int) -> bool:
    """Elimina una inversión del registro."""

    cursor = con.execute(
        "DELETE FROM inversiones WHERE id = ?",
        (inversion_id,),
    )
    return cursor.rowcount > 0
