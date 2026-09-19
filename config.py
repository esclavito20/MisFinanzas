"""Configuración central del proyecto.

Única fuente de verdad para las rutas de datos, la versión de la aplicación y
el registro de eventos, tanto en ejecución desde código fuente como en la
aplicación de escritorio empaquetada con PyInstaller y en el despliegue de
Android generado con python-for-android.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOMBRE_APP = "Mis Finanzas"
IDENTIFICADOR_APP = "MisFinanzas"

# Retención de los respaldos automáticos creados antes de inicializar o migrar.
MAX_RESPALDOS_AUTOMATICOS = 10

BASE_DIR = Path(__file__).resolve().parent
ES_APLICACION_INSTALADA = bool(getattr(sys, "frozen", False))

# El bootstrap de python-for-android define estas variables y expone en
# ANDROID_PRIVATE el almacenamiento privado de la aplicación, único punto
# escribible garantizado en el dispositivo.
ES_ANDROID = sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ

# Permite verificar el diseño compacto en escritorio sin desplegar al teléfono.
VARIABLE_MODO_MOVIL = "MIS_FINANZAS_MOVIL"


def es_movil() -> bool:
    """Indica si la interfaz debe usar el diseño compacto.

    Se resuelve de forma perezosa para que las pruebas puedan forzarlo con
    ``MIS_FINANZAS_MOVIL=1`` en lugar de depender del dispositivo.
    """

    if os.environ.get(VARIABLE_MODO_MOVIL) == "1":
        return True

    return ES_ANDROID


def _directorio_de_datos() -> Path:
    """Resuelve el directorio escribible de datos según la plataforma.

    En Android el paquete desplegado es de solo lectura: los datos deben vivir
    en el almacenamiento privado de la aplicación. En una instalación de
    escritorio se usa el perfil del usuario para no depender de permisos dentro
    de Archivos de programa, y en desarrollo se mantiene la carpeta del
    proyecto.
    """

    if ES_ANDROID:
        privado = os.environ.get("ANDROID_PRIVATE") or os.environ.get(
            "ANDROID_APP_PATH"
        )

        if privado:
            return Path(privado) / "data"

        return Path.home() / IDENTIFICADOR_APP / "data"

    if ES_APLICACION_INSTALADA:
        perfil_usuario = Path(
            os.environ.get(
                "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
            )
        )
        return perfil_usuario / IDENTIFICADOR_APP / "data"

    return BASE_DIR / "data"


DIRECTORIO_DATOS = _directorio_de_datos()

DIRECTORIO_RESPALDOS = DIRECTORIO_DATOS.parent / "backups"
DIRECTORIO_RESPALDOS_MANUALES = DIRECTORIO_DATOS.parent / "backups_manual"
DIRECTORIO_LOGS = DIRECTORIO_DATOS.parent / "logs"

RUTA_BASE_DATOS = DIRECTORIO_DATOS / "finanzas.db"
RUTA_LOG = DIRECTORIO_LOGS / "mis_finanzas.log"

# ---------------------------------------------------------------------------
# Actualizaciones
# ---------------------------------------------------------------------------

# Repositorio público de GitHub del que se descargan las versiones nuevas, con
# el formato "usuario/repositorio". Debe ser accesible sin credenciales: la
# aplicación consulta la API de forma anónima, y un repositorio privado
# responde 404 a cualquier cliente externo. Dejarlo vacío desactiva por completo
# la búsqueda de actualizaciones.
REPOSITORIO_ACTUALIZACIONES = "esclavito20/MisFinanzas"

URL_ULTIMA_RELEASE = "https://api.github.com/repos/{repositorio}/releases/latest"
VERSION_API_GITHUB = "2022-11-28"

# Límites de espera de red. La descarga es mucho más lenta que la consulta
# porque el instalador pesa más de cien megabytes.
TIEMPO_ESPERA_CONSULTA_MS = 15_000
TIEMPO_ESPERA_DESCARGA_MS = 600_000

# Retardo de la comprobación automática posterior al arranque: se espera a que
# la ventana esté pintada para no competir con la carga inicial.
DEMORA_COMPROBACION_MS = 6_000

DIRECTORIO_ACTUALIZACIONES = DIRECTORIO_DATOS.parent / "updates"

# Ruta del ejecutable en curso. Solo existe cuando la aplicación está empaquetada,
# que es el único caso en el que puede reemplazarse a sí misma.
RUTA_EJECUTABLE = Path(sys.executable) if ES_APLICACION_INSTALADA else None


# ---------------------------------------------------------------------------
# Sincronización
# ---------------------------------------------------------------------------

# Archivo donde se recuerda la carpeta compartida elegida por el usuario y el
# momento de la última sincronización. Vive junto al directorio de datos y no
# dentro de la base: es una preferencia de cada equipo, no un dato financiero, y
# por tanto no debe viajar en los archivos de intercambio.
RUTA_CONFIGURACION_SYNC = DIRECTORIO_DATOS.parent / "sincronizacion.json"


def ruta_recurso(ruta_relativa: str | Path) -> Path:
    """Devuelve la ruta de un recurso empaquetado (iconos, versión).

    En el ejecutable de escritorio los recursos se extraen en ``_MEIPASS``; en
    Android el código se despliega junto a ellos en el directorio de la
    aplicación.
    """

    base = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    return base / ruta_relativa


def _leer_version() -> str:
    try:
        return (
            ruta_recurso("VERSION.txt")
            .read_text(encoding="utf-8")
            .strip()
            or "0.0.0"
        )
    except OSError:
        return "0.0.0"


VERSION = _leer_version()
RUTA_ICONO = ruta_recurso(Path("assets") / "MisFinanzas.ico")


def asegurar_directorios() -> None:
    """Garantiza la existencia del directorio de datos."""

    DIRECTORIO_DATOS.mkdir(parents=True, exist_ok=True)


def configurar_logging() -> None:
    """Redirige los eventos de la aplicación a un archivo de log rotativo.

    La aplicación empaquetada no tiene consola, por lo que el archivo de log es
    el único canal de diagnóstico disponible para el usuario final.
    """

    if logging.getLogger().handlers:
        return

    try:
        DIRECTORIO_LOGS.mkdir(parents=True, exist_ok=True)
        manejador = RotatingFileHandler(
            RUTA_LOG,
            maxBytes=512_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        # La ausencia de logs no debe impedir el arranque de la aplicación.
        return

    manejador.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
    )
    logging.basicConfig(level=logging.INFO, handlers=[manejador])
