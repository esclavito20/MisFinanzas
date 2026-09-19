"""Normalización y comparación de versiones numéricas.

Las versiones se comparan como tuplas de enteros y nunca como texto: sin esa
normalización ``2.10.0`` resultaría "menor" que ``2.9.0`` por orden alfabético y
la aplicación rechazaría actualizaciones legítimas.
"""

from __future__ import annotations

SEPARADOR = "."
PREFIJOS = "vV"


def partir_version(texto: str | None) -> tuple[int, ...]:
    """Convierte una etiqueta de versión en una tupla comparable.

    Admite las etiquetas que usa GitHub (``v2.2.0``) y descarta los sufijos de
    previsualización: ``2.3.0-rc1`` se reduce a ``(2, 3, 0)``, de modo que una
    versión de prueba nunca supera a la definitiva de la misma serie. Una
    cadena sin dígitos iniciales se interpreta como ``(0,)``.
    """

    limpio = (texto or "").strip().lstrip(PREFIJOS)
    numeros: list[int] = []

    for fragmento in limpio.split(SEPARADOR):
        digitos = ""

        for caracter in fragmento:
            if not caracter.isdigit():
                break

            digitos += caracter

        if not digitos:
            break

        numeros.append(int(digitos))

    return tuple(numeros) or (0,)


def comparar(izquierda: str | None, derecha: str | None) -> int:
    """Devuelve -1, 0 o 1 según el orden de las dos versiones."""

    partes_izquierda = partir_version(izquierda)
    partes_derecha = partir_version(derecha)

    largo = max(len(partes_izquierda), len(partes_derecha))
    partes_izquierda += (0,) * (largo - len(partes_izquierda))
    partes_derecha += (0,) * (largo - len(partes_derecha))

    return (partes_izquierda > partes_derecha) - (
        partes_izquierda < partes_derecha
    )


def es_mas_reciente(remota: str | None, local: str | None) -> bool:
    """Indica si la versión remota supera a la instalada."""

    return comparar(remota, local) > 0
