"""Lógica de negocio de inversiones y rendimiento devengado.

El capital invertido **no** se registra como gasto: es un traslado de activo
(efectivo hacia inversión). Por eso resta del dinero disponible sin alterar los
gastos del mes, y el rendimiento se materializa como ingreso únicamente al
cerrar la inversión, cuando efectivamente se acredita.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from database.conexion import conexion, transaccion
from database.semilla import CATEGORIA_RENDIMIENTOS
from models.inversion import (
    RETENCION_POR_DEFECTO,
    TIPO_CDT,
    TIPOS_VALIDOS,
    Inversion,
)
from models.movimiento import TIPO_INGRESO, Movimiento
from repositories import inversiones_repo, movimientos_repo
from services import categorias_service
from utils.dinero import redondear

logger = logging.getLogger(__name__)


def _validar_datos(
    tipo: str,
    capital: float,
    tasa_ea: float,
    plazo_dias: int | None,
    retencion_porcentaje: float,
) -> tuple[float, float, int | None, float]:
    """Valida las invariantes de una inversión y normaliza sus importes."""

    if tipo not in TIPOS_VALIDOS:
        raise ValueError(
            f"Tipo de inversión no válido: {tipo!r}. "
            f"Use {' o '.join(TIPOS_VALIDOS)}."
        )

    importe = redondear(capital)

    if importe <= 0:
        raise ValueError("El monto de la inversión debe ser mayor que cero.")

    if tasa_ea < 0:
        raise ValueError("La rentabilidad no puede ser negativa.")

    if not 0 <= retencion_porcentaje < 100:
        raise ValueError(
            "La retención debe estar entre 0 y 100 por ciento."
        )

    if tipo == TIPO_CDT:
        # Un CDT sin plazo no tiene vencimiento y, por tanto, no es un CDT.
        if plazo_dias is None or int(plazo_dias) <= 0:
            raise ValueError("Un CDT requiere un plazo mayor que cero.")

        plazo_dias = int(plazo_dias)
    else:
        # Las cajitas de ahorro son abiertas: no tienen vencimiento pactado.
        plazo_dias = None

    return importe, float(tasa_ea), plazo_dias, float(retencion_porcentaje)


def crear_inversion(
    tipo: str,
    capital: float,
    tasa_ea: float,
    fecha_inicio: date | None = None,
    entidad: str = "",
    plazo_dias: int | None = None,
    retencion_porcentaje: float = RETENCION_POR_DEFECTO,
    descripcion: str = "",
) -> int:
    """Registra una inversión. Devuelve su identificador."""

    importe, tasa, plazo, retencion = _validar_datos(
        tipo,
        capital,
        tasa_ea,
        plazo_dias,
        retencion_porcentaje,
    )

    inicio = fecha_inicio or date.today()
    vencimiento = inicio + timedelta(days=plazo) if plazo else None

    with transaccion() as con:
        inversion_id = inversiones_repo.insertar(
            con,
            Inversion(
                id=0,
                tipo=tipo,
                capital=importe,
                tasa_ea=tasa,
                fecha_inicio=inicio,
                entidad=(entidad or "").strip(),
                plazo_dias=plazo,
                fecha_vencimiento=vencimiento,
                retencion_porcentaje=retencion,
                descripcion=(descripcion or "").strip(),
            ),
        )

    logger.info(
        "Inversión creada id=%s tipo=%s capital=%s tasa=%s",
        inversion_id,
        tipo,
        importe,
        tasa,
    )

    return inversion_id


def obtener_inversiones(solo_activas: bool = False) -> list[Inversion]:
    """Lista las inversiones registradas."""

    with conexion() as con:
        return inversiones_repo.listar(con, solo_activas)


def obtener_inversion(inversion_id: int) -> Inversion | None:
    """Recupera una inversión específica."""

    with conexion() as con:
        return inversiones_repo.obtener(con, inversion_id)


def capital_invertido() -> float:
    """Capital vigente que resta del dinero disponible."""

    with conexion() as con:
        return inversiones_repo.total_capital_activo(con)


def rendimiento_acumulado(fecha: date | None = None) -> float:
    """Rendimiento neto devengado por las inversiones vigentes."""

    referencia = fecha or date.today()

    return redondear(
        sum(
            inversion.rendimiento_neto(referencia)
            for inversion in obtener_inversiones(solo_activas=True)
        )
    )


def finalizar_inversion(
    inversion_id: int,
    fecha: date | None = None,
) -> float:
    """Cierra una inversión y acredita su rendimiento.

    El capital vuelve al efectivo disponible por el simple hecho de dejar de
    computar como invertido; el rendimiento neto devengado se registra como
    ingreso porque es dinero que sí ingresa. Devuelve el rendimiento acreditado.
    """

    fecha_cierre = fecha or date.today()

    with transaccion() as con:
        inversion = inversiones_repo.obtener(con, inversion_id)

        if inversion is None:
            raise ValueError("La inversión no existe.")

        if not inversion.activa:
            raise ValueError("Esta inversión ya fue cerrada.")

        rendimiento = inversion.rendimiento_neto(fecha_cierre)

        if rendimiento > 0:
            detalle = f" ({inversion.entidad})" if inversion.entidad else ""

            movimientos_repo.insertar(
                con,
                Movimiento(
                    fecha=fecha_cierre,
                    tipo=TIPO_INGRESO,
                    valor=rendimiento,
                    categoria_id=categorias_service.obtener_o_crear_id(
                        con,
                        CATEGORIA_RENDIMIENTOS,
                        TIPO_INGRESO,
                    ),
                    descripcion=(
                        f"Rendimiento {inversion.etiqueta_tipo}{detalle}"
                    ),
                ),
            )

        inversiones_repo.marcar_finalizada(con, inversion_id)

    logger.info(
        "Inversión cerrada id=%s rendimiento=%s", inversion_id, rendimiento
    )

    return rendimiento


def eliminar_inversion(inversion_id: int) -> bool:
    """Elimina una inversión del registro."""

    with transaccion() as con:
        eliminada = inversiones_repo.eliminar(con, inversion_id)

    if eliminada:
        logger.info("Inversión eliminada id=%s", inversion_id)

    return eliminada
