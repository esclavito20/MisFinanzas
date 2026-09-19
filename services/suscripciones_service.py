"""Lógica de negocio de suscripciones y proyección de compromisos.

El modelo de esta capa es **proyectivo**: las suscripciones no escriben gastos
por sí mismas. Restan del dinero disponible a través del compromiso pendiente
del mes y solo se materializan como gasto cuando el usuario confirma el cobro,
de modo que el histórico contable nunca contiene datos sintéticos.
"""

from __future__ import annotations

import logging
from datetime import date

from database.conexion import conexion, transaccion
from database.semilla import CATEGORIA_SUSCRIPCIONES
from models.movimiento import TIPO_GASTO, Movimiento
from models.suscripcion import (
    DIA_MAXIMO,
    DIA_MINIMO,
    ESTADO_ACTIVA,
    ESTADO_FINALIZADA,
    PERIODICIDAD_ANUAL,
    PERIODICIDADES_VALIDAS,
    Suscripcion,
)
from repositories import movimientos_repo, suscripciones_repo
from services import categorias_service
from utils.dinero import redondear

logger = logging.getLogger(__name__)


def _validar_datos(
    nombre: str,
    costo: float,
    periodicidad: str,
    dia_facturacion: int,
    mes_facturacion: int | None,
) -> tuple[str, float, int | None]:
    """Valida las invariantes de una suscripción."""

    nombre = (nombre or "").strip()

    if not nombre:
        raise ValueError("El nombre de la suscripción es obligatorio.")

    importe = redondear(costo)

    if importe <= 0:
        raise ValueError("El costo debe ser mayor que cero.")

    if periodicidad not in PERIODICIDADES_VALIDAS:
        raise ValueError(
            f"Periodicidad no válida: {periodicidad!r}. "
            f"Use {' o '.join(PERIODICIDADES_VALIDAS)}."
        )

    if not DIA_MINIMO <= int(dia_facturacion) <= DIA_MAXIMO:
        raise ValueError(
            f"El día de facturación debe estar entre {DIA_MINIMO} y "
            f"{DIA_MAXIMO}."
        )

    if periodicidad == PERIODICIDAD_ANUAL:
        if mes_facturacion is None or not 1 <= int(mes_facturacion) <= 12:
            raise ValueError(
                "Una suscripción anual requiere el mes de facturación."
            )
    else:
        # El mes solo tiene sentido en los ciclos anuales; se descarta para que
        # el registro sea coherente con su periodicidad.
        mes_facturacion = None

    return nombre, importe, mes_facturacion


def crear_suscripcion(
    nombre: str,
    costo: float,
    periodicidad: str,
    dia_facturacion: int,
    fecha_inicio: date | None = None,
    mes_facturacion: int | None = None,
    descripcion: str = "",
) -> int:
    """Registra una suscripción. Devuelve su identificador."""

    nombre, importe, mes_facturacion = _validar_datos(
        nombre,
        costo,
        periodicidad,
        dia_facturacion,
        mes_facturacion,
    )

    with transaccion() as con:
        suscripcion_id = suscripciones_repo.insertar(
            con,
            Suscripcion(
                id=0,
                nombre=nombre,
                costo=importe,
                periodicidad=periodicidad,
                dia_facturacion=int(dia_facturacion),
                fecha_inicio=fecha_inicio or date.today(),
                mes_facturacion=mes_facturacion,
                estado=ESTADO_ACTIVA,
                descripcion=(descripcion or "").strip(),
            ),
        )

    logger.info(
        "Suscripción creada id=%s nombre=%s costo=%s",
        suscripcion_id,
        nombre,
        importe,
    )

    return suscripcion_id


def obtener_suscripciones(solo_activas: bool = False) -> list[Suscripcion]:
    """Lista las suscripciones registradas."""

    with conexion() as con:
        return suscripciones_repo.listar(con, solo_activas)


def obtener_suscripcion(suscripcion_id: int) -> Suscripcion | None:
    """Recupera una suscripción específica."""

    with conexion() as con:
        return suscripciones_repo.obtener(con, suscripcion_id)


def detener_ciclo(
    suscripcion_id: int,
    fecha: date | None = None,
) -> bool:
    """Detiene el ciclo de facturación conservando el histórico."""

    with transaccion() as con:
        detenida = suscripciones_repo.actualizar_ciclo(
            con,
            suscripcion_id,
            ESTADO_FINALIZADA,
            fecha or date.today(),
        )

    if detenida:
        logger.info("Ciclo detenido para la suscripción id=%s", suscripcion_id)

    return detenida


def reactivar_ciclo(suscripcion_id: int) -> bool:
    """Reactiva una suscripción cuyo ciclo había sido detenido."""

    with transaccion() as con:
        reactivada = suscripciones_repo.actualizar_ciclo(
            con,
            suscripcion_id,
            ESTADO_ACTIVA,
            None,
        )

    if reactivada:
        logger.info(
            "Ciclo reactivado para la suscripción id=%s", suscripcion_id
        )

    return reactivada


def eliminar_suscripcion(suscripcion_id: int) -> bool:
    """Elimina una suscripción sin borrar los gastos ya registrados."""

    with transaccion() as con:
        eliminada = suscripciones_repo.eliminar(con, suscripcion_id)

    if eliminada:
        logger.info("Suscripción eliminada id=%s", suscripcion_id)

    return eliminada


def registrar_pago(
    suscripcion_id: int,
    fecha: date | None = None,
    descripcion: str = "",
) -> int:
    """Materializa el cobro de un ciclo como gasto.

    La comprobación de duplicidad y la inserción comparten transacción, por lo
    que dos confirmaciones del mismo ciclo no pueden generar dos gastos.
    """

    fecha_cobro = fecha or date.today()
    descripcion = (descripcion or "").strip()

    with transaccion() as con:
        suscripcion = suscripciones_repo.obtener(con, suscripcion_id)

        if suscripcion is None:
            raise ValueError("La suscripción no existe.")

        if movimientos_repo.existe_pago_de_suscripcion(
            con, suscripcion_id, fecha_cobro
        ):
            raise ValueError(
                "Ya registraste el cobro de esta suscripción en esa fecha."
            )

        movimiento_id = movimientos_repo.insertar(
            con,
            Movimiento(
                fecha=fecha_cobro,
                tipo=TIPO_GASTO,
                valor=suscripcion.costo,
                categoria_id=categorias_service.obtener_o_crear_id(
                    con,
                    CATEGORIA_SUSCRIPCIONES,
                    TIPO_GASTO,
                ),
                descripcion=(
                    descripcion or f"Suscripción: {suscripcion.nombre}"
                ),
                suscripcion_id=suscripcion_id,
            ),
        )

    logger.info(
        "Cobro registrado id=%s suscripcion=%s valor=%s",
        movimiento_id,
        suscripcion_id,
        suscripcion.costo,
    )

    return movimiento_id


def pagos_registrados() -> dict[int, set[date]]:
    """Fechas de ciclo ya cobradas, agrupadas por suscripción."""

    with conexion() as con:
        return movimientos_repo.pagos_por_suscripcion(con)


def cobros_registrados(suscripcion_id: int) -> set[date]:
    """Fechas de ciclo ya cobradas de una suscripción."""

    return pagos_registrados().get(suscripcion_id, set())


def comprometido_mes(fecha_referencia: date | None = None) -> float:
    """Cobros del mes en curso que aún están pendientes de pago.

    Solo se consideran los cargos cuya fecha es igual o posterior a la fecha de
    referencia y que no se hayan registrado todavía: los ya transcurridos se
    asumen pagados y descontados del saldo real, y los ya registrados generaron
    su propio gasto, por lo que volver a restarlos duplicaría el compromiso.
    """

    referencia = fecha_referencia or date.today()
    pagos = pagos_registrados()
    total = 0.0

    for suscripcion in obtener_suscripciones(solo_activas=True):
        cobrados = pagos.get(suscripcion.id, set())
        pendientes = [
            cobro
            for cobro in suscripcion.cobros_pendientes(referencia)
            if cobro not in cobrados
        ]
        total += suscripcion.costo * len(pendientes)

    return redondear(total)


def costo_mensual_equivalente() -> float:
    """Costo mensual normalizado de todas las suscripciones vigentes."""

    return redondear(
        sum(
            suscripcion.costo_mensual_equivalente
            for suscripcion in obtener_suscripciones(solo_activas=True)
        )
    )


def proximo_cobro(
    fecha_referencia: date | None = None,
) -> tuple[Suscripcion, date] | None:
    """Suscripción y fecha del cobro más cercano por ocurrir."""

    referencia = fecha_referencia or date.today()
    proximo: tuple[Suscripcion, date] | None = None

    for suscripcion in obtener_suscripciones(solo_activas=True):
        cobro = suscripcion.proximo_cobro(referencia)

        if cobro is None:
            continue

        if proximo is None or cobro < proximo[1]:
            proximo = (suscripcion, cobro)

    return proximo
