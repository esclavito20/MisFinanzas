"""Modelo de una actualización publicada.

Describe la versión remota tal como la anuncia su repositorio: qué versión es,
de dónde se descarga su instalador, con qué resumen criptográfico verificarlo y
las notas que la acompañan. Es un objeto de solo lectura: la actualización no se
altera después de interpretar la respuesta del servidor.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.versiones import es_mas_reciente

LONGITUD_SHA256 = 64


@dataclass(frozen=True)
class InfoActualizacion:
    """Versión publicada y su instalador."""

    version: str
    url_descarga: str
    nombre_instalador: str = ""
    sha256: str = ""
    tamano: int = 0
    notas: str = ""
    publicada: str = ""
    direccion_publicacion: str = ""

    def supera_a(self, version_local: str) -> bool:
        """Indica si esta versión es posterior a la instalada."""

        return es_mas_reciente(self.version, version_local)

    @property
    def verificable(self) -> bool:
        """Indica si la publicación permite comprobar la descarga.

        Sin resumen SHA-256 no es posible demostrar que el instalador
        descargado es el que publicó el repositorio, por lo que la aplicación
        no lo ejecuta.
        """

        return len(self.sha256) == LONGITUD_SHA256

    @property
    def notas_limpias(self) -> str:
        return (self.notas or "").strip()
