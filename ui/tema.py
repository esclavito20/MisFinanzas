"""Tema visual centralizado: paleta, tipografías y hojas de estilo comunes.

Evita repetir literales de color y bloques QSS en cada widget, de modo que un
cambio de identidad visual se aplique desde un único punto.

La aplicación fija su propia paleta clara y su estilo en
:func:`aplicar_tema`: sin esa fijación, un sistema operativo configurado en
modo oscuro impone la paleta oscura de ``windows11`` y deja en negro toda
superficie que ningún widget pinte explícitamente.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)

import config

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

MORADO = "#7652B5"
MORADO_HOVER = "#6845A4"
MORADO_ACTIVO = "#59398F"
MORADO_DESHABILITADO = "#C9BEE0"
MORADO_CLARO = "#E9DEFF"
MORADO_BORDE = "#DDD4EA"

LATERAL = "#F3EEFF"
FONDO = "#FAF9FC"
TARJETA = "#FFFFFF"
TARJETA_SUAVE = "#FAF9FC"

TEXTO = "#302A38"
TEXTO_TITULO = "#4D3B67"
TEXTO_ETIQUETA = "#756A80"
TEXTO_SECUNDARIO = "#81768D"
TEXTO_TENUE = "#8A808F"
TEXTO_CAMPO = "#3E3547"
TEXTO_FORMULARIO = "#4D4358"

POSITIVO = "#4B8B5A"
NEGATIVO = "#B45B6A"
PELIGRO_FONDO = "#FCE7EB"
PELIGRO_FONDO_HOVER = "#F7D2DA"
PELIGRO_TEXTO = "#A83F55"

BARRA_FONDO = "#EEE9F5"
BARRA_PROGRESO = "#8B68C7"

FUENTE = "Segoe UI"
FUENTE_EMOJI = "Segoe UI Emoji"


# ---------------------------------------------------------------------------
# Tipografías
# ---------------------------------------------------------------------------


def fuente(tamano: int, negrita: bool = False) -> QFont:
    """Devuelve la fuente base de la aplicación."""

    peso = QFont.Weight.Bold if negrita else QFont.Weight.Normal
    return QFont(FUENTE, tamano, peso)


def fuente_emoji(tamano: int) -> QFont:
    return QFont(FUENTE_EMOJI, tamano)


# ---------------------------------------------------------------------------
# Tema de la aplicación
# ---------------------------------------------------------------------------

OBJETO_PAGINA = "pagina_app"


def preparar_pagina(pagina: QWidget) -> None:
    """Habilita el pintado del fondo en una página de contenido.

    Un ``QWidget`` sin ``paintEvent`` propio solo dibuja el fondo definido en
    su hoja de estilo cuando tiene activo ``WA_StyledBackground``; sin ese
    atributo la superficie queda a cargo de la paleta del sistema.
    """

    pagina.setObjectName(OBJETO_PAGINA)
    pagina.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


def construir_paleta() -> QPalette:
    """Paleta clara fija, independiente del tema del sistema operativo."""

    rol = QPalette.ColorRole
    grupo = QPalette.ColorGroup

    paleta = QPalette()
    paleta.setColor(rol.Window, QColor(FONDO))
    paleta.setColor(rol.WindowText, QColor(TEXTO))
    paleta.setColor(rol.Base, QColor(TARJETA))
    paleta.setColor(rol.AlternateBase, QColor(TARJETA_SUAVE))
    paleta.setColor(rol.Text, QColor(TEXTO))
    paleta.setColor(rol.Button, QColor(TARJETA))
    paleta.setColor(rol.ButtonText, QColor(TEXTO))
    paleta.setColor(rol.BrightText, QColor("#FFFFFF"))
    paleta.setColor(rol.Highlight, QColor(MORADO))
    paleta.setColor(rol.HighlightedText, QColor("#FFFFFF"))
    paleta.setColor(rol.ToolTipBase, QColor(TEXTO))
    paleta.setColor(rol.ToolTipText, QColor("#FFFFFF"))
    paleta.setColor(rol.PlaceholderText, QColor(TEXTO_TENUE))
    paleta.setColor(rol.Link, QColor(MORADO))
    paleta.setColor(rol.Light, QColor(TARJETA))
    paleta.setColor(rol.Midlight, QColor(LATERAL))
    paleta.setColor(rol.Mid, QColor(MORADO_BORDE))
    paleta.setColor(rol.Dark, QColor(TEXTO_ETIQUETA))
    paleta.setColor(rol.Shadow, QColor("#D9D3E2"))

    for deshabilitado in (rol.Text, rol.WindowText, rol.ButtonText):
        paleta.setColor(grupo.Disabled, deshabilitado, QColor(TEXTO_TENUE))

    return paleta


def instalar_traducciones(aplicacion: QApplication) -> None:
    """Traduce al español los textos propios de Qt.

    ``QMessageBox`` y otros cuadros estándar componen sus botones con los
    textos de Qt, que sin traducción instalada aparecen en inglés.
    """

    traductor = QTranslator(aplicacion)
    directorio = QLibraryInfo.path(
        QLibraryInfo.LibraryPath.TranslationsPath
    )

    if traductor.load(QLocale("es_CO"), "qt", "_", directorio):
        aplicacion.installTranslator(traductor)


def aplicar_tema(aplicacion: QApplication) -> None:
    """Fija estilo, paleta, traducciones y hojas globales de la aplicación.

    Debe invocarse una sola vez, antes de crear cualquier ventana.
    """

    aplicacion.setStyle("Fusion")
    aplicacion.setPalette(construir_paleta())
    aplicacion.setStyleSheet(estilo_global())
    instalar_traducciones(aplicacion)


def estilo_global() -> str:
    """Ajustes que aplican a toda la aplicación (ventanas y controles)."""

    return f"""
        QMainWindow,
        QDialog,
        QStackedWidget {{
            background-color: {FONDO};
        }}

        QToolTip {{
            background-color: {TEXTO};
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 5px 8px;
        }}

        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical {{
            background: {MORADO_BORDE};
            border-radius: 4px;
            min-height: 32px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {MORADO_DESHABILITADO};
        }}

        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal {{
            background: {MORADO_BORDE};
            border-radius: 4px;
            min-width: 32px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {MORADO_DESHABILITADO};
        }}

        QScrollBar::add-line,
        QScrollBar::sub-line,
        QScrollBar::add-page,
        QScrollBar::sub-page {{
            background: transparent;
            border: none;
            width: 0;
            height: 0;
        }}
    """


# ---------------------------------------------------------------------------
# Adaptación al tamaño de pantalla
# ---------------------------------------------------------------------------

MARGEN_PAGINA_ESCRITORIO = 30
MARGEN_PAGINA_MOVIL = 14
COLUMNAS_DATOS_MOVIL = 2
ESPACIADO_DATOS_ESCRITORIO = 28
ESPACIADO_DATOS_MOVIL = 16


def uso_movil() -> bool:
    """Indica si la interfaz debe usar el diseño compacto."""

    return config.es_movil()


def margen_pagina() -> int:
    """Margen interior de una página según el espacio disponible."""

    return MARGEN_PAGINA_MOVIL if uso_movil() else MARGEN_PAGINA_ESCRITORIO


def ancho_dialogo(preferido: int) -> int:
    """Ancho de un diálogo acotado al espacio real de la pantalla.

    En un teléfono, un diálogo de ancho fijo mayor que la pantalla quedaría
    recortado y sus botones resultarían inalcanzables.
    """

    pantalla = QGuiApplication.primaryScreen()

    if pantalla is None:
        return preferido

    disponible = int(pantalla.availableGeometry().width() * 0.94)

    return max(min(preferido, disponible), 280)


def rejilla_datos(datos: Sequence[tuple[str, str]]) -> QGridLayout:
    """Distribuye pares etiqueta/valor en una rejilla adaptable.

    En escritorio cada dato ocupa su propia columna; en móvil se reparten en
    dos columnas para que ningún valor quede recortado.
    """

    movil = uso_movil()
    rejilla = QGridLayout()
    rejilla.setHorizontalSpacing(
        ESPACIADO_DATOS_MOVIL if movil else ESPACIADO_DATOS_ESCRITORIO
    )
    rejilla.setVerticalSpacing(10)

    columnas = COLUMNAS_DATOS_MOVIL if movil else max(len(datos), 1)

    for indice, (etiqueta, valor) in enumerate(datos):
        fila, columna = divmod(indice, columnas)

        columna_layout = QVBoxLayout()
        columna_layout.setSpacing(2)

        titulo = QLabel(etiqueta)
        titulo.setStyleSheet(estilo_etiqueta_dato())

        contenido = QLabel(valor)
        contenido.setWordWrap(True)
        contenido.setStyleSheet(
            f"color: {TEXTO_CAMPO}; font-size: 13px; font-weight: bold;"
        )

        columna_layout.addWidget(titulo)
        columna_layout.addWidget(contenido)
        rejilla.addLayout(columna_layout, fila, columna)

    # La columna libre absorbe el espacio restante, como el ensanchador que
    # separa los datos de las acciones en la disposición de escritorio.
    rejilla.setColumnStretch(columnas, 1)

    return rejilla


def fila_de_tarjetas(*tarjetas: QWidget) -> QGridLayout:
    """Distribuye tarjetas de resumen según el espacio disponible.

    En escritorio comparten una fila; en móvil se apilan para que el contenido
    de cada una conserve su ancho legible.
    """

    rejilla = QGridLayout()
    rejilla.setSpacing(15)

    for indice, tarjeta in enumerate(tarjetas):
        if uso_movil():
            rejilla.addWidget(tarjeta, indice, 0)
        else:
            rejilla.addWidget(tarjeta, 0, indice)
            rejilla.setColumnStretch(indice, 1)

    return rejilla


def fila_de_acciones(
    principal: QWidget,
    secundario: QWidget | None = None,
    peligro: QWidget | None = None,
    editar: QWidget | None = None,
) -> QLayout:
    """Distribuye las acciones de una tarjeta según el espacio disponible.

    En escritorio se alinean en una fila, con la acción destructiva al final; en
    móvil la acción principal ocupa la fila completa y las demás se reparten de
    dos en dos debajo, porque tres botones no caben en el ancho de un teléfono.
    Cuando el número de acciones complementarias es impar, la última ocupa la
    fila entera en lugar de dejar un hueco a su lado.
    """

    if not uso_movil():
        fila = QHBoxLayout()
        fila.addWidget(principal)

        if secundario is not None:
            fila.addWidget(secundario)

        fila.addStretch()

        if editar is not None:
            fila.addWidget(editar)

        if peligro is not None:
            fila.addWidget(peligro)

        return fila

    rejilla = QGridLayout()
    rejilla.setHorizontalSpacing(10)
    rejilla.setVerticalSpacing(8)
    rejilla.addWidget(principal, 0, 0, 1, 2)

    acciones = [
        accion
        for accion in (secundario, editar, peligro)
        if accion is not None
    ]

    for indice, accion in enumerate(acciones):
        fila = 1 + indice // 2
        ultima_impar = indice == len(acciones) - 1 and len(acciones) % 2 == 1

        if ultima_impar:
            rejilla.addWidget(accion, fila, 0, 1, 2)
        else:
            rejilla.addWidget(accion, fila, indice % 2)

    rejilla.setColumnStretch(0, 1)
    rejilla.setColumnStretch(1, 1)

    return rejilla


def encabezado_pagina(titulo: QWidget, accion: QWidget) -> QLayout:
    """Encabezado con el título de la página y su acción principal.

    En escritorio ambos comparten la fila con el título a la izquierda; en
    móvil se apilan porque el título y el botón juntos superan el ancho de un
    teléfono y forzarían desplazamiento horizontal.
    """

    if not uso_movil():
        fila = QHBoxLayout()
        fila.addWidget(titulo)
        fila.addStretch()
        fila.addWidget(accion)
        return fila

    columna = QVBoxLayout()
    columna.setSpacing(12)
    columna.addWidget(titulo)
    columna.addWidget(accion)
    return columna


# ---------------------------------------------------------------------------
# Hojas de estilo reutilizables
# ---------------------------------------------------------------------------


def estilo_pagina() -> str:
    """Fondo de una página completa y color base de su texto.

    El fondo se declara sobre la propia página (identificada con
    :data:`OBJETO_PAGINA`) para no teñir de opaco los controles hijos, que en
    otro caso perderían su propio estilo.
    """

    return f"""
        QWidget#{OBJETO_PAGINA} {{
            background-color: {FONDO};
        }}

        QLabel {{
            color: {TEXTO};
            background-color: transparent;
        }}
    """


def estilo_dialogo() -> str:
    """Hoja común de los formularios de alta.

    Reúne el fondo del cuadro, el color de sus rótulos y el aspecto de los
    campos y selectores, que cada diálogo declaraba por su cuenta.
    """

    return (
        f"""
        QDialog {{
            background-color: {FONDO};
        }}

        QLabel {{
            color: {TEXTO_FORMULARIO};
            background-color: transparent;
        }}
        """
        + estilo_campos()
        + estilo_selectores()
    )


def estilo_boton_primario(padding: str = "10px 15px") -> str:
    """Botón de acción principal."""

    return f"""
        QPushButton {{
            background-color: {MORADO};
            color: white;
            border: none;
            border-radius: 9px;
            padding: {padding};
            font-weight: bold;
        }}

        QPushButton:hover {{
            background-color: {MORADO_HOVER};
        }}

        QPushButton:pressed {{
            background-color: {MORADO_ACTIVO};
        }}

        QPushButton:disabled {{
            background-color: {MORADO_DESHABILITADO};
            color: {TARJETA};
        }}
    """


def estilo_boton_secundario() -> str:
    """Botón de acción complementaria (cancelar, cerrar, alternativas)."""

    return f"""
        QPushButton {{
            background-color: {TARJETA};
            color: {TEXTO_TITULO};
            border: 1px solid {MORADO_BORDE};
            border-radius: 9px;
            padding: 9px 15px;
        }}

        QPushButton:hover {{
            background-color: {LATERAL};
            border: 1px solid {MORADO_CLARO};
        }}

        QPushButton:pressed {{
            background-color: {MORADO_CLARO};
        }}

        QPushButton:disabled {{
            color: {TEXTO_TENUE};
            background-color: {TARJETA_SUAVE};
        }}
    """


def estilo_boton_peligro(padding: str = "0") -> str:
    """Botón de acción destructiva."""

    return f"""
        QPushButton {{
            background-color: {PELIGRO_FONDO};
            color: {PELIGRO_TEXTO};
            border: none;
            border-radius: 8px;
            padding: {padding};
        }}

        QPushButton:hover {{
            background-color: {PELIGRO_FONDO_HOVER};
        }}

        QPushButton:pressed {{
            background-color: {PELIGRO_TEXTO};
            color: {TARJETA};
        }}

        QPushButton:disabled {{
            background-color: {TARJETA_SUAVE};
            color: {TEXTO_TENUE};
        }}
    """


def estilo_tarjeta(radio: int = 16, color: str = TARJETA) -> str:
    """Contenedor tipo tarjeta."""

    return f"""
        QFrame {{
            background-color: {color};
            border-radius: {radio}px;
        }}
    """


def estilo_campos() -> str:
    """Campos de entrada de los formularios."""

    return f"""
        QLineEdit,
        QSpinBox,
        QDoubleSpinBox,
        QDateEdit,
        QTextEdit {{
            background-color: white;
            border: 1px solid {MORADO_BORDE};
            border-radius: 8px;
            padding: 7px;
            color: {TEXTO_CAMPO};
            selection-background-color: {MORADO};
            selection-color: white;
        }}

        QLineEdit:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QDateEdit:focus,
        QTextEdit:focus {{
            border: 1px solid {BARRA_PROGRESO};
        }}
    """


def estilo_selectores() -> str:
    """Listas desplegables."""

    # En un teléfono dos selectores de 150 px no caben en la misma fila.
    ancho_minimo = 110 if uso_movil() else 150

    return f"""
        QComboBox {{
            background-color: white;
            border: 1px solid {MORADO_BORDE};
            border-radius: 9px;
            padding: 8px 10px;
            color: #514568;
            min-width: {ancho_minimo}px;
        }}

        QComboBox:focus {{
            border: 1px solid {MORADO};
        }}

        QComboBox QAbstractItemView {{
            background-color: white;
            border: 1px solid {MORADO_BORDE};
            border-radius: 8px;
            padding: 4px;
            color: {TEXTO};
            outline: none;
            selection-background-color: {MORADO_CLARO};
            selection-color: {TEXTO_TITULO};
        }}
    """


def estilo_barra_progreso() -> str:
    return f"""
        QProgressBar {{
            background-color: {BARRA_FONDO};
            border: none;
            border-radius: 7px;
            height: 14px;
            text-align: center;
            color: {TEXTO_TITULO};
            font-size: 11px;
            font-weight: bold;
        }}

        QProgressBar::chunk {{
            background-color: {BARRA_PROGRESO};
            border-radius: 7px;
        }}
    """


def estilo_texto_secundario(tamano: int = 13) -> str:
    return f"color: {TEXTO_SECUNDARIO}; font-size: {tamano}px;"


def estilo_titulo(tamano: int = 26) -> str:
    return f"font-size: {tamano}px; font-weight: bold; color: {TEXTO};"


def estilo_etiqueta_dato() -> str:
    return f"color: {TEXTO_ETIQUETA}; font-size: 12px;"
