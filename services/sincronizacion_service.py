"""Sincronización de los datos a través de una carpeta compartida.

El transporte lo pone el servicio de almacenamiento del usuario —Google Drive,
OneDrive, Dropbox—: la aplicación se limita a escribir y leer un archivo de
intercambio en una carpeta que él elige y ese servicio la replica entre
dispositivos. No se guardan credenciales ni se depende de una API externa, y la
sincronización funciona incluso sin conexión: el archivo se replica cuando el
servicio recupere la red.

La sincronización es **explícita y de un solo sentido por operación**. No se
fusionan automáticamente dos bases: combinar fila a fila exigiría resolver
conflictos y podría duplicar o perder registros sin que el usuario lo advierta.
En su lugar se informa qué lado cambió desde la última vez y es él quien decide
la dirección.

La recepción reutiliza la importación general y hereda sus garantías: valida el
archivo completo, crea un respaldo previo y aplica el reemplazo en una única
transacción.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

import config
from models.paquete_datos import (
    ResumenDatos,
    ResultadoExportacion,
    ResultadoImportacion,
)
from services import datos_service
from services.datos_service import ErrorDatos

logger = logging.getLogger(__name__)

# Nombre fijo del archivo compartido: la carpeta es del usuario y puede contener
# cualquier otra cosa, así que la aplicación nunca elige por él.
NOMBRE_ARCHIVO = "MisFinanzas_datos.json"

SENTIDO_ENVIO = "envio"
SENTIDO_RECEPCION = "recepcion"

DESCRIPCION_SENTIDO = {
    SENTIDO_ENVIO: "última operación: envío",
    SENTIDO_RECEPCION: "última operación: recepción",
}


class ErrorSincronizacion(Exception):
    """Falla controlada de una operación de sincronización."""


@dataclass(frozen=True)
class ConfiguracionSincronizacion:
    """Carpeta compartida recordada en este equipo."""

    carpeta: Path | None = None
    # Momento de la instantánea que este equipo conoce. Si el archivo compartido
    # declara uno posterior, otra instalación escribió en él.
    ultima: str = ""
    sentido: str = ""

    @property
    def descripcion_sentido(self) -> str:
        return DESCRIPCION_SENTIDO.get(self.sentido, "sin sincronizaciones")


@dataclass(frozen=True)
class EstadoSincronizacion:
    """Diagnóstico previo a decidir en qué dirección sincronizar."""

    local: ResumenDatos
    configuracion: ConfiguracionSincronizacion
    ruta: Path | None = None
    remoto: ResumenDatos | None = None
    aviso: str = ""

    @property
    def configurada(self) -> bool:
        return self.configuracion.carpeta is not None

    @property
    def existe_remoto(self) -> bool:
        return self.remoto is not None

    @property
    def pendiente_de_recepcion(self) -> bool:
        """Indica si la copia compartida se escribió después de la última vez."""

        if self.remoto is None:
            return False

        return self.remoto.exportado_en > self.configuracion.ultima

    def detalle(self) -> str:
        """Texto legible del estado y de la dirección sugerida."""

        # Un problema con la base o con el archivo compartido es más urgente que
        # la ausencia de carpeta: se informa antes que nada.
        if self.aviso:
            return self.aviso

        if not self.configurada:
            return (
                "Sin carpeta configurada. Elige la carpeta de tu servicio de "
                "almacenamiento (por ejemplo, Google Drive) para compartir los "
                "datos entre equipos."
            )

        if not self.existe_remoto:
            return (
                "La carpeta no contiene todavía una copia compartida. Usa "
                "«Enviar» para crear la primera."
            )

        if self.pendiente_de_recepcion:
            return (
                "La copia compartida es más reciente que este equipo. Usa "
                "«Traer» para adoptarla; hacerlo reemplaza los datos locales "
                "(se crea un respaldo antes)."
            )

        return (
            "No hay cambios pendientes de otros equipos. Usa «Enviar» para "
            "publicar el estado de este equipo."
        )


# =========================================================================
# Configuración de la carpeta compartida
# =========================================================================


def configuracion() -> ConfiguracionSincronizacion:
    """Lee la carpeta compartida recordada en este equipo."""

    try:
        documento = json.loads(
            config.RUTA_CONFIGURACION_SYNC.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return ConfiguracionSincronizacion()

    if not isinstance(documento, dict):
        return ConfiguracionSincronizacion()

    carpeta = documento.get("carpeta")

    return ConfiguracionSincronizacion(
        carpeta=Path(carpeta) if isinstance(carpeta, str) and carpeta else None,
        ultima=str(documento.get("ultima") or ""),
        sentido=str(documento.get("sentido") or ""),
    )


def _guardar(configuracion_nueva: ConfiguracionSincronizacion) -> None:
    documento = {
        "carpeta": (
            str(configuracion_nueva.carpeta)
            if configuracion_nueva.carpeta
            else ""
        ),
        "ultima": configuracion_nueva.ultima,
        "sentido": configuracion_nueva.sentido,
    }

    ruta = config.RUTA_CONFIGURACION_SYNC

    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(documento, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as error:
        raise ErrorSincronizacion(
            f"No se pudo guardar la configuración de sincronización: {error}"
        ) from error


def configurar(carpeta: Path) -> ConfiguracionSincronizacion:
    """Fija la carpeta compartida y olvida el estado de la sincronización previa.

    La carpeta se crea si no existe y se comprueba que admita escritura: elegir
    una ruta inaccesible solo se detectaría al enviar, con el trabajo ya hecho.
    """

    destino = Path(carpeta).expanduser()

    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ErrorSincronizacion(
            f"No se pudo usar la carpeta indicada: {error}"
        ) from error

    if not os.access(destino, os.W_OK):
        raise ErrorSincronizacion(
            "La carpeta indicada no admite escritura."
        )

    actual = configuracion()

    # Reelegir la misma carpeta no reinicia el estado: si se olvidara qué copia
    # conoce este equipo, la aplicación anunciaría cambios remotos inexistentes.
    if actual.carpeta is not None and actual.carpeta == destino:
        _guardar(actual)
        return actual

    nueva = ConfiguracionSincronizacion(carpeta=destino)
    _guardar(nueva)

    logger.info("Carpeta de sincronización establecida en %s", destino)

    return nueva


def desactivar() -> None:
    """Olvida la carpeta compartida. Los archivos ya escritos no se tocan."""

    _guardar(ConfiguracionSincronizacion())


# =========================================================================
# Estado y operaciones
# =========================================================================


def ruta_archivo() -> Path | None:
    """Ruta del archivo compartido, o ``None`` si no hay carpeta configurada."""

    carpeta = configuracion().carpeta

    return carpeta / NOMBRE_ARCHIVO if carpeta else None


def estado() -> EstadoSincronizacion:
    """Compara el contenido local con el archivo compartido.

    La consulta no modifica nada y nunca falla: si la base no se puede leer o el
    archivo compartido está dañado o es de otro formato, se informa en ``aviso``
    y se deja que el usuario decida.
    """

    configuracion_actual = configuracion()

    try:
        local = datos_service.resumen_actual()
    except ErrorDatos as error:
        return EstadoSincronizacion(
            local=ResumenDatos(conteos={}),
            configuracion=configuracion_actual,
            aviso=f"No se pudo leer la base de datos local: {error}",
        )

    if configuracion_actual.carpeta is None:
        return EstadoSincronizacion(
            local=local,
            configuracion=configuracion_actual,
        )

    ruta = configuracion_actual.carpeta / NOMBRE_ARCHIVO

    if not ruta.exists():
        return EstadoSincronizacion(
            local=local,
            configuracion=configuracion_actual,
            ruta=ruta,
        )

    try:
        remoto = datos_service.leer_paquete(ruta).resumen
    except ErrorDatos as error:
        return EstadoSincronizacion(
            local=local,
            configuracion=configuracion_actual,
            ruta=ruta,
            aviso=(
                f"El archivo compartido no se puede usar: {error} "
                "Usa «Enviar» para reemplazarlo por el estado de este equipo."
            ),
        )

    return EstadoSincronizacion(
        local=local,
        configuracion=configuracion_actual,
        ruta=ruta,
        remoto=remoto,
    )


def enviar() -> ResultadoExportacion:
    """Publica el estado de este equipo en la carpeta compartida.

    Se escribe un único archivo: las hojas de cálculo de la exportación manual
    no aportan nada aquí y multiplicarían los archivos que el servicio de
    almacenamiento debe replicar.
    """

    configuracion_actual = configuracion()

    if configuracion_actual.carpeta is None:
        raise ErrorSincronizacion(
            "No hay una carpeta de sincronización configurada."
        )

    resultado = datos_service.exportar(
        configuracion_actual.carpeta / NOMBRE_ARCHIVO,
        con_csv=False,
    )

    _guardar(
        replace(
            configuracion_actual,
            ultima=resultado.resumen.exportado_en,
            sentido=SENTIDO_ENVIO,
        )
    )

    logger.info(
        "Sincronización enviada a %s (%s registros)",
        resultado.ruta_json,
        resultado.resumen.total,
    )

    return resultado


def traer() -> ResultadoImportacion:
    """Adopta la copia compartida como contenido de este equipo.

    Reemplaza todos los datos locales; la importación crea antes un respaldo
    manual, de modo que la operación siempre es reversible.
    """

    configuracion_actual = configuracion()

    if configuracion_actual.carpeta is None:
        raise ErrorSincronizacion(
            "No hay una carpeta de sincronización configurada."
        )

    ruta = configuracion_actual.carpeta / NOMBRE_ARCHIVO

    if not ruta.exists():
        raise ErrorSincronizacion(
            "La carpeta no contiene todavía una copia compartida."
        )

    paquete = datos_service.leer_paquete(ruta)
    resultado = datos_service.importar(paquete)

    _guardar(
        replace(
            configuracion_actual,
            ultima=paquete.resumen.exportado_en,
            sentido=SENTIDO_RECEPCION,
        )
    )

    logger.info(
        "Sincronización recibida desde %s (%s registros)",
        ruta,
        paquete.resumen.total,
    )

    return resultado
