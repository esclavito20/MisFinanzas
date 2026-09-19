"""Conversión y cálculo de rangos de fechas en formato ISO (YYYY-MM-DD)."""

from __future__ import annotations

import calendar
from datetime import date


def desde_iso(texto: str | None) -> date | None:
    """Convierte una fecha ISO almacenada en la base de datos."""

    if not texto:
        return None

    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def a_iso(fecha: date | None) -> str:
    """Convierte una fecha a su representación ISO."""

    return (fecha or date.today()).isoformat()


def formatear_fecha(fecha: date | None, formato: str = "%d/%m/%Y") -> str:
    """Presenta una fecha con la convención local, no en ISO.

    La ISO se reserva para el almacenamiento y los archivos de intercambio; en
    pantalla la misma fecha se escribe como el usuario la introduce en los
    formularios, que usan ``dd/MM/yyyy``.
    """

    return fecha.strftime(formato) if fecha else ""


def rango_mes(fecha_referencia: date | None = None) -> tuple[str, str]:
    """Devuelve el rango semiabierto [inicio, fin) del mes de referencia.

    Sustituye al cálculo ``date(fecha, '+1 month')`` de SQLite por límites
    explícitos, lo que permite usarlos como condiciones *sargables* contra los
    índices de la tabla ``movimientos``.
    """

    referencia = fecha_referencia or date.today()
    inicio = referencia.replace(day=1)

    if inicio.month == 12:
        fin = inicio.replace(year=inicio.year + 1, month=1)
    else:
        fin = inicio.replace(month=inicio.month + 1)

    return inicio.isoformat(), fin.isoformat()


def dias_del_mes(anio: int, mes: int) -> int:
    """Cantidad de días de un mes concreto."""

    return calendar.monthrange(anio, mes)[1]


def fecha_normalizada(anio: int, mes: int, dia: int) -> date:
    """Construye una fecha ajustando el día al último del mes cuando excede.

    Una facturación configurada para el día 31 debe cobrarse el 28/29 de
    febrero y el 30 en los meses de 30 días, no generar una fecha inválida.
    """

    return date(anio, mes, min(dia, dias_del_mes(anio, mes)))


def sumar_meses(fecha: date, meses: int) -> date:
    """Desplaza una fecha en meses conservando el día cuando existe."""

    total = fecha.month - 1 + meses
    anio = fecha.year + total // 12
    mes = total % 12 + 1

    return fecha_normalizada(anio, mes, fecha.day)


def dias_entre(inicio: date, fin: date) -> int:
    """Días transcurridos entre dos fechas, nunca negativos."""

    return max((fin - inicio).days, 0)
