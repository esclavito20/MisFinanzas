"""Lógica de actualización: consulta, verificación y aplicación.

Esta capa no usa Qt ni abre conexiones: construye la dirección de consulta,
interpreta la respuesta de la API de GitHub, comprueba la integridad del
instalador ya descargado y compone la orden de instalación. La transferencia la
realiza la interfaz con ``QNetworkAccessManager``, para que el bucle de eventos
nunca quede bloqueado durante la descarga de más de cien megabytes.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

import config
from models.actualizacion import LONGITUD_SHA256, InfoActualizacion

logger = logging.getLogger(__name__)

EXTENSION_INSTALADOR = ".exe"
PREFIJO_INSTALADOR = "MisFinanzas_Setup"
PREFIJO_RESUMEN = "sha256:"


class ErrorActualizacion(Exception):
    """Falla controlada del proceso de actualización."""


class ActualizacionesNoConfiguradas(ErrorActualizacion):
    """Todavía no se ha declarado el repositorio de actualizaciones."""


# =========================================================================
# Origen de las actualizaciones
# =========================================================================


def repositorio() -> str:
    """Repositorio declarado, en formato ``usuario/repositorio``."""

    return (config.REPOSITORIO_ACTUALIZACIONES or "").strip()


def disponible() -> bool:
    """Indica si este despliegue puede buscar actualizaciones.

    Android queda excluido: allí la actualización consiste en instalar un APK
    nuevo y ninguna aplicación puede reemplazarse a sí misma sin la intervención
    del sistema.
    """

    return not config.ES_ANDROID and bool(repositorio())


def url_consulta() -> str:
    """Dirección de la última publicación del repositorio."""

    if not repositorio():
        raise ActualizacionesNoConfiguradas(
            "La búsqueda de actualizaciones está desactivada porque no se ha "
            "declarado el repositorio en config.REPOSITORIO_ACTUALIZACIONES."
        )

    return config.URL_ULTIMA_RELEASE.format(repositorio=repositorio())


def cabeceras() -> dict[str, str]:
    """Cabeceras que exige la API de GitHub.

    GitHub rechaza con el código 403 toda petición sin ``User-Agent``.
    """

    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": config.VERSION_API_GITHUB,
        "User-Agent": f"MisFinanzas/{config.VERSION}",
    }


# =========================================================================
# Interpretación de la publicación
# =========================================================================


def interpretar_release(datos: object) -> InfoActualizacion:
    """Extrae la información de actualización de una publicación de GitHub."""

    if not isinstance(datos, dict):
        raise ErrorActualizacion(
            "El servidor respondió con un formato que no corresponde a una "
            "publicación de GitHub."
        )

    if datos.get("draft"):
        raise ErrorActualizacion(
            "La última publicación del repositorio está marcada como borrador."
        )

    adjunto = _seleccionar_instalador(datos.get("assets"))

    if adjunto is None:
        raise ErrorActualizacion(
            "La última publicación no incluye ningún instalador .exe."
        )

    version = str(datos.get("tag_name") or datos.get("name") or "").strip()

    if not version:
        raise ErrorActualizacion(
            "La última publicación no declara una etiqueta de versión."
        )

    return InfoActualizacion(
        version=version,
        url_descarga=str(adjunto.get("browser_download_url") or ""),
        nombre_instalador=str(adjunto.get("name") or ""),
        sha256=resumen_de_adjunto(adjunto),
        tamano=_entero(adjunto.get("size")),
        notas=str(datos.get("body") or ""),
        publicada=str(datos.get("published_at") or ""),
        direccion_publicacion=str(datos.get("html_url") or ""),
    )


def resumen_de_adjunto(adjunto: dict) -> str:
    """Normaliza el campo ``digest`` del adjunto a hexadecimal minúscula."""

    resumen = str(adjunto.get("digest") or "").strip().lower()

    if resumen.startswith(PREFIJO_RESUMEN):
        resumen = resumen[len(PREFIJO_RESUMEN):]

    if len(resumen) != LONGITUD_SHA256:
        return ""

    return resumen


def _seleccionar_instalador(adjuntos: object) -> dict | None:
    """Elige el instalador de entre los adjuntos de la publicación.

    Se prefiere el nombre convenido por el proyecto y, si no aparece, el primer
    ejecutable publicado: el repositorio solo aloja esta aplicación, de modo que
    un renombrado del instalador no debe dejar sin actualizaciones al usuario.
    """

    if not isinstance(adjuntos, list):
        return None

    candidatos = [
        adjunto
        for adjunto in adjuntos
        if isinstance(adjunto, dict)
        and str(adjunto.get("name") or "")
        .lower()
        .endswith(EXTENSION_INSTALADOR)
    ]

    if not candidatos:
        return None

    for candidato in candidatos:
        nombre = str(candidato.get("name") or "").lower()

        if nombre.startswith(PREFIJO_INSTALADOR.lower()):
            return candidato

    return candidatos[0]


def _entero(valor: object) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def version_local() -> str:
    """Versión instalada de la aplicación."""

    return config.VERSION


# =========================================================================
# Descarga e integridad
# =========================================================================


def ruta_descarga(info: InfoActualizacion) -> Path:
    """Destino del instalador descargado."""

    nombre = info.nombre_instalador or (
        f"{PREFIJO_INSTALADOR}_{info.version}{EXTENSION_INSTALADOR}"
    )

    return config.DIRECTORIO_ACTUALIZACIONES / nombre


class VerificadorDescarga:
    """Acumula el resumen SHA-256 mientras llega la descarga.

    Verificar de forma incremental evita una segunda lectura del instalador
    completo —más de cien megabytes— una vez descargado, y concentra en esta
    capa la política de integridad, que la interfaz se limita a invocar.
    """

    def __init__(self, info: InfoActualizacion) -> None:
        self._info = info
        self._resumen = hashlib.sha256()

    def agregar(self, datos: bytes) -> None:
        self._resumen.update(datos)

    def comprobar(self) -> None:
        """Confirma que lo recibido coincide con lo publicado."""

        if not self._info.verificable:
            raise ErrorActualizacion(
                "La publicación no declara el resumen SHA-256 del instalador, "
                "así que no es posible comprobar que la descarga sea íntegra."
            )

        if self._resumen.hexdigest() != self._info.sha256:
            raise ErrorActualizacion(
                "El instalador descargado no coincide con el resumen publicado. "
                "Se descartó el archivo por seguridad."
            )

        logger.info("Instalador verificado: %s", self._info.nombre_instalador)


# =========================================================================
# Aplicación de la actualización
# =========================================================================


def puede_instalarse() -> bool:
    """Indica si la aplicación en curso puede reemplazarse a sí misma."""

    return config.ES_APLICACION_INSTALADA and config.RUTA_EJECUTABLE is not None


def orden_instalacion(ruta: Path) -> list[str]:
    """Compone la orden que instala en silencio y reabre la aplicación.

    El instalador se ejecuta en modo silencioso y con el cierre de la aplicación
    en curso habilitado; al terminar, la misma orden vuelve a abrirla. Se usa
    ``cmd`` como intérprete porque necesita encadenar ambos pasos y esperar a que
    el primero concluya, algo que no puede hacerse con una única llamada.
    """

    if not puede_instalarse():
        raise ErrorActualizacion(
            "Solo la aplicación instalada puede actualizarse a sí misma. "
            "Ejecutando desde el código fuente, descarga el instalador y "
            "ábrelo manualmente."
        )

    pasos = [f'"{ruta}" /SILENT /NORESTART /CLOSEAPPLICATIONS']

    if config.RUTA_EJECUTABLE is not None:
        pasos.append(f'start "" "{config.RUTA_EJECUTABLE}"')

    return ["cmd", "/c", " && ".join(pasos)]


def aplicar(ruta: Path) -> None:
    """Lanza el instalador verificado en modo silencioso."""

    orden = orden_instalacion(ruta)

    subprocess.Popen(
        orden,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )

    logger.info("Instalación iniciada desde %s", ruta.name)
