"""Capa de servicios: reglas de negocio y límites transaccionales.

El paquete expone un módulo por área funcional; fuera de él se importan sus
módulos, no sus funciones sueltas, porque varios comparten nombre —``listar``,
``obtener``, ``eliminar``— y el módulo es lo que da contexto a cada uno.
"""

from services import (
    actualizaciones_service,
    categorias_service,
    datos_service,
    deudas_service,
    inversiones_service,
    movimientos_service,
    sincronizacion_service,
    suscripciones_service,
)

__all__ = [
    "actualizaciones_service",
    "categorias_service",
    "datos_service",
    "deudas_service",
    "inversiones_service",
    "movimientos_service",
    "sincronizacion_service",
    "suscripciones_service",
]
