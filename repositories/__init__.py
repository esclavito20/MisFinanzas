"""Capa de repositorios: SQL aislado y mapeo a modelos de dominio.

Todas las funciones reciben una conexión explícita, de modo que el límite
transaccional pertenece siempre a la capa de servicios y las consultas son
verificables de forma aislada.

El paquete expone un módulo por agregado; fuera de él se importan sus módulos,
no sus funciones sueltas, para que el origen de cada consulta quede explícito.
"""

from repositories import (
    categorias_repo,
    deudas_repo,
    inversiones_repo,
    movimientos_repo,
    suscripciones_repo,
)

__all__ = [
    "categorias_repo",
    "deudas_repo",
    "inversiones_repo",
    "movimientos_repo",
    "suscripciones_repo",
]
