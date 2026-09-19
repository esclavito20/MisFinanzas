"""Modelo de deuda con saldo, progreso y recordatorio de pago.

``estado`` no se persiste como fuente de verdad: el saldo pendiente se calcula
siempre a partir del total abonado, único dato que no puede desincronizarse.

El recordatorio de próximo pago es opcional y se compone de dos datos
independientes: la fecha (sin la cual no hay alerta) y el valor mínimo que se
espera pagar. Su situación se deriva de la fecha comparada con el día en curso,
de modo que la alerta se actualiza sola sin reescribir la base.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from utils.dinero import redondear
from utils.fechas import sumar_meses

ESTADO_PENDIENTE = "pendiente"
ESTADO_PAGADA = "pagada"

ALERTA_NINGUNA = "ninguna"
ALERTA_PROGRAMADA = "programada"
ALERTA_PROXIMA = "proxima"
ALERTA_VENCIDA = "vencida"

# Antelación con la que el recordatorio pasa a considerarse inminente.
DIAS_DE_AVISO = 5

# Periodos con los que se puede desplazar el recordatorio al registrar un abono.
PERIODO_SEMANAL = "semana"
PERIODO_QUINCENAL = "quincena"
PERIODO_MENSUAL = "mes"

DESPLAZAMIENTOS: dict[str, tuple[int, int]] = {
    PERIODO_SEMANAL: (0, 7),
    PERIODO_QUINCENAL: (0, 15),
    PERIODO_MENSUAL: (1, 0),
}

# Tope de periodos que se suman de una vez. Acota el recorrido cuando la fecha
# almacenada quedó muy atrás: 50 años de pagos mensuales son suficientes para
# cualquier deuda real y evitan un bucle sin salida si el dato estuviera dañado.
MAXIMO_PERIODOS = 600


def _desplazar(fecha: date, meses: int, dias: int) -> date:
    return sumar_meses(fecha, meses) if meses else fecha + timedelta(days=dias)


def siguiente_vencimiento(
    fecha: date,
    meses: int = 1,
    dias: int = 0,
    referencia: date | None = None,
) -> date:
    """Primer vencimiento futuro al desplazar una fecha por periodos.

    Se avanza **al menos un periodo** —quien acaba de pagar no vuelve a deber la
    misma fecha— y se sigue avanzando mientras el resultado no quede por delante
    del día de referencia, de modo que un recordatorio sin actualizar durante
    varios periodos recupere el próximo pago realmente pendiente.
    """

    if meses <= 0 and dias <= 0:
        return fecha

    hoy = referencia or date.today()
    nueva = _desplazar(fecha, meses, dias)
    periodos = 1

    while nueva <= hoy and periodos < MAXIMO_PERIODOS:
        nueva = _desplazar(nueva, meses, dias)
        periodos += 1

    return nueva


@dataclass
class Deuda:
    """Deuda con su agregado de abonos y su recordatorio de pago."""

    id: int
    nombre: str
    monto_inicial: float
    fecha_creacion: date | None = None
    descripcion: str = ""
    total_abonado: float = 0.0
    pago_minimo: float | None = None
    fecha_proximo_pago: date | None = None

    @property
    def saldo_pendiente(self) -> float:
        return redondear(max(self.monto_inicial - self.total_abonado, 0.0))

    @property
    def porcentaje(self) -> float:
        if self.monto_inicial <= 0:
            return 0.0

        return min(self.total_abonado / self.monto_inicial * 100, 100.0)

    @property
    def pagada(self) -> bool:
        return self.saldo_pendiente <= 0

    @property
    def estado(self) -> str:
        return ESTADO_PAGADA if self.pagada else ESTADO_PENDIENTE

    # ------------------------------------------------------------------
    # Recordatorio de pago
    # ------------------------------------------------------------------

    def dias_para_pago(self, referencia: date | None = None) -> int | None:
        """Días que faltan para el próximo pago; negativo si ya venció."""

        if self.fecha_proximo_pago is None:
            return None

        return (self.fecha_proximo_pago - (referencia or date.today())).days

    def alerta(self, referencia: date | None = None) -> str:
        """Situación del recordatorio en la fecha de referencia."""

        if self.fecha_proximo_pago is None or self.pagada:
            return ALERTA_NINGUNA

        dias = self.dias_para_pago(referencia)
        dias = 0 if dias is None else dias

        if dias < 0:
            return ALERTA_VENCIDA

        if dias <= DIAS_DE_AVISO:
            return ALERTA_PROXIMA

        return ALERTA_PROGRAMADA

    def requiere_atencion(self, referencia: date | None = None) -> bool:
        """Indica si el recordatorio está vencido o a punto de vencer."""

        return self.alerta(referencia) in (ALERTA_VENCIDA, ALERTA_PROXIMA)
