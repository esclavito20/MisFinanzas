"""Modelo de suscripción con proyección de cobros derivada del calendario.

La proyección es **determinista**: la fecha del próximo cobro se calcula desde
``fecha_inicio``, ``periodicidad`` y ``dia_facturacion``, sin depender de
temporizadores ni de procesos en segundo plano. Ese diseño es el único fiable
en plataformas móviles, donde el sistema operativo puede terminar el proceso y
donde un trabajo programado no se ejecutaría.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from utils.dinero import redondear
from utils.fechas import fecha_normalizada

PERIODICIDAD_MENSUAL = "mensual"
PERIODICIDAD_ANUAL = "anual"
PERIODICIDADES_VALIDAS = (PERIODICIDAD_MENSUAL, PERIODICIDAD_ANUAL)

ETIQUETAS_PERIODICIDAD = {
    PERIODICIDAD_MENSUAL: "Mensual",
    PERIODICIDAD_ANUAL: "Anual",
}

MESES_POR_PERIODICIDAD = {
    PERIODICIDAD_MENSUAL: 1,
    PERIODICIDAD_ANUAL: 12,
}

ESTADO_ACTIVA = "activa"
ESTADO_FINALIZADA = "finalizada"

# Meses que se recorren al buscar el próximo cobro: cubre con margen los ciclos
# mensuales y anuales sin bucles sin cota.
MESES_DE_PROYECCION = 24

DIA_MINIMO = 1
DIA_MAXIMO = 31


@dataclass
class Suscripcion:
    """Suscripción recurrente con costo y ciclo de facturación."""

    id: int
    nombre: str
    costo: float
    periodicidad: str
    dia_facturacion: int
    fecha_inicio: date
    mes_facturacion: int | None = None
    fecha_fin: date | None = None
    estado: str = ESTADO_ACTIVA
    descripcion: str = ""

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    @property
    def activa(self) -> bool:
        return self.estado == ESTADO_ACTIVA

    @property
    def etiqueta_periodicidad(self) -> str:
        return ETIQUETAS_PERIODICIDAD.get(self.periodicidad, self.periodicidad)

    @property
    def costo_mensual_equivalente(self) -> float:
        """Costo normalizado a un mes (las anuales se prorratean)."""

        return redondear(
            self.costo / MESES_POR_PERIODICIDAD.get(self.periodicidad, 1)
        )

    # ------------------------------------------------------------------
    # Proyección de cobros
    # ------------------------------------------------------------------

    def cobro_en(self, anio: int, mes: int) -> date | None:
        """Fecha de cobro dentro de un mes, si el ciclo la produce."""

        if (
            self.periodicidad == PERIODICIDAD_ANUAL
            and self.mes_facturacion is not None
            and mes != self.mes_facturacion
        ):
            return None

        return fecha_normalizada(anio, mes, self.dia_facturacion)

    def cobros_del_mes(self, anio: int, mes: int) -> list[date]:
        """Cobros del mes, excluyendo los anteriores al inicio del ciclo."""

        cobro = self.cobro_en(anio, mes)

        if cobro is None or cobro < self.fecha_inicio:
            return []

        return [cobro]

    def proximo_cobro(self, desde: date) -> date | None:
        """Primer cobro a partir de ``desde`` (inclusive), o ``None``."""

        if not self.activa:
            return None

        anio, mes = desde.year, desde.month

        for _ in range(MESES_DE_PROYECCION):
            for cobro in self.cobros_del_mes(anio, mes):
                if cobro >= desde:
                    return cobro

            anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)

        return None

    def cobros_pendientes(self, referencia: date) -> list[date]:
        """Cobros del mes de referencia que aún no han ocurrido."""

        return [
            cobro
            for cobro in self.cobros_del_mes(referencia.year, referencia.month)
            if cobro >= referencia
        ]
