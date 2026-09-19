"""Punto de entrada de Mis Finanzas.

Composición de la aplicación: configuración de logs, preparación del esquema de
datos y arranque de la interfaz. La inicialización se ejecuta dentro de
``main`` para que el módulo pueda importarse sin efectos secundarios.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

import config
from database.esquema import inicializar_base_de_datos
from database.semilla import crear_categorias_iniciales
from ui import tema
from ui.actualizacion_dialog import verificar_al_arrancar
from ui.ventana_principal import VentanaPrincipal

logger = logging.getLogger(__name__)


def main() -> int:
    """Inicia la aplicación y devuelve el código de salida."""

    config.configurar_logging()
    logger.info("Iniciando %s %s", config.NOMBRE_APP, config.VERSION)

    try:
        inicializar_base_de_datos()
        crear_categorias_iniciales()
    except Exception:
        logger.exception("No fue posible preparar la base de datos.")
        raise

    aplicacion = QApplication(sys.argv)
    aplicacion.setApplicationName(config.NOMBRE_APP)
    aplicacion.setApplicationDisplayName(config.NOMBRE_APP)
    aplicacion.setApplicationVersion(config.VERSION)

    # El tema se fija antes de construir cualquier ventana: de lo contrario el
    # modo oscuro del sistema deja sin pintar las superficies de la interfaz.
    tema.aplicar_tema(aplicacion)

    if config.RUTA_ICONO.exists():
        aplicacion.setWindowIcon(QIcon(str(config.RUTA_ICONO)))

    ventana = VentanaPrincipal()
    ventana.show()

    # La comprobación de actualizaciones se aplaza para no competir con la carga
    # inicial. Si no hay red o no hay versiones nuevas, no interrumpe al usuario.
    QTimer.singleShot(
        config.DEMORA_COMPROBACION_MS,
        lambda: verificar_al_arrancar(ventana),
    )

    return aplicacion.exec()


if __name__ == "__main__":
    sys.exit(main())
