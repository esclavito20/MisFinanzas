"""Diálogo de configuración: información de la aplicación y respaldos."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

import config
from database import respaldo
from services import actualizaciones_service as servicio_actualizaciones
from services import sincronizacion_service as servicio_sincronizacion
from ui import datos_dialog, tema
from ui.actualizacion_dialog import ActualizacionDialog
from ui.sincronizacion_dialog import SincronizacionDialog

logger = logging.getLogger(__name__)


class ConfiguracionDialog(QDialog):
    """Información de la aplicación y utilidades de mantenimiento."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # La ventana principal debe refrescar sus páginas cuando una
        # importación reemplaza el contenido de la base.
        self.datos_reemplazados = False

        self.setWindowTitle("Configuración")
        self.setFixedWidth(tema.ancho_dialogo(520))

        self._crear_interfaz()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)

        titulo = QLabel("⚙️ Configuración")
        titulo.setStyleSheet(tema.estilo_titulo(20))
        layout.addWidget(titulo)

        for etiqueta, valor in (
            ("Versión", config.VERSION),
            ("Carpeta de datos", str(config.DIRECTORIO_DATOS)),
            ("Respaldos automáticos", str(config.DIRECTORIO_RESPALDOS)),
            ("Respaldos manuales", str(config.DIRECTORIO_RESPALDOS_MANUALES)),
            ("Actualizaciones", self._estado_de_actualizaciones()),
        ):
            layout.addWidget(self._crear_dato(etiqueta, valor))

        self.sincronizacion_label = self._crear_dato(
            "Sincronización",
            self._estado_de_sincronizacion(),
        )
        layout.addWidget(self.sincronizacion_label)

        layout.addWidget(self._crear_separador())

        descripcion = QLabel(
            "Los respaldos se crean con la API de copia de SQLite, por lo que "
            "la copia es consistente aunque la aplicación esté en uso."
        )
        descripcion.setWordWrap(True)
        descripcion.setStyleSheet(
            f"color: {tema.TEXTO_SECUNDARIO}; font-size: 12px;"
        )
        layout.addWidget(descripcion)

        boton_respaldo = QPushButton("💾 Crear respaldo ahora")
        boton_respaldo.setStyleSheet(tema.estilo_boton_primario("10px 15px"))
        boton_respaldo.clicked.connect(self._crear_respaldo)

        boton_carpeta = QPushButton("📂 Abrir carpeta de datos")
        boton_carpeta.setStyleSheet(tema.estilo_boton_secundario())
        boton_carpeta.clicked.connect(self._abrir_carpeta)

        self.boton_actualizaciones = QPushButton("⬆️ Buscar actualizaciones")
        self.boton_actualizaciones.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_actualizaciones.clicked.connect(self._buscar_actualizaciones)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setStyleSheet(tema.estilo_boton_secundario())
        boton_cerrar.clicked.connect(self.accept)

        layout.addLayout(
            tema.fila_de_acciones(
                boton_respaldo,
                boton_carpeta,
                self.boton_actualizaciones,
            )
        )

        layout.addWidget(self._crear_separador())

        sobre_datos = QLabel(
            "Exportar genera un archivo de intercambio con todos los registros y "
            "una hoja de cálculo por tabla. Importar reemplaza los datos "
            "actuales por los de ese archivo, tras crear un respaldo previo."
        )
        sobre_datos.setWordWrap(True)
        sobre_datos.setStyleSheet(
            f"color: {tema.TEXTO_SECUNDARIO}; font-size: 12px;"
        )
        layout.addWidget(sobre_datos)

        self.boton_exportar = QPushButton("📤 Exportar datos")
        self.boton_exportar.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_exportar.clicked.connect(self._exportar_datos)

        self.boton_importar = QPushButton("📥 Importar datos")
        self.boton_importar.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_importar.clicked.connect(self._importar_datos)

        self.boton_sincronizar = QPushButton("☁️ Sincronización")
        self.boton_sincronizar.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_sincronizar.setToolTip(
            "Compartir los datos entre equipos a través de una carpeta en la nube"
        )
        self.boton_sincronizar.clicked.connect(self._sincronizar)

        layout.addLayout(
            tema.fila_de_acciones(
                self.boton_exportar,
                self.boton_importar,
                self.boton_sincronizar,
            )
        )

        cierre = QHBoxLayout()
        cierre.addStretch()
        cierre.addWidget(boton_cerrar)
        layout.addLayout(cierre)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {tema.FONDO};
            }}

            QLabel {{
                color: {tema.TEXTO};
                background-color: transparent;
            }}
            """
        )

    def _texto_dato(self, etiqueta: str, valor: str) -> str:
        return f"<b>{etiqueta}:</b> {valor}"

    def _crear_dato(self, etiqueta: str, valor: str) -> QLabel:
        texto = QLabel(self._texto_dato(etiqueta, valor))
        texto.setTextFormat(Qt.TextFormat.RichText)
        texto.setWordWrap(True)
        texto.setStyleSheet("font-size: 12px;")

        return texto

    def _crear_separador(self) -> QLabel:
        linea = QLabel()
        linea.setFixedHeight(1)
        linea.setStyleSheet(
            f"background-color: {tema.MORADO_BORDE};"
        )

        return linea

    def _estado_de_actualizaciones(self) -> str:
        """Describe el origen configurado para las versiones nuevas."""

        if config.ES_ANDROID:
            return "no disponibles en Android: se actualiza instalando el APK"

        repositorio = servicio_actualizaciones.repositorio()

        if not repositorio:
            return "sin configurar: falta declarar el repositorio en config.py"

        return f"activadas desde {repositorio}"

    def _estado_de_sincronizacion(self) -> str:
        """Describe la carpeta compartida configurada, si la hay."""

        carpeta = servicio_sincronizacion.configuracion().carpeta

        if carpeta is None:
            return "sin configurar (elige una carpeta de tu servicio en la nube)"

        return str(carpeta)

    # ======================================================
    # ACCIONES
    # ======================================================

    def _crear_respaldo(self) -> None:
        try:
            destino = respaldo.crear_respaldo_manual()
        except Exception as error:  # pragma: no cover - error de E/S
            logger.exception("No se pudo crear el respaldo manual.")
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo crear el respaldo.\n\n{error}",
            )
            return

        if destino is None:
            QMessageBox.warning(
                self,
                "Sin respaldo",
                "No se pudo crear el respaldo. Verifica que la base de "
                "datos exista y que la carpeta sea escribible.",
            )
            return

        QMessageBox.information(
            self,
            "Respaldo creado",
            f"Se creó una copia de seguridad en:\n{destino}",
        )

    def _abrir_carpeta(self) -> None:
        config.asegurar_directorios()

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(config.DIRECTORIO_DATOS))
        )

    def _buscar_actualizaciones(self) -> None:
        ActualizacionDialog(self).exec()

    def _exportar_datos(self) -> None:
        datos_dialog.exportar(self)

    def _importar_datos(self) -> None:
        if datos_dialog.importar(self):
            self.datos_reemplazados = True

    def _sincronizar(self) -> None:
        dialogo = SincronizacionDialog(self)
        dialogo.exec()

        if dialogo.datos_reemplazados:
            self.datos_reemplazados = True

        self.sincronizacion_label.setText(
            self._texto_dato(
                "Sincronización",
                self._estado_de_sincronizacion(),
            )
        )
