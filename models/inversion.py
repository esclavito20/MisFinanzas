"""Modelo de inversión con rendimiento devengado calculado por tasa efectiva.

Colombia expresa la rentabilidad de captación como **tasa efectiva anual**
(EA). El valor futuro de un capital con tasa constante se obtiene por
capitalización compuesta ``VF = C · (1 + EA)^(días / 365)``, expresión válida
tanto para un CDT (abono de intereses al vencimiento) como para una cuenta de
ahorro de capitalización diaria con tasa constante.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from utils.dinero import redondear
from utils.fechas import dias_entre

TIPO_CDT = "cdt"
TIPO_CAJITA_NU = "cajita_nu"
TIPOS_VALIDOS = (TIPO_CDT, TIPO_CAJITA_NU)

ETIQUETAS_TIPO = {
    TIPO_CDT: "CDT",
    TIPO_CAJITA_NU: "Cajita de NU",
}

ESTADO_ACTIVA = "activa"
ESTADO_FINALIZADA = "finalizada"

DIAS_POR_ANIO = 365

# Tasa típica de retención en la fuente sobre rendimientos financieros.
# Es un valor por defecto editable por inversión: debe confirmarse con la
# normativa vigente antes de darlo por definitivo.
RETENCION_POR_DEFECTO = 4.0


@dataclass
class Inversion:
    """Capital invertido con su tasa efectiva anual y plazo."""

    id: int
    tipo: str
    capital: float
    tasa_ea: float
    fecha_inicio: date
    entidad: str = ""
    plazo_dias: int | None = None
    fecha_vencimiento: date | None = None
    retencion_porcentaje: float = RETENCION_POR_DEFECTO
    estado: str = ESTADO_ACTIVA
    descripcion: str = ""

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    @property
    def activa(self) -> bool:
        return self.estado == ESTADO_ACTIVA

    @property
    def etiqueta_tipo(self) -> str:
        return ETIQUETAS_TIPO.get(self.tipo, self.tipo)

    @property
    def es_plazo_fijo(self) -> bool:
        return self.tipo == TIPO_CDT

    # ------------------------------------------------------------------
    # Plazos
    # ------------------------------------------------------------------

    def dias_transcurridos(self, hasta: date | None = None) -> int:
        return dias_entre(self.fecha_inicio, hasta or date.today())

    def dias_totales(self, hasta: date | None = None) -> int:
        """Días del plazo pactado; en inversiones abiertas, los devengados."""

        if self.plazo_dias is not None:
            return self.plazo_dias

        return self.dias_transcurridos(hasta)

    def progreso(self, hasta: date | None = None) -> float:
        """Porcentaje del plazo transcurrido (0 en inversiones abiertas)."""

        if self.plazo_dias is None or self.plazo_dias <= 0:
            return 0.0

        return min(
            self.dias_transcurridos(hasta) / self.plazo_dias * 100,
            100.0,
        )

    def vencida(self, hasta: date | None = None) -> bool:
        if self.plazo_dias is None:
            return False

        return self.dias_transcurridos(hasta) >= self.plazo_dias

    # ------------------------------------------------------------------
    # Rendimiento
    # ------------------------------------------------------------------

    def _factor_capitalizacion(self, dias: int) -> float:
        if dias <= 0 or self.tasa_ea <= 0:
            return 1.0

        return (1 + self.tasa_ea / 100) ** (dias / DIAS_POR_ANIO)

    def valor_futuro(self, dias: int) -> float:
        """Capital más rendimiento bruto al cabo de ``dias``."""

        return redondear(self.capital * self._factor_capitalizacion(dias))

    def rendimiento_bruto(self, hasta: date | None = None) -> float:
        """Rendimiento devengado antes de retención."""

        return redondear(
            self.valor_futuro(self.dias_transcurridos(hasta)) - self.capital
        )

    def retencion(self, hasta: date | None = None) -> float:
        return redondear(
            self.rendimiento_bruto(hasta) * self.retencion_porcentaje / 100
        )

    def rendimiento_neto(self, hasta: date | None = None) -> float:
        """Rendimiento que efectivamente se acredita al inversionista."""

        return redondear(
            self.rendimiento_bruto(hasta) - self.retencion(hasta)
        )

    def valor_actual(self, hasta: date | None = None) -> float:
        """Capital más el rendimiento neto devengado a la fecha de corte."""

        return redondear(self.capital + self.rendimiento_neto(hasta))

    def rendimiento_bruto_proyectado(self) -> float:
        """Rendimiento antes de retención si se mantiene hasta el vencimiento."""

        if self.plazo_dias is None:
            return 0.0

        return redondear(
            self.valor_futuro(self.plazo_dias) - self.capital
        )

    def rendimiento_proyectado(self) -> float:
        """Rendimiento neto si la inversión se mantiene hasta el vencimiento."""

        return redondear(
            self.rendimiento_bruto_proyectado()
            * (1 - self.retencion_porcentaje / 100)
        )

    def valor_proyectado(self) -> float:
        """Capital más rendimiento neto al vencimiento."""

        if self.plazo_dias is None:
            return self.capital

        return redondear(self.capital + self.rendimiento_proyectado())

    def fecha_fin_estimada(self) -> date | None:
        """Vencimiento: el pactado o, en inversiones abiertas, el de hoy."""

        if self.fecha_vencimiento is not None:
            return self.fecha_vencimiento

        if self.plazo_dias is None:
            return None

        return self.fecha_inicio + timedelta(days=self.plazo_dias)
