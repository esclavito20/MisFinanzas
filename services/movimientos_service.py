"""Lógica de negocio de movimientos, saldo y análisis mensual."""

from __future__ import annotations

import logging
from datetime import date

from database.conexion import conexion, transaccion
from models.movimiento import (
    TIPO_GASTO,
    TIPO_INGRESO,
    TIPOS_VALIDOS,
    Movimiento,
)
from repositories import deudas_repo, movimientos_repo
from utils.dinero import redondear
from utils.fechas import rango_mes

logger = logging.getLogger(__name__)


def _validar(movimiento: Movimiento) -> float:
    """Valida las invariantes de un movimiento y normaliza su importe."""

    if movimiento.tipo not in TIPOS_VALIDOS:
        raise ValueError(
            f"Tipo de movimiento no válido: {movimiento.tipo!r}."
        )

    importe = redondear(movimiento.valor)

    if importe <= 0:
        raise ValueError(
            "El valor del movimiento debe ser mayor que cero."
        )

    return importe


def guardar_movimiento(movimiento: Movimiento) -> Movimiento:
    """Valida y persiste un movimiento. Devuelve el movimiento con su id."""

    movimiento.valor = _validar(movimiento)

    with transaccion() as con:
        movimiento.id = movimientos_repo.insertar(con, movimiento)

    logger.info(
        "Movimiento registrado id=%s tipo=%s valor=%s",
        movimiento.id,
        movimiento.tipo,
        movimiento.valor,
    )

    return movimiento


def obtener_movimientos() -> list[Movimiento]:
    """Lista todos los movimientos registrados."""

    with conexion() as con:
        return movimientos_repo.listar(con)


def obtener_movimientos_recientes(limite: int = 5) -> list[Movimiento]:
    """Lista los últimos movimientos registrados."""

    with conexion() as con:
        return movimientos_repo.listar_recientes(con, limite)


def obtener_ingresos_mes(
    fecha_referencia: date | None = None,
) -> float:
    """Calcula los ingresos del mes de referencia."""

    inicio, fin = rango_mes(fecha_referencia)

    with conexion() as con:
        return movimientos_repo.total_mes(con, TIPO_INGRESO, inicio, fin)


def obtener_gastos_mes(
    fecha_referencia: date | None = None,
) -> float:
    """Calcula el consumo del mes de referencia.

    Excluye los movimientos que reflejan un abono a una deuda: devolver un
    compromiso ya contraído no es un gasto nuevo. La salida de dinero que sí
    producen se refleja en el efectivo, no en la tarjeta de gastos.
    """

    inicio, fin = rango_mes(fecha_referencia)

    with conexion() as con:
        return movimientos_repo.total_mes(
            con,
            TIPO_GASTO,
            inicio,
            fin,
            solo_consumo=True,
        )


def obtener_gastos_por_categoria_mes(
    fecha_referencia: date | None = None,
) -> list[tuple[str, float]]:
    """Agrupa los gastos del mes de referencia por categoría."""

    inicio, fin = rango_mes(fecha_referencia)

    with conexion() as con:
        return movimientos_repo.gastos_por_categoria(con, inicio, fin)


def calcular_saldo_mes(fecha_referencia: date | None = None) -> float:
    """Calcula el resultado de caja del mes de referencia.

    Es el dinero que quedó disponible ese mes: los ingresos menos los gastos,
    contando los abonos como salida porque el dinero salió de la cuenta. Solo
    entran los movimientos del mes, de modo que registrar un pago de marzo no
    altera el disponible de septiembre.
    """

    inicio, fin = rango_mes(fecha_referencia)

    with conexion() as con:
        return movimientos_repo.neto(con, inicio, fin)


def eliminar_movimiento(movimiento_id: int) -> bool:
    """Elimina un movimiento y mantiene coherente la deuda de origen.

    Cuando el gasto proviene de un abono se elimina el abono, de modo que el
    saldo de la deuda recupere su valor previo; la clave foránea en cascada del
    esquema retira el movimiento asociado.
    """

    with transaccion() as con:
        movimiento = movimientos_repo.obtener(con, movimiento_id)

        if movimiento is None:
            return False

        if movimiento.abono_id is None:
            return movimientos_repo.eliminar(con, movimiento_id)

        deuda_id = deudas_repo.eliminar_abono(con, movimiento.abono_id)

        if deuda_id is not None:
            deudas_repo.sincronizar_estado(con, deuda_id)

        # La cascada del esquema ya retiró el movimiento; se refuerza el
        # borrado para bases creadas antes de la migración de claves foráneas.
        movimientos_repo.eliminar(con, movimiento_id)

        logger.info(
            "Abono %s revertido al eliminar el movimiento %s",
            movimiento.abono_id,
            movimiento_id,
        )

        return True
