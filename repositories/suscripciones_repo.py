"""Consultas sobre la tabla ``suscripciones``."""

from __future__ import annotations

import sqlite3
from datetime import date

from models.suscripcion import ESTADO_ACTIVA, Suscripcion
from utils.dinero import redondear
from utils.fechas import a_iso, desde_iso

_COLUMNAS = """
    id,
    nombre,
    costo,
    periodicidad,
    dia_facturacion,
    mes_facturacion,
    fecha_inicio,
    fecha_fin,
    estado,
    COALESCE(descripcion, '') AS descripcion
"""


def _a_suscripcion(fila: sqlite3.Row) -> Suscripcion:
    return Suscripcion(
        id=fila["id"],
        nombre=fila["nombre"],
        costo=redondear(fila["costo"]),
        periodicidad=fila["periodicidad"],
        dia_facturacion=fila["dia_facturacion"],
        fecha_inicio=desde_iso(fila["fecha_inicio"]) or date.today(),
        mes_facturacion=fila["mes_facturacion"],
        fecha_fin=desde_iso(fila["fecha_fin"]),
        estado=fila["estado"],
        descripcion=fila["descripcion"] or "",
    )


def listar(
    con: sqlite3.Connection,
    solo_activas: bool = False,
) -> list[Suscripcion]:
    """Lista las suscripciones, opcionalmente restringidas a las vigentes."""

    sql = f"SELECT {_COLUMNAS} FROM suscripciones"

    if solo_activas:
        sql += " WHERE estado = ?"

    sql += " ORDER BY nombre COLLATE NOCASE"

    parametros = (ESTADO_ACTIVA,) if solo_activas else ()

    return [_a_suscripcion(fila) for fila in con.execute(sql, parametros)]


def obtener(
    con: sqlite3.Connection,
    suscripcion_id: int,
) -> Suscripcion | None:
    """Recupera una suscripción por su identificador."""

    fila = con.execute(
        f"SELECT {_COLUMNAS} FROM suscripciones WHERE id = ?",
        (suscripcion_id,),
    ).fetchone()

    return _a_suscripcion(fila) if fila else None


def insertar(con: sqlite3.Connection, suscripcion: Suscripcion) -> int:
    """Inserta una suscripción activa y devuelve su identificador."""

    cursor = con.execute(
        """
        INSERT INTO suscripciones (
            nombre,
            costo,
            periodicidad,
            dia_facturacion,
            mes_facturacion,
            fecha_inicio,
            fecha_fin,
            estado,
            descripcion
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            suscripcion.nombre,
            redondear(suscripcion.costo),
            suscripcion.periodicidad,
            suscripcion.dia_facturacion,
            suscripcion.mes_facturacion,
            a_iso(suscripcion.fecha_inicio),
            a_iso(suscripcion.fecha_fin) if suscripcion.fecha_fin else None,
            suscripcion.estado,
            suscripcion.descripcion,
        ),
    )

    return int(cursor.lastrowid or 0)


def actualizar_ciclo(
    con: sqlite3.Connection,
    suscripcion_id: int,
    estado: str,
    fecha_fin: date | None,
) -> bool:
    """Activa o detiene el ciclo de facturación de una suscripción.

    ``fecha_inicio`` nunca se modifica: conserva el aniversario original del
    cobro, de modo que al reactivar el ciclo la proyección retoma la fecha
    habitual sin generar cobros retroactivos (los ya transcurridos quedan
    excluidos por la regla de "cobros pendientes").
    """

    cursor = con.execute(
        """
        UPDATE suscripciones
        SET estado = ?, fecha_fin = ?
        WHERE id = ?
        """,
        (estado, a_iso(fecha_fin) if fecha_fin else None, suscripcion_id),
    )

    return cursor.rowcount > 0


def eliminar(con: sqlite3.Connection, suscripcion_id: int) -> bool:
    """Elimina una suscripción.

    Los gastos ya registrados por sus ciclos se conservan: la clave foránea
    ``ON DELETE SET NULL`` desvincula el histórico en lugar de borrarlo.
    """

    cursor = con.execute(
        "DELETE FROM suscripciones WHERE id = ?",
        (suscripcion_id,),
    )
    return cursor.rowcount > 0
