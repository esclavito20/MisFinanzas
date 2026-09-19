"""Diálogo de sincronización con una carpeta compartida.

El transporte lo pone el servicio de almacenamiento del usuario: la aplicación
solo escribe y lee un archivo en la carpeta elegida. La sincronización es de un
sentido por operación y siempre explícita; el diálogo informa qué lado cambió y
deja la decisión al usuario.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services import sincronizacion_service as servicio
from services.datos_service import ErrorDatos
from ui import tema

logger = logging.getLogger(__name__)

SIN_REGISTROS = "· Sin registros"


class SincronizacionDialog(QDialog):
    """Configura la carpeta compartida y sincroniza en un sentido."""

    ANCHO = 580

    def __init__(self, parent=None):
        super().__init__(parent)

        # La ventana principal debe refrescar sus páginas cuando la recepción
        # reemplaza el contenido de la base.
        self.datos_reemplazados = False

        self.setWindowTitle("Sincronización")
        self.setFixedWidth(tema.ancho_dialogo(self.ANCHO))

        self._crear_interfaz()
        self._actualizar_estado()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)

        titulo = QLabel("☁️ Sincronización")
        titulo.setStyleSheet(tema.estilo_titulo(20))
        layout.addWidget(titulo)

        explicacion = QLabel(
            "Elige una carpeta de tu servicio de almacenamiento en la nube "
            "(Google Drive, OneDrive, Dropbox). La aplicación escribe ahí una "
            "copia de todo; ese servicio se encarga de replicarla entre tus "
            "equipos, sin credenciales ni conexión permanente."
        )
        explicacion.setWordWrap(True)
        explicacion.setStyleSheet(tema.estilo_texto_secundario(12))
        layout.addWidget(explicacion)

        self.carpeta_label = QLabel()
        self.carpeta_label.setWordWrap(True)
        self.carpeta_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.carpeta_label)

        self.estado_label = QLabel()
        self.estado_label.setWordWrap(True)
        self.estado_label.setStyleSheet(
            f"background-color: {tema.MORADO_CLARO};"
            f" color: {tema.TEXTO_TITULO};"
            " border-radius: 12px; padding: 12px; font-size: 13px;"
        )
        layout.addWidget(self.estado_label)

        layout.addWidget(self._crear_comparacion())

        self.boton_carpeta = QPushButton("📂 Elegir carpeta")
        self.boton_carpeta.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_carpeta.clicked.connect(self._elegir_carpeta)

        self.boton_enviar = QPushButton("⬆️ Enviar")
        self.boton_enviar.setStyleSheet(tema.estilo_boton_primario("10px 15px"))
        self.boton_enviar.setToolTip(
            "Publica el estado de este equipo en la carpeta compartida"
        )
        self.boton_enviar.clicked.connect(self._enviar)

        self.boton_traer = QPushButton("⬇️ Traer")
        self.boton_traer.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_traer.setToolTip(
            "Adopta la copia compartida como contenido de este equipo"
        )
        self.boton_traer.clicked.connect(self._traer)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setStyleSheet(tema.estilo_boton_secundario())
        boton_cerrar.clicked.connect(self.accept)

        layout.addLayout(
            tema.fila_de_acciones(
                self.boton_enviar,
                self.boton_carpeta,
                boton_cerrar,
                self.boton_traer,
            )
        )

        self.setStyleSheet(tema.estilo_dialogo())

    def _crear_comparacion(self) -> QFrame:
        """Contenido de cada lado, para decidir con la información a la vista."""

        tarjeta = QFrame()
        tarjeta.setStyleSheet(tema.estilo_tarjeta(12))

        layout = QHBoxLayout(tarjeta)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(18)

        self.local_label = QLabel()
        self.local_label.setWordWrap(True)
        self.local_label.setStyleSheet("font-size: 12px;")

        self.remoto_label = QLabel()
        self.remoto_label.setWordWrap(True)
        self.remoto_label.setStyleSheet("font-size: 12px;")

        layout.addWidget(self.local_label, 1)
        layout.addWidget(self.remoto_label, 1)

        return tarjeta

    # ======================================================
    # ESTADO
    # ======================================================

    def _actualizar_estado(self) -> None:
        """Refresca el diagnóstico y habilita lo que tenga sentido."""

        estado = servicio.estado()
        configuracion = estado.configuracion

        self.carpeta_label.setText(
            "<b>Carpeta:</b> "
            + (str(configuracion.carpeta) if configuracion.carpeta else "sin elegir")
            + f"<br><b>Última operación:</b> {configuracion.descripcion_sentido}"
        )

        self.estado_label.setText(estado.detalle())

        # El detalle de cada lado es texto plano con saltos de línea: en un
        # rótulo con formato enriquecido hay que traducirlos a <br>, o se
        # colapsarían en un único renglón.
        self.local_label.setText(
            "<b>Este equipo</b><br>"
            + (estado.local.detalle() or SIN_REGISTROS).replace("\n", "<br>")
        )
        self.remoto_label.setText(
            "<b>Copia compartida</b><br>"
            + (
                estado.remoto.detalle() if estado.remoto else SIN_REGISTROS
            ).replace("\n", "<br>")
        )

        self.boton_enviar.setEnabled(estado.configurada)
        self.boton_traer.setEnabled(estado.existe_remoto)

    # ======================================================
    # ACCIONES
    # ======================================================

    def _elegir_carpeta(self) -> None:
        actual = servicio.configuracion().carpeta

        elegida = QFileDialog.getExistingDirectory(
            self,
            "Elegir la carpeta compartida",
            str(actual) if actual else str(Path.home()),
        )

        if not elegida:
            return

        try:
            servicio.configurar(Path(elegida))
        except servicio.ErrorSincronizacion as error:
            QMessageBox.warning(self, "Carpeta no válida", str(error))
            return

        self._actualizar_estado()

    def _enviar(self) -> None:
        estado = servicio.estado()

        if estado.pendiente_de_recepcion:
            respuesta = QMessageBox.question(
                self,
                "La copia compartida es más reciente",
                "La copia compartida se escribió después de la última "
                "sincronización de este equipo.\n\n"
                "Si envías ahora, la reemplazarás por la de este equipo y "
                "perderás los cambios del otro.\n\n¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if respuesta != QMessageBox.StandardButton.Yes:
                return

        try:
            resultado = servicio.enviar()
        except (servicio.ErrorSincronizacion, ErrorDatos) as error:
            logger.warning("No se pudo enviar la sincronización: %s", error)
            QMessageBox.critical(self, "No se pudo enviar", str(error))
            return
        except Exception as error:  # pragma: no cover - error de E/S
            logger.exception("Fallo inesperado al enviar la sincronización.")
            QMessageBox.critical(
                self,
                "No se pudo enviar",
                f"Ocurrió un error inesperado:\n{error}",
            )
            return

        self._actualizar_estado()

        QMessageBox.information(
            self,
            "Copia publicada",
            "Se escribió la copia compartida con "
            f"{resultado.resumen.total} registro(s).\n\n"
            "Tu servicio de almacenamiento la replicará al resto de equipos.",
        )

    def _traer(self) -> None:
        respuesta = QMessageBox.question(
            self,
            "Adoptar la copia compartida",
            "Se reemplazarán TODOS los datos de este equipo por los de la "
            "copia compartida.\n\n"
            "Antes de hacerlo se crea un respaldo de seguridad.\n\n"
            "¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            resultado = servicio.traer()
        except (servicio.ErrorSincronizacion, ErrorDatos) as error:
            logger.warning("No se pudo recibir la sincronización: %s", error)
            QMessageBox.critical(self, "No se pudo traer", str(error))
            return
        except Exception as error:  # pragma: no cover - error de E/S
            logger.exception("Fallo inesperado al recibir la sincronización.")
            QMessageBox.critical(
                self,
                "No se pudo traer",
                f"Ocurrió un error inesperado:\n{error}",
            )
            return

        self.datos_reemplazados = True
        self._actualizar_estado()

        detalle = resultado.resumen.detalle()
        respaldo = (
            f"\n\nRespaldo previo:\n{resultado.ruta_respaldo}"
            if resultado.ruta_respaldo
            else ""
        )

        QMessageBox.information(
            self,
            "Datos actualizados",
            f"Se adoptó la copia compartida ({resultado.resumen.total} "
            f"registro(s)):\n\n{detalle}{respaldo}",
        )
