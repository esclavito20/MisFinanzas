"""Normalización y presentación de importes monetarios y porcentajes.

Los importes se persisten como ``REAL``; para evitar la propagación de errores
de redondeo binario toda escritura y toda agregación pasa por
:func:`redondear`, que aplica redondeo comercial (half-up) sobre ``Decimal``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENTIMOS = Decimal("0.01")


def redondear(valor: object) -> float:
    """Normaliza un importe a dos decimales con redondeo comercial."""

    try:
        decimal = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0

    if not decimal.is_finite():
        return 0.0

    return float(decimal.quantize(CENTIMOS, rounding=ROUND_HALF_UP))


def formatear_dinero(valor: object) -> str:
    """Formatea un importe con separadores colombianos.

    Los importes sin parte decimal se muestran sin centavos para conservar la
    legibilidad del diseño original: ``$ 1.250.000``. Los importes con centavos
    se muestran completos: ``$ 1.250.000,50``.
    """

    importe = Decimal(str(redondear(valor)))

    if importe == importe.to_integral_value():
        texto = f"{importe:,.0f}"
    else:
        texto = f"{importe:,.2f}"

    # Conversión de separadores en-US (,) (.) a es-CO (.) (,).
    return "$ " + texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def formatear_porcentaje(valor: object, decimales: int = 1) -> str:
    """Formatea un porcentaje con la convención decimal local (``40,0%``)."""

    return f"{redondear(valor):.{decimales}f}%".replace(".", ",")
