"""Lógica de negocio de deudas, abonos y recordatorios de pago.

Un abono se persiste dos veces: como registro del historial de la deuda
(``abonos``) y como movimiento de caja (``movimientos``) que lo refleja. Toda
operación que toque uno de los dos —registrar, corregir, eliminar— escribe
ambos y recalcula el estado de la deuda dentro de una única transacción; de lo
contrario el saldo pendiente y el flujo de caja contarían cosas distintas.
"""

from __future__ import annotations

import logging
from datetime import date

from database.conexion import conexion, transaccion
from database.semilla import CATEGORIA_DEUDAS
from models.abono import Abono
from models.deuda import (
    DESPLAZAMIENTOS,
    Deuda,
    siguiente_vencimiento,
)
from models.movimiento import TIPO_GASTO, Movimiento
from repositories import deudas_repo, movimientos_repo
from services import categorias_service
from utils.dinero import formatear_dinero, redondear
from utils.fechas import rango_mes

logger = logging.getLogger(__name__)

# Reprogramación del recordatorio al registrar un abono. Los periodos válidos
# son los que declara el modelo; estos dos no desplazan ninguna fecha.
SIN_CAMBIO = "sin_cambio"
QUITAR_RECORDATORIO = "quitar"


def _validar_datos(
    nombre: str,
    monto_inicial: float,
    pago_minimo: float | None,
    ya_abonado: float = 0.0,
) -> tuple[str, float, float | None]:
    """Valida los datos comunes del alta y la edición de una deuda.

    Devuelve los valores normalizados, con el pago mínimo reducido a ``None``
    cuando no se define: cero y «sin mínimo» son el mismo caso.
    """

    nombre = (nombre or "").strip()
    importe = redondear(monto_inicial)
    minimo = redondear(pago_minimo) if pago_minimo else None

    if not nombre:
        raise ValueError("El nombre de la deuda es obligatorio.")

    if importe <= 0:
        raise ValueError("El monto inicial debe ser mayor que cero.")

    if importe < redondear(ya_abonado):
        raise ValueError(
            "El monto inicial no puede ser menor que lo ya abonado "
            f"({formatear_dinero(ya_abonado)})."
        )

    if minimo is not None and minimo <= 0:
        raise ValueError("El pago mínimo debe ser mayor que cero.")

    return nombre, importe, minimo


def crear_deuda(
    nombre: str,
    monto_inicial: float,
    fecha_creacion: date | None = None,
    descripcion: str = "",
    pago_minimo: float | None = None,
    fecha_proximo_pago: date | None = None,
) -> int:
    """Registra una deuda. Devuelve su identificador."""

    nombre, importe, minimo = _validar_datos(nombre, monto_inicial, pago_minimo)

    with transaccion() as con:
        deuda_id = deudas_repo.insertar(
            con,
            nombre=nombre,
            monto_inicial=importe,
            fecha_creacion=fecha_creacion or date.today(),
            descripcion=(descripcion or "").strip(),
            pago_minimo=minimo,
            fecha_proximo_pago=fecha_proximo_pago,
        )

    logger.info("Deuda creada id=%s nombre=%s", deuda_id, nombre)
    return deuda_id


def actualizar_deuda(
    deuda_id: int,
    nombre: str,
    monto_inicial: float,
    fecha_creacion: date | None = None,
    descripcion: str = "",
    pago_minimo: float | None = None,
    fecha_proximo_pago: date | None = None,
) -> bool:
    """Corrige los datos de una deuda, incluido su recordatorio de pago."""

    with transaccion() as con:
        deuda = deudas_repo.obtener(con, deuda_id)

        if deuda is None:
            raise ValueError("La deuda no existe.")

        nombre, importe, minimo = _validar_datos(
            nombre,
            monto_inicial,
            pago_minimo,
            deuda.total_abonado,
        )

        actualizada = deudas_repo.actualizar(
            con,
            deuda_id,
            nombre=nombre,
            monto_inicial=importe,
            fecha_creacion=fecha_creacion or deuda.fecha_creacion or date.today(),
            descripcion=(descripcion or "").strip(),
            pago_minimo=minimo,
            fecha_proximo_pago=fecha_proximo_pago,
        )

        if actualizada:
            # El monto inicial puede cambiar y con él la condición de pagada, así
            # que el estado persistido se recalcula en la misma transacción.
            deudas_repo.sincronizar_estado(con, deuda_id)

    if actualizada:
        logger.info("Deuda actualizada id=%s nombre=%s", deuda_id, nombre)

    return actualizada


def obtener_deudas() -> list[Deuda]:
    """Lista todas las deudas con su saldo y progreso calculados."""

    with conexion() as con:
        return deudas_repo.listar(con)


def obtener_deuda(deuda_id: int) -> Deuda | None:
    """Recupera una deuda específica."""

    with conexion() as con:
        return deudas_repo.obtener(con, deuda_id)


def deudas_con_alerta(fecha_referencia: date | None = None) -> list[Deuda]:
    """Deudas cuyo próximo pago está vencido o a punto de vencer."""

    return [
        deuda
        for deuda in obtener_deudas()
        if deuda.requiere_atencion(fecha_referencia)
    ]


# =========================================================================
# Abonos
# =========================================================================


def registrar_abono(
    deuda_id: int,
    valor: float,
    fecha: date | None = None,
    descripcion: str = "",
    reprogramar: str = SIN_CAMBIO,
) -> int:
    """Registra un abono y lo refleja como movimiento de caja.

    La validación del saldo y la escritura del abono, del movimiento asociado,
    del estado de la deuda y del recordatorio se ejecutan en una única
    transacción: si algo falla, ni el dinero ni el próximo pago quedan a medias.

    ``reprogramar`` decide qué ocurre con el recordatorio al pagar. Por defecto
    no se toca, porque un abono puede ser parcial y no corresponder al pago
    programado.
    """

    fecha_abono = fecha or date.today()
    descripcion = (descripcion or "").strip()

    with transaccion() as con:
        deuda = deudas_repo.obtener(con, deuda_id)

        if deuda is None:
            raise ValueError("La deuda no existe.")

        importe = redondear(valor)

        if importe <= 0:
            raise ValueError(
                "El valor del abono debe ser mayor que cero."
            )

        if deuda.pagada:
            raise ValueError("Esta deuda ya está pagada.")

        if importe > deuda.saldo_pendiente:
            raise ValueError(
                "El abono no puede ser superior al saldo pendiente."
            )

        abono_id = deudas_repo.insertar_abono(
            con,
            Abono(
                deuda_id=deuda_id,
                fecha=fecha_abono,
                valor=importe,
                descripcion=descripcion,
            ),
        )

        movimientos_repo.insertar(
            con,
            Movimiento(
                fecha=fecha_abono,
                tipo=TIPO_GASTO,
                valor=importe,
                categoria_id=categorias_service.obtener_o_crear_id(
                    con,
                    CATEGORIA_DEUDAS,
                    TIPO_GASTO,
                ),
                descripcion=descripcion or f"Abono: {deuda.nombre}",
                abono_id=abono_id,
            ),
        )

        deudas_repo.sincronizar_estado(con, deuda_id)
        _reprogramar(con, deuda, reprogramar)

    logger.info(
        "Abono registrado id=%s deuda=%s valor=%s",
        abono_id,
        deuda_id,
        importe,
    )

    return abono_id


def _reprogramar(
    con,
    deuda: Deuda,
    reprogramar: str,
) -> None:
    """Ajusta el recordatorio de la deuda según lo elegido al pagar.

    La modalidad se valida antes de comprobar si hay fecha: un valor desconocido
    es un error del programa y no debe quedar enmascarado porque la deuda no
    tuviera recordatorio.
    """

    if reprogramar == SIN_CAMBIO:
        return

    if reprogramar != QUITAR_RECORDATORIO and reprogramar not in DESPLAZAMIENTOS:
        raise ValueError(
            f"Reprogramación del recordatorio no válida: {reprogramar!r}."
        )

    # Sin fecha programada no hay nada que desplazar ni que retirar.
    if deuda.fecha_proximo_pago is None:
        return

    if reprogramar == QUITAR_RECORDATORIO:
        deudas_repo.actualizar_proximo_pago(con, deuda.id, None)
        logger.info("Recordatorio retirado de la deuda %s", deuda.id)
        return

    meses, dias = DESPLAZAMIENTOS[reprogramar]

    nueva = siguiente_vencimiento(deuda.fecha_proximo_pago, meses, dias)

    deudas_repo.actualizar_proximo_pago(con, deuda.id, nueva)

    logger.info(
        "Recordatorio de la deuda %s reprogramado de %s a %s",
        deuda.id,
        deuda.fecha_proximo_pago,
        nueva,
    )


def actualizar_abono(
    deuda_id: int,
    abono_id: int,
    valor: float,
    fecha: date | None = None,
    descripcion: str = "",
) -> bool:
    """Corrige el importe, la fecha o la nota de un abono ya registrado.

    El tope del nuevo importe es el saldo pendiente más lo que este mismo abono
    aportaba: corregirlo al alza no puede llevar el total abonado por encima del
    monto inicial de la deuda.
    """

    fecha_abono = fecha or date.today()
    descripcion = (descripcion or "").strip()

    with transaccion() as con:
        deuda = deudas_repo.obtener(con, deuda_id)
        abono = deudas_repo.obtener_abono(con, abono_id)

        if deuda is None:
            raise ValueError("La deuda no existe.")

        if abono is None or abono.deuda_id != deuda_id:
            raise ValueError("El abono no pertenece a esta deuda.")

        importe = redondear(valor)

        if importe <= 0:
            raise ValueError("El valor del abono debe ser mayor que cero.")

        maximo = redondear(deuda.saldo_pendiente + abono.valor)

        if importe > maximo:
            raise ValueError(
                "El abono no puede superar el saldo pendiente de la deuda "
                f"({formatear_dinero(maximo)})."
            )

        deudas_repo.actualizar_abono(
            con,
            abono_id,
            fecha=fecha_abono,
            valor=importe,
            descripcion=descripcion,
        )

        movimientos_repo.actualizar_por_abono(
            con,
            abono_id,
            fecha=fecha_abono,
            valor=importe,
            descripcion=descripcion or f"Abono: {deuda.nombre}",
        )

        deudas_repo.sincronizar_estado(con, deuda_id)

    logger.info(
        "Abono actualizado id=%s deuda=%s valor=%s",
        abono_id,
        deuda_id,
        importe,
    )

    return True


def eliminar_abono(deuda_id: int, abono_id: int) -> bool:
    """Elimina un abono y revierte su efecto sobre la deuda.

    El movimiento asociado se retira en cascada desde ``abonos``, de modo que el
    dinero vuelve a contar como disponible.
    """

    with transaccion() as con:
        abono = deudas_repo.obtener_abono(con, abono_id)

        if abono is None or abono.deuda_id != deuda_id:
            return False

        eliminado = deudas_repo.eliminar_abono(con, abono_id) is not None

        if eliminado:
            deudas_repo.sincronizar_estado(con, deuda_id)

    if eliminado:
        logger.info("Abono eliminado id=%s deuda=%s", abono_id, deuda_id)

    return eliminado


def obtener_abonos(deuda_id: int) -> list[Abono]:
    """Lista el historial de abonos de una deuda."""

    with conexion() as con:
        return deudas_repo.listar_abonos(con, deuda_id)


# =========================================================================
# Agregados
# =========================================================================


def pagado_a_deudas_mes(fecha_referencia: date | None = None) -> float:
    """Total abonado a deudas durante el mes de referencia.

    Permite que el resumen desglose cuánto del dinero que salió de la cuenta en
    el periodo se destinó a deudas.
    """

    inicio, fin = rango_mes(fecha_referencia)

    with conexion() as con:
        return deudas_repo.total_abonos_mes(con, inicio, fin)


def obtener_total_deudas_pendientes() -> float:
    """Calcula el total pendiente de todas las deudas vigentes."""

    return redondear(
        sum(
            deuda.saldo_pendiente
            for deuda in obtener_deudas()
            if not deuda.pagada
        )
    )


def eliminar_deuda(deuda_id: int) -> bool:
    """Elimina una deuda junto con sus abonos y los movimientos asociados.

    La eliminación se delega a las claves foráneas del esquema
    (``abonos`` -> ``deudas`` y ``movimientos`` -> ``abonos``), evitando que
    queden movimientos huérfanos que alteren el saldo del usuario.
    """

    with transaccion() as con:
        eliminada = deudas_repo.eliminar(con, deuda_id)

    if eliminada:
        logger.info("Deuda eliminada id=%s", deuda_id)

    return eliminada
