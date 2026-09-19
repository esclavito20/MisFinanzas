"""Utilidades transversales sin dependencias del dominio.

A diferencia de las capas de datos, aquí cada módulo agrupa funciones pequeñas
y sin estado, de modo que el paquete expone las funciones directamente y quien
las usa no necesita recordar en qué archivo vive cada una.
"""

from utils.dinero import (
    formatear_dinero,
    formatear_porcentaje,
    redondear,
)
from utils.fechas import (
    a_iso,
    desde_iso,
    dias_del_mes,
    dias_entre,
    fecha_normalizada,
    formatear_fecha,
    rango_mes,
    sumar_meses,
)
from utils.versiones import comparar, es_mas_reciente, partir_version

__all__ = [
    "a_iso",
    "comparar",
    "desde_iso",
    "dias_del_mes",
    "dias_entre",
    "es_mas_reciente",
    "fecha_normalizada",
    "formatear_dinero",
    "formatear_fecha",
    "formatear_porcentaje",
    "partir_version",
    "rango_mes",
    "redondear",
    "sumar_meses",
]
