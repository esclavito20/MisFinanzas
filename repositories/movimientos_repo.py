"""Consultas sobre la tabla ``movimientos``."""

from __future__ import annotations

import sqlite3
from datetime import date

from models.movimiento import Movimiento
from utils.dinero import redondear
from utils.fechas import a_iso, desde_iso

# Proyección compartida: resuelve el nombre de la categoría mediante JOIN y
# desacopla a los consumidores del orden físico de las columnas.
_COLUMNAS = """
    m.id             AS id,
    m.fecha          AS fecha,
    m.tipo           AS tipo,
    m.categoria_id   AS categoria_id,
    COALESCE(c.nombre, '') AS categoria_nombre,
    COALESCE(m.descripcion, '') AS descripcion,
    m.valor          AS valor,
    m.abono_id       AS abono_id,
    m.suscripcion_id AS suscripcion_id
"""


def _a_movimiento(fila: sqlite3.Row) -> Movimiento:
    return Movimiento(
        fecha=desde_iso(fila["fecha"]) or date.today(),
        tipo=fila["tipo"],
        valor=redondear(fila["valor"]),
        categoria_id=fila["categoria_id"],
        descripcion=fila["descripcion"] or "",
        abono_id=fila["abono_id"],
        suscripcion_id=fila["suscripcion_id"],
        id=fila["id"],
        categoria_nombre=fila["categoria_nombre"] or "",
    )


def listar(con: sqlite3.Connection) -> list[Movimiento]:
    """Lista todos los movimientos, del más reciente al más antiguo."""

    filas = con.execute(
        f"""
        SELECT {_COLUMNAS}
        FROM movimientos m
        LEFT JOIN categorias c
            ON c.id = m.categoria_id
        ORDER BY m.fecha DESC, m.id DESC
        """
    )

    return [_a_movimiento(fila) for fila in filas]


def listar_recientes(
    con: sqlite3.Connection,
    limite: int = 5,
) -> list[Movimiento]:
    """Lista los últimos movimientos registrados."""

    filas = con.execute(
        f"""
        SELECT {_COLUMNAS}
        FROM movimientos m
        LEFT JOIN categorias c
            ON c.id = m.categoria_id
        ORDER BY m.fecha DESC, m.id DESC
        LIMIT ?
        """,
        (max(int(limite), 1),),
    )

    return [_a_movimiento(fila) for fila in filas]


def obtener(
    con: sqlite3.Connection,
    movimiento_id: int,
) -> Movimiento | None:
    """Recupera un movimiento por su identificador."""

    fila = con.execute(
        f"""
        SELECT {_COLUMNAS}
        FROM movimientos m
        LEFT JOIN categorias c
            ON c.id = m.categoria_id
        WHERE m.id = ?
        """,
        (movimiento_id,),
    ).fetchone()

    return _a_movimiento(fila) if fila else None


def insertar(con: sqlite3.Connection, movimiento: Movimiento) -> int:
    """Inserta un movimiento y devuelve su identificador."""

    cursor = con.execute(
        """
        INSERT INTO movimientos (
            fecha,
            tipo,
            categoria_id,
            descripcion,
            valor,
            abono_id,
            suscripcion_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            a_iso(movimiento.fecha),
            movimiento.tipo,
            movimiento.categoria_id,
            movimiento.descripcion,
            redondear(movimiento.valor),
            movimiento.abono_id,
            movimiento.suscripcion_id,
        ),
    )

    return int(cursor.lastrowid or 0)


def existe_pago_de_suscripcion(
    con: sqlite3.Connection,
    suscripcion_id: int,
    fecha: date,
) -> bool:
    """Indica si un ciclo de una suscripción ya se registró como gasto.

    Evita duplicar el cobro cuando el usuario pulsa dos veces el registro del
    mismo periodo.
    """

    fila = con.execute(
        """
        SELECT 1
        FROM movimientos
        WHERE suscripcion_id = ?
          AND fecha = ?
        LIMIT 1
        """,
        (suscripcion_id, a_iso(fecha)),
    ).fetchone()

    return fila is not None


def pagos_por_suscripcion(
    con: sqlite3.Connection,
) -> dict[int, set[date]]:
    """Fechas de ciclo ya materializadas como gasto, por suscripción.

    Permite que la proyección de compromisos descuente los cobros ya
    registrados en lugar de seguir contándolos como pendientes.
    """

    pagos: dict[int, set[date]] = {}

    for fila in con.execute(
        """
        SELECT suscripcion_id, fecha
        FROM movimientos
        WHERE suscripcion_id IS NOT NULL
        """
    ):
        fecha = desde_iso(fila["fecha"])

        if fecha is None:
            continue

        pagos.setdefault(int(fila["suscripcion_id"]), set()).add(fecha)

    return pagos


def eliminar(con: sqlite3.Connection, movimiento_id: int) -> bool:
    """Elimina un movimiento. Devuelve ``True`` si existía."""

    cursor = con.execute(
        "DELETE FROM movimientos WHERE id = ?",
        (movimiento_id,),
    )
    return cursor.rowcount > 0


def total(con: sqlite3.Connection, tipo: str | None = None) -> float:
    """Suma los importes de todos los movimientos, opcionalmente por tipo."""

    if tipo:
        fila = con.execute(
            """
            SELECT COALESCE(SUM(valor), 0)
            FROM movimientos
            WHERE tipo = ?
            """,
            (tipo,),
        ).fetchone()
    else:
        fila = con.execute(
            "SELECT COALESCE(SUM(valor), 0) FROM movimientos"
        ).fetchone()

    return redondear(fila[0])


def neto(con: sqlite3.Connection, inicio: str, fin: str) -> float:
    """Resultado de caja del rango [inicio, fin) en una única consulta.

    Los abonos cuentan como salida —el dinero salió de la cuenta—, pero solo los
    del rango: el resultado de un mes no debe arrastrar pagos de meses
    anteriores, que ya pertenecen a su propio periodo.
    """

    fila = con.execute(
        """
        SELECT COALESCE(
            SUM(CASE WHEN tipo = 'ingreso' THEN valor ELSE -valor END),
            0
        )
        FROM movimientos
        WHERE fecha >= ?
          AND fecha < ?
        """,
        (inicio, fin),
    ).fetchone()

    return redondear(fila[0])


def total_mes(
    con: sqlite3.Connection,
    tipo: str,
    inicio: str,
    fin: str,
    solo_consumo: bool = False,
) -> float:
    """Suma los importes de un tipo dentro del rango [inicio, fin).

    ``solo_consumo`` excluye los movimientos originados por un abono: pagar una
    deuda no es consumir, aunque el dinero sí haya salido de la cuenta. El
    efecto sobre el efectivo lo recoge :func:`neto`, que no aplica el filtro.
    """

    filtro = "AND abono_id IS NULL" if solo_consumo else ""

    fila = con.execute(
        f"""
        SELECT COALESCE(SUM(valor), 0)
        FROM movimientos
        WHERE tipo = ?
          AND fecha >= ?
          AND fecha < ?
          {filtro}
        """,
        (tipo, inicio, fin),
    ).fetchone()

    return redondear(fila[0])


def gastos_por_categoria(
    con: sqlite3.Connection,
    inicio: str,
    fin: str,
) -> list[tuple[str, float]]:
    """Agrupa por categoría el consumo del rango, de mayor a menor.

    Queda fuera el gasto que refleja un abono: su importe no es una compra sino
    la devolución de un compromiso ya contraído, y sumarlo aquí inflaría una
    categoría que no describe consumo alguno.
    """

    filas = con.execute(
        """
        SELECT
            COALESCE(c.nombre, 'Sin categoría') AS categoria,
            SUM(m.valor) AS total
        FROM movimientos m
        LEFT JOIN categorias c
            ON c.id = m.categoria_id
        WHERE m.tipo = 'gasto'
          AND m.abono_id IS NULL
          AND m.fecha >= ?
          AND m.fecha < ?
        GROUP BY COALESCE(c.nombre, 'Sin categoría')
        ORDER BY total DESC
        """,
        (inicio, fin),
    )

    return [(fila["categoria"], redondear(fila["total"])) for fila in filas]


def actualizar_por_abono(
    con: sqlite3.Connection,
    abono_id: int,
    fecha: date,
    valor: float,
    descripcion: str,
) -> bool:
    """Traslada al gasto asociado los datos corregidos de un abono.

    Un abono se persiste dos veces —en ``abonos`` y como movimiento—; editar
    solo una de las dos copias dejaría el saldo de la deuda y el flujo de caja
    contando cosas distintas.
    """

    cursor = con.execute(
        """
        UPDATE movimientos
        SET fecha = ?,
            valor = ?,
            descripcion = ?
        WHERE abono_id = ?
        """,
        (a_iso(fecha), redondear(valor), descripcion, abono_id),
    )

    return cursor.rowcount > 0
