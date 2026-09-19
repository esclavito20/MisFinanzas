"""Base de los formularios de alta.

Los cinco diálogos de registro —movimiento, deuda, abono, suscripción e
inversión— repetían el mismo esqueleto: márgenes y espaciado, un
``QFormLayout`` para los campos, una botonera con Cancelar y Guardar, la hoja
de estilo del conjunto y la traducción de los fallos de persistencia a avisos.
Aquí vive una sola vez.

Las clases derivadas conservan el control de su contenido: declaran sus campos,
deciden en qué punto del diálogo aparece el formulario (hay formularios
precedidos de rótulos informativos y seguidos de cálculos en vivo) y aportan el
guardado concreto.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ui import tema

logger = logging.getLogger(__name__)

# Geometría común: el margen interior, la separación entre bloques del diálogo
# y la de cada fila de campos.
MARGEN_DIALOGO = 25
ESPACIADO_DIALOGO = 15
ESPACIADO_FORMULARIO = 12

ANCHO_DIALOGO = 450
RELLENO_BOTON_GUARDAR = "9px 15px"


class DialogoFormulario(QDialog):
    """Esqueleto común de los formularios de alta."""

    # Ancho preferido del cuadro; las clases derivadas lo ajustan a su
    # contenido concreto.
    ANCHO = ANCHO_DIALOGO

    def __init__(self, titulo: str, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle(titulo)
        self.setFixedWidth(tema.ancho_dialogo(self.ANCHO))

        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(
            MARGEN_DIALOGO,
            MARGEN_DIALOGO,
            MARGEN_DIALOGO,
            MARGEN_DIALOGO,
        )
        self.layout_principal.setSpacing(ESPACIADO_DIALOGO)

        self.formulario = QFormLayout()
        self.formulario.setSpacing(ESPACIADO_FORMULARIO)

    # ======================================================
    # CONSTRUCCIÓN
    # ======================================================

    def agregar_titulo(self, texto: str) -> None:
        """Rótulo destacado del registro sobre el que se opera."""

        titulo = QLabel(texto)
        titulo.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {tema.TEXTO_TITULO};"
        )
        self.layout_principal.addWidget(titulo)

    def agregar_formulario(self) -> None:
        """Coloca los campos en el punto del diálogo que decide la clase derivada."""

        self.layout_principal.addLayout(self.formulario)

    def agregar_botonera(
        self,
        texto_guardar: str,
        accion: Callable[[], None],
    ) -> None:
        """Añade al pie la cancelación y la acción de guardado."""

        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.setStyleSheet(tema.estilo_boton_secundario())
        boton_cancelar.clicked.connect(self.reject)

        boton_guardar = QPushButton(texto_guardar)
        boton_guardar.setDefault(True)
        boton_guardar.setStyleSheet(
            tema.estilo_boton_primario(RELLENO_BOTON_GUARDAR)
        )
        boton_guardar.clicked.connect(accion)

        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)
        self.layout_principal.addLayout(botones)

    def estilos_extra(self) -> str:
        """Hojas adicionales que necesita el formulario concreto."""

        return ""

    def aplicar_estilos(self) -> None:
        """Fija el estilo del cuadro una vez construidos sus controles."""

        self.setStyleSheet(tema.estilo_dialogo() + self.estilos_extra())

    # ======================================================
    # PERSISTENCIA
    # ======================================================

    def persistir(
        self,
        accion: Callable[[], None],
        descripcion: str,
        titulo_validacion: str = "Datos inválidos",
    ) -> bool:
        """Ejecuta el guardado traduciendo los fallos a avisos.

        ``descripcion`` encabeza tanto el registro del error como el aviso al
        usuario. Un ``ValueError`` es un dato rechazado —se avisa y el diálogo
        sigue abierto—; cualquier otra excepción es un fallo de persistencia.
        Devuelve verdadero cuando el guardado termina y el diálogo se acepta.
        """

        try:
            accion()
        except ValueError as error:
            QMessageBox.warning(self, titulo_validacion, str(error))
            return False
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception(descripcion)
            QMessageBox.critical(self, "Error", f"{descripcion}\n\n{error}")
            return False

        self.accept()
        return True
