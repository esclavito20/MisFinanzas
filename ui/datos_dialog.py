"""Acciones de exportación e importación de datos.

No define ventanas propias: cada operación se reduce a elegir un archivo y
confirmar, así que se apoya en ``QFileDialog`` y en los cuadros de mensaje de Qt.
La lógica de formato y escritura vive en :mod:`services.datos_service`; aquí solo
se recoge la intención del usuario y se le informa del resultado.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from models.paquete_datos import ResumenDatos
from services import datos_service

logger = logging.getLogger(__name__)

FILTRO_JSON = "Datos de Mis Finanzas (*.json)"
EXTENSION = ".json"


def exportar(parent) -> bool:
    """Pide el destino, escribe todos los datos e informa del resultado."""

    destino, _ = QFileDialog.getSaveFileName(
        parent,
        "Exportar todos los datos",
        str(Path.home() / datos_service.nombre_sugerido()),
        FILTRO_JSON,
    )

    if not destino:
        return False

    ruta = Path(destino)

    if ruta.suffix.lower() != EXTENSION:
        ruta = ruta.with_suffix(EXTENSION)

    try:
        resultado = datos_service.exportar(ruta)
    except datos_service.ErrorDatos as error:
        logger.warning("Exportación rechazada: %s", error)
        QMessageBox.critical(parent, "No se pudo exportar", str(error))
        return False

    QMessageBox.information(
        parent,
        "Datos exportados",
        _detalle_exportacion(resultado),
    )

    return True


def importar(parent) -> bool:
    """Pide el archivo, avisa de lo que se reemplazará y aplica la importación."""

    origen, _ = QFileDialog.getOpenFileName(
        parent,
        "Importar datos",
        str(Path.home()),
        FILTRO_JSON,
    )

    if not origen:
        return False

    try:
        paquete = datos_service.leer_paquete(Path(origen))
    except datos_service.ErrorDatos as error:
        logger.warning("Importación rechazada: %s", error)
        QMessageBox.critical(parent, "Archivo no válido", str(error))
        return False

    respuesta = QMessageBox.warning(
        parent,
        "Reemplazar los datos actuales",
        _aviso_de_reemplazo(paquete.resumen),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )

    if respuesta != QMessageBox.StandardButton.Yes:
        return False

    try:
        resultado = datos_service.importar(paquete)
    except datos_service.ErrorDatos as error:
        logger.warning("Importación no aplicada: %s", error)
        QMessageBox.critical(parent, "No se pudo importar", str(error))
        return False
    except Exception:
        # La transacción del servicio garantiza que la base conserva el estado
        # anterior íntegro, así que el fallo se comunica y no se propaga.
        logger.exception("Fallo inesperado al importar los datos.")
        QMessageBox.critical(
            parent,
            "No se pudo importar",
            "La importación falló y se revirtió por completo: tus datos siguen "
            "como estaban. Revisa el registro de la aplicación para ver el "
            "detalle.",
        )
        return False

    QMessageBox.information(
        parent,
        "Datos importados",
        _detalle_importacion(resultado),
    )

    return True


# =========================================================================
# Mensajes
# =========================================================================


def _detalle_exportacion(resultado) -> str:
    partes = [
        f"Se exportaron {resultado.resumen.total} registros.",
        "",
        resultado.resumen.detalle(),
        "",
        "Archivo de datos:",
        str(resultado.ruta_json),
    ]

    if resultado.rutas_csv:
        partes += [
            "",
            f"Hojas de cálculo ({len(resultado.rutas_csv)} archivos):",
            str(resultado.rutas_csv[0].parent),
        ]

    return "\n".join(partes)


def _aviso_de_reemplazo(resumen: ResumenDatos) -> str:
    procedencia = resumen.version_aplicacion or "versión desconocida"
    momento = resumen.exportado_en or "fecha desconocida"

    return "\n".join(
        [
            "Se van a reemplazar TODOS los datos actuales por los del archivo.",
            "Esta acción no se puede deshacer, aunque antes de aplicarla se "
            "creará un respaldo de los datos actuales.",
            "",
            f"El archivo contiene {resumen.total} registros "
            f"(exportado el {momento} con la versión {procedencia}):",
            "",
            resumen.detalle(),
            "",
            "¿Reemplazar los datos actuales?",
        ]
    )


def _detalle_importacion(resultado) -> str:
    partes = [
        f"Se importaron {resultado.resumen.total} registros.",
        "",
        resultado.resumen.detalle(),
    ]

    if resultado.ruta_respaldo is not None:
        partes += [
            "",
            "Respaldo de los datos anteriores:",
            str(resultado.ruta_respaldo),
        ]
    else:
        partes += [
            "",
            "Aviso: no se pudo crear el respaldo previo de los datos "
            "anteriores.",
        ]

    return "\n".join(partes)
