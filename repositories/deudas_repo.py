"""Consultas sobre las tablas ``deudas`` y ``abonos``."""

from __future__ import annotations

import sqlite3
from datetime import date

from models.abono import Abono
from models.deuda import Deuda
from utils.dinero import redondear
from utils.fechas import a_iso, desde_iso

_COLUMNAS_DEUDA = """
    d.id                            AS id,
    d.nombre                        AS nombre,
    d.monto_inicial                 AS monto_inicial,
    d.fecha_creacion                AS fecha_creacion,
    COALESCE(d.descripcion, '')     AS descripcion,
    d.pago_minimo                   AS pago_minimo,
    d.fecha_proximo_pago            AS fecha_proximo_pago,
    COALESCE(SUM(a.valor), 0)       AS total_abonado
"""

_AGRUPACION = """
    d.id,
    d.nombre,
    d.monto_inicial,
    d.fecha_creacion,
    d.descripcion,
    d.pago_minimo,
    d.fecha_proximo_pago
"""


def _a_deuda(fila: sqlite3.Row) -> Deuda:
    minimo = fila["pago_minimo"]

    return Deuda(
        id=fila["id"],
        nombre=fila["nombre"],
        monto_inicial=redondear(fila["monto_inicial"]),
        fecha_creacion=desde_iso(fila["fecha_creacion"]),
        descripcion=fila["descripcion"] or "",
        total_abonado=redondear(fila["total_abonado"]),
        pago_minimo=redondear(minimo) if minimo is not None else None,
        fecha_proximo_pago=desde_iso(fila["fecha_proximo_pago"]),
    )


def listar(con: sqlite3.Connection) -> list[Deuda]:
    """Lista todas las deudas con el total abonado agregado."""

    filas = con.execute(
        f"""
        SELECT {_COLUMNAS_DEUDA}
        FROM deudas d
        LEFT JOIN abonos a
            ON a.deuda_id = d.id
        GROUP BY {_AGRUPACION}
        ORDER BY d.fecha_creacion DESC, d.id DESC
        """
    )

    return [_a_deuda(fila) for fila in filas]


def obtener(con: sqlite3.Connection, deuda_id: int) -> Deuda | None:
    """Recupera una deuda por su identificador."""

    fila = con.execute(
        f"""
        SELECT {_COLUMNAS_DEUDA}
        FROM deudas d
        LEFT JOIN abonos a
            ON a.deuda_id = d.id
        WHERE d.id = ?
        GROUP BY {_AGRUPACION}
        """,
        (deuda_id,),
    ).fetchone()

    return _a_deuda(fila) if fila else None


def insertar(
    con: sqlite3.Connection,
    nombre: str,
    monto_inicial: float,
    fecha_creacion: date,
    descripcion: str = "",
    pago_minimo: float | None = None,
    fecha_proximo_pago: date | None = None,
) -> int:
    """Inserta una deuda pendiente y devuelve su identificador."""

    cursor = con.execute(
        """
        INSERT INTO deudas (
            nombre,
            monto_inicial,
            fecha_creacion,
            descripcion,
            estado,
            pago_minimo,
            fecha_proximo_pago
        )
        VALUES (?, ?, ?, ?, 'pendiente', ?, ?)
        """,
        (
            nombre,
            redondear(monto_inicial),
            a_iso(fecha_creacion),
            descripcion,
            redondear(pago_minimo) if pago_minimo else None,
            a_iso(fecha_proximo_pago) if fecha_proximo_pago else None,
        ),
    )

    return int(cursor.lastrowid or 0)


def actualizar(
    con: sqlite3.Connection,
    deuda_id: int,
    nombre: str,
    monto_inicial: float,
    fecha_creacion: date,
    descripcion: str = "",
    pago_minimo: float | None = None,
    fecha_proximo_pago: date | None = None,
) -> bool:
    """Reescribe los datos de una deuda. Devuelve ``True`` si existía.

    No toca los abonos: el saldo pendiente sigue derivándose de ellos, de modo
    que corregir el monto inicial no puede alterar el historial de pagos.
    """

    cursor = con.execute(
        """
        UPDATE deudas
        SET nombre = ?,
            monto_inicial = ?,
            fecha_creacion = ?,
            descripcion = ?,
            pago_minimo = ?,
            fecha_proximo_pago = ?
        WHERE id = ?
        """,
        (
            nombre,
            redondear(monto_inicial),
            a_iso(fecha_creacion),
            descripcion,
            redondear(pago_minimo) if pago_minimo else None,
            a_iso(fecha_proximo_pago) if fecha_proximo_pago else None,
            deuda_id,
        ),
    )

    return cursor.rowcount > 0


def actualizar_proximo_pago(
    con: sqlite3.Connection,
    deuda_id: int,
    fecha: date | None,
) -> bool:
    """Fija o retira el recordatorio sin tocar el resto de la deuda.

    Se separa de :func:`actualizar` porque reprogramar el próximo pago es una
    escritura de una sola columna que ocurre al registrar un abono, y reescribir
    con ella el nombre o el monto sería un efecto colateral indeseado.
    """

    cursor = con.execute(
        "UPDATE deudas SET fecha_proximo_pago = ? WHERE id = ?",
        (a_iso(fecha) if fecha else None, deuda_id),
    )

    return cursor.rowcount > 0


def eliminar(con: sqlite3.Connection, deuda_id: int) -> bool:
    """Elimina una deuda. Sus abonos y los gastos asociados se eliminan en
    cascada mediante las claves foráneas del esquema."""

    cursor = con.execute(
        "DELETE FROM deudas WHERE id = ?",
        (deuda_id,),
    )
    return cursor.rowcount > 0


def insertar_abono(con: sqlite3.Connection, abono: Abono) -> int:
    """Registra un abono y devuelve su identificador."""

    cursor = con.execute(
        """
        INSERT INTO abonos (
            deuda_id,
            fecha,
            valor,
            descripcion
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            abono.deuda_id,
            a_iso(abono.fecha),
            redondear(abono.valor),
            abono.descripcion,
        ),
    )

    return int(cursor.lastrowid or 0)


def actualizar_abono(
    con: sqlite3.Connection,
    abono_id: int,
    fecha: date,
    valor: float,
    descripcion: str = "",
) -> bool:
    """Corrige el importe, la fecha o la nota de un abono existente.

    Devuelve ``True`` si el abono existía. La coherencia con el movimiento
    asociado y con el saldo de la deuda la garantiza la capa de servicios, que
    ejecuta las tres escrituras en una sola transacción.
    """

    cursor = con.execute(
        """
        UPDATE abonos
        SET fecha = ?,
            valor = ?,
            descripcion = ?
        WHERE id = ?
        """,
        (a_iso(fecha), redondear(valor), descripcion, abono_id),
    )

    return cursor.rowcount > 0


def obtener_abono(
    con: sqlite3.Connection,
    abono_id: int,
) -> Abono | None:
    """Recupera un abono por su identificador."""

    fila = con.execute(
        """
        SELECT id, deuda_id, fecha, valor, descripcion
        FROM abonos
        WHERE id = ?
        """,
        (abono_id,),
    ).fetchone()

    if fila is None:
        return None

    return Abono(
        id=fila["id"],
        deuda_id=fila["deuda_id"],
        fecha=desde_iso(fila["fecha"]) or date.today(),
        valor=redondear(fila["valor"]),
        descripcion=fila["descripcion"] or "",
    )


def listar_abonos(
    con: sqlite3.Connection,
    deuda_id: int,
) -> list[Abono]:
    """Lista el historial de abonos de una deuda."""

    filas = con.execute(
        """
        SELECT id, deuda_id, fecha, valor, descripcion
        FROM abonos
        WHERE deuda_id = ?
        ORDER BY fecha DESC, id DESC
        """,
        (deuda_id,),
    )

    return [
        Abono(
            id=fila["id"],
            deuda_id=fila["deuda_id"],
            fecha=desde_iso(fila["fecha"]) or date.today(),
            valor=redondear(fila["valor"]),
            descripcion=fila["descripcion"] or "",
        )
        for fila in filas
    ]


def total_abonos_mes(
    con: sqlite3.Connection,
    inicio: str,
    fin: str,
) -> float:
    """Suma los abonos aplicados en el rango [inicio, fin).

    Permite desglosar en el resumen cuánto del dinero que salió de la cuenta este
    periodo se destinó a deudas, sin arrastrar pagos de meses anteriores.
    """

    fila = con.execute(
        """
        SELECT COALESCE(SUM(valor), 0)
        FROM abonos
        WHERE fecha >= ?
          AND fecha < ?
        """,
        (inicio, fin),
    ).fetchone()

    return redondear(fila[0])


def eliminar_abono(
    con: sqlite3.Connection,
    abono_id: int,
) -> int | None:
    """Elimina un abono y devuelve el identificador de su deuda.

    El movimiento de gasto asociado se elimina en cascada desde ``abonos``.
    Devuelve ``None`` cuando el abono no existe.
    """

    fila = con.execute(
        "SELECT deuda_id FROM abonos WHERE id = ?",
        (abono_id,),
    ).fetchone()

    if fila is None:
        return None

    con.execute("DELETE FROM abonos WHERE id = ?", (abono_id,))

    return int(fila["deuda_id"])


def sincronizar_estado(con: sqlite3.Connection, deuda_id: int) -> None:
    """Recalcula el estado persistido de una deuda a partir de sus abonos.

    ``estado`` es una columna de compatibilidad; la fuente de verdad del saldo
    es siempre la suma de abonos. Esta función la mantiene coherente para
    cualquier consumidor externo de la base de datos.
    """

    con.execute(
        """
        UPDATE deudas
        SET estado = CASE
            WHEN COALESCE(
                (SELECT SUM(valor) FROM abonos WHERE deuda_id = deudas.id),
                0
            ) >= monto_inicial
            THEN 'pagada'
            ELSE 'pendiente'
        END
        WHERE id = ?
        """,
        (deuda_id,),
    )
