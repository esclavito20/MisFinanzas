"""Base de las páginas que muestran una colección de tarjetas.

Cuatro páginas —movimientos, deudas, suscripciones e inversiones— compartían el
mismo esqueleto: área de desplazamiento, contenedor con espaciador final,
limpieza previa a cada recarga y mensaje de listado vacío. Tenerlo repetido no
solo duplicaba código: un arreglo sobre ese esqueleto debía replicarse en cada
archivo. Aquí vive una sola vez.

Las páginas derivadas conservan el control de su contenido: declaran el título y
sus acciones, añaden sus propios rótulos de resumen y construyen la tarjeta de
cada registro.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui import tema

# Espaciado del contenido de la página y entre tarjetas. Las páginas que
# necesitan otra densidad los sobrescriben.
ESPACIADO_PAGINA = 18
ESPACIADO_TARJETAS = 15
RELLENO_MENSAJE = 40


class PaginaListado(QWidget):
    """Esqueleto común de las páginas con listado desplazable."""

    ESPACIADO_PAGINA = ESPACIADO_PAGINA
    ESPACIADO_TARJETAS = ESPACIADO_TARJETAS

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        tema.preparar_pagina(self)

        margen = tema.margen_pagina()
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(margen, margen, margen, margen)
        self.layout_principal.setSpacing(self.ESPACIADO_PAGINA)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.contenedor = QWidget()
        self.listado = QVBoxLayout(self.contenedor)
        self.listado.setContentsMargins(0, 0, 0, 0)
        self.listado.setSpacing(self.ESPACIADO_TARJETAS)
        # El espaciador final absorbe el espacio libre para que las tarjetas se
        # apilen desde arriba y no se repartan por toda la altura.
        self.listado.addStretch()

        self.scroll.setWidget(self.contenedor)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def titulo_pagina(self, texto: str, accion: QWidget | None = None) -> None:
        """Añade el encabezado, que se apila cuando la pantalla es estrecha."""

        titulo = QLabel(texto)
        titulo.setStyleSheet(tema.estilo_titulo())

        if accion is None:
            self.layout_principal.addWidget(titulo)
            return

        self.layout_principal.addLayout(tema.encabezado_pagina(titulo, accion))

    def agregar_area(self) -> None:
        """Coloca el listado desplazable al final de la página."""

        self.layout_principal.addWidget(self.scroll)

    def estilos_extra(self) -> str:
        """Hojas adicionales que necesita la página concreta."""

        return ""

    def aplicar_estilos(self) -> None:
        """Fija el estilo de la página una vez construidos sus controles."""

        self.setStyleSheet(tema.estilo_pagina() + self.estilos_extra())

    # ------------------------------------------------------------------
    # Contenido
    # ------------------------------------------------------------------

    def limpiar_listado(self) -> None:
        """Retira las tarjetas previas conservando el espaciador final."""

        while self.listado.count() > 1:
            item = self.listado.takeAt(0)
            widget = item.widget()

            if widget is not None:
                # El widget se libera en el siguiente ciclo del bucle de
                # eventos; ocultarlo evita que siga pintándose mientras tanto.
                widget.hide()
                widget.deleteLater()

    def agregar_tarjeta(self, tarjeta: QWidget) -> None:
        """Inserta una tarjeta antes del espaciador final."""

        self.listado.insertWidget(self.listado.count() - 1, tarjeta)

    def mostrar_mensaje(self, texto: str) -> None:
        """Sustituye el listado por un aviso centrado."""

        mensaje = QLabel(texto)
        mensaje.setWordWrap(True)
        mensaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mensaje.setStyleSheet(
            f"color: {tema.TEXTO_TENUE}; font-size: 14px; "
            f"padding: {RELLENO_MENSAJE}px;"
        )
        self.listado.insertWidget(0, mensaje)
