"""Ventana principal: barra lateral de navegación y páginas de la aplicación."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import config
from ui import tema
from ui.analisis_widget import AnalisisWidget
from ui.configuracion_dialog import ConfiguracionDialog
from ui.dashboard_widget import DashboardWidget
from ui.deudas_widget import DeudasWidget
from ui.inversiones_widget import InversionesWidget
from ui.movimientos_widget import MovimientosWidget
from ui.suscripciones_widget import SuscripcionesWidget


class VentanaPrincipal(QMainWindow):
    """Contenedor principal de la aplicación."""

    ANCHO_LATERAL = 230
    TAMANO_MINIMO = (1020, 640)
    TAMANO_MOVIL = (400, 780)
    ALTO_BARRA_INFERIOR = 62

    def __init__(self, parent=None):
        super().__init__(parent)

        self._botones: dict[str, QPushButton] = {}
        self.compacto = tema.uso_movil()

        self.setWindowTitle(config.NOMBRE_APP)

        if self.compacto:
            # En un teléfono la pantalla es más estrecha que cualquier mínimo
            # de escritorio: fijarlo impediría que la ventana cupiera.
            self.resize(*self.TAMANO_MOVIL)
        else:
            self.setMinimumSize(*self.TAMANO_MINIMO)
            self.resize(1200, 760)

        central = QWidget()
        self.setCentralWidget(central)

        layout_principal = QVBoxLayout(central) if self.compacto else QHBoxLayout(
            central
        )
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        self.paginas = QStackedWidget()

        self.pagina_inicio = DashboardWidget()
        self.pagina_movimientos = MovimientosWidget()
        self.pagina_deudas = DeudasWidget()
        self.pagina_suscripciones = SuscripcionesWidget()
        self.pagina_inversiones = InversionesWidget()
        self.pagina_analisis = AnalisisWidget()

        for entrada in self._entradas_navegacion():
            self.paginas.addWidget(entrada.pagina)

        if self.compacto:
            layout_principal.addWidget(self.paginas)
            layout_principal.addWidget(self._crear_barra_inferior())
        else:
            layout_principal.addWidget(self._crear_barra_lateral())
            layout_principal.addWidget(self.paginas)

        self.mostrar_inicio()

    # ======================================================
    # NAVEGACIÓN: DEFINICIÓN COMPARTIDA
    # ======================================================

    class _Entrada:
        """Elemento del menú: icono, textos y página asociada."""

        __slots__ = ("clave", "icono", "etiqueta", "corta", "pagina")

        def __init__(self, clave, icono, etiqueta, corta, pagina):
            self.clave = clave
            self.icono = icono
            self.etiqueta = etiqueta
            self.corta = corta
            self.pagina = pagina

    def _entradas_navegacion(self) -> tuple[_Entrada, ...]:
        """Fuente única de la navegación de ambas presentaciones."""

        return (
            self._Entrada("inicio", "🏠", "Inicio", "Inicio", self.pagina_inicio),
            self._Entrada(
                "movimientos",
                "💰",
                "Movimientos",
                "Movim.",
                self.pagina_movimientos,
            ),
            self._Entrada("deudas", "💳", "Deudas", "Deudas", self.pagina_deudas),
            self._Entrada(
                "suscripciones",
                "🔁",
                "Suscripciones",
                "Suscrip.",
                self.pagina_suscripciones,
            ),
            self._Entrada(
                "inversiones",
                "📈",
                "Inversiones",
                "Invers.",
                self.pagina_inversiones,
            ),
            self._Entrada(
                "analisis", "📊", "Análisis", "Análisis", self.pagina_analisis
            ),
        )

    def _crear_boton_navegacion(
        self,
        entrada: _Entrada,
        texto: str,
    ) -> QPushButton:
        boton = QPushButton(texto)
        boton.setCheckable(True)
        boton.setAutoExclusive(True)
        boton.setToolTip(entrada.etiqueta)
        boton.clicked.connect(
            lambda _marcado=False, p=entrada.pagina, c=entrada.clave: (
                self._mostrar(p, c)
            )
        )
        self._botones[entrada.clave] = boton

        return boton

    # ======================================================
    # BARRA INFERIOR (MÓVIL)
    # ======================================================

    def _crear_barra_inferior(self) -> QFrame:
        barra = QFrame()
        barra.setFixedHeight(self.ALTO_BARRA_INFERIOR)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        for entrada in self._entradas_navegacion():
            layout.addWidget(
                self._crear_boton_navegacion(
                    entrada,
                    f"{entrada.icono}\n{entrada.corta}",
                )
            )

        # Sin barra lateral, la configuración necesita un acceso propio.
        boton_configuracion = QPushButton("⚙️\nAjustes")
        boton_configuracion.setToolTip("Configuración")
        boton_configuracion.clicked.connect(self.abrir_configuracion)
        layout.addWidget(boton_configuracion)

        barra.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tema.LATERAL};
                border-top: 1px solid {tema.MORADO_BORDE};
            }}

            QPushButton {{
                border: none;
                border-radius: 9px;
                padding: 2px;
                font-size: 12px;
                color: #514568;
                background-color: transparent;
            }}

            QPushButton:checked {{
                background-color: {tema.MORADO_CLARO};
                color: #4B2E92;
                font-weight: bold;
            }}
            """
        )

        return barra

    # ======================================================
    # BARRA LATERAL (ESCRITORIO)
    # ======================================================

    def _crear_barra_lateral(self) -> QFrame:
        barra = QFrame()
        barra.setFixedWidth(self.ANCHO_LATERAL)

        layout = QVBoxLayout(barra)
        layout.setContentsMargins(20, 25, 20, 25)
        layout.setSpacing(8)

        logo = QLabel("💜 Mis Finanzas")
        logo.setFont(tema.fuente(18, negrita=True))

        subtitulo = QLabel("Finanzas personales")
        subtitulo.setStyleSheet(
            f"color: #8A78A8; font-size: 12px;"
        )

        layout.addWidget(logo)
        layout.addWidget(subtitulo)
        layout.addSpacing(30)

        for entrada in self._entradas_navegacion():
            layout.addWidget(
                self._crear_boton_navegacion(
                    entrada,
                    f"{entrada.icono}  {entrada.etiqueta}",
                )
            )

        layout.addStretch()

        boton_configuracion = QPushButton("⚙️  Configuración")
        boton_configuracion.clicked.connect(self.abrir_configuracion)
        layout.addWidget(boton_configuracion)

        barra.setStyleSheet(
            f"""
            QFrame {{
                background-color: {tema.LATERAL};
            }}

            QLabel {{
                color: #5B3E96;
                background-color: transparent;
            }}

            QPushButton {{
                border: none;
                border-radius: 10px;
                padding: 12px;
                text-align: left;
                font-size: 14px;
                color: #514568;
                background-color: transparent;
            }}

            QPushButton:hover {{
                background-color: #E5D9FF;
            }}

            QPushButton:pressed {{
                background-color: #D8C7FF;
            }}

            QPushButton:checked {{
                background-color: #E2D3FF;
                color: #4B2E92;
                font-weight: bold;
            }}
            """
        )

        return barra

    # ======================================================
    # NAVEGACIÓN
    # ======================================================

    def mostrar_inicio(self) -> None:
        self._mostrar(self.pagina_inicio, "inicio")

    def mostrar_movimientos(self) -> None:
        self._mostrar(self.pagina_movimientos, "movimientos")

    def mostrar_deudas(self) -> None:
        self._mostrar(self.pagina_deudas, "deudas")

    def mostrar_suscripciones(self) -> None:
        self._mostrar(self.pagina_suscripciones, "suscripciones")

    def mostrar_inversiones(self) -> None:
        self._mostrar(self.pagina_inversiones, "inversiones")

    def mostrar_analisis(self) -> None:
        self._mostrar(self.pagina_analisis, "analisis")

    def _mostrar(self, pagina: QWidget, clave: str) -> None:
        """Refresca la página solicitada antes de mostrarla.

        El refresco diferido mantiene sincronizadas todas las vistas sin
        recalcular las que el usuario no está consultando.
        """

        pagina.actualizar()
        self.paginas.setCurrentWidget(pagina)
        self._botones[clave].setChecked(True)

    # ======================================================
    # CONFIGURACIÓN
    # ======================================================

    def abrir_configuracion(self) -> None:
        dialogo = ConfiguracionDialog(self)
        dialogo.exec()

        # Una importación reemplaza el contenido de la base: las vistas que ya
        # estaban construidas seguirían mostrando los datos anteriores.
        if dialogo.datos_reemplazados:
            self.actualizar_todo()

    def actualizar_todo(self) -> None:
        """Refresca todas las páginas con el contenido actual de la base."""

        for entrada in self._entradas_navegacion():
            entrada.pagina.actualizar()
