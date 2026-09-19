"""Página de inicio: saldo, resumen del mes, gráfico y movimientos recientes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.movimiento import Movimiento
from services.deudas_service import (
    obtener_total_deudas_pendientes,
    pagado_a_deudas_mes,
)
from services.inversiones_service import capital_invertido
from services.movimientos_service import (
    calcular_saldo_mes,
    obtener_gastos_mes,
    obtener_gastos_por_categoria_mes,
    obtener_ingresos_mes,
    obtener_movimientos_recientes,
)
from services.suscripciones_service import comprometido_mes
from ui import tema
from ui.grafico_gastos import GraficoGastos
from ui.movimiento_dialog import MovimientoDialog
from utils.dinero import formatear_dinero


class DashboardWidget(QWidget):
    """Resumen financiero del mes en curso."""

    MAXIMO_MOVIMIENTOS_RECIENTES = 5

    def __init__(self, parent=None):
        super().__init__(parent)

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        tema.preparar_pagina(self)

        layout_pagina = QVBoxLayout(self)
        layout_pagina.setContentsMargins(0, 0, 0, 0)

        contenido = QWidget()
        contenido_layout = QVBoxLayout(contenido)
        margen = tema.margen_pagina()
        contenido_layout.setContentsMargins(margen, margen, margen, margen)
        contenido_layout.setSpacing(20)

        saludo = QLabel("Bienvenido Kevin 💜")
        saludo.setFont(tema.fuente(26, negrita=True))

        periodo = QLabel("Este es el resumen de tus finanzas")
        periodo.setStyleSheet(tema.estilo_texto_secundario(14))

        boton_nuevo = QPushButton("＋ Agregar movimiento")
        boton_nuevo.setFixedHeight(45)
        boton_nuevo.clicked.connect(self._nuevo_movimiento)

        contenido_layout.addWidget(saludo)
        contenido_layout.addWidget(periodo)
        contenido_layout.addWidget(boton_nuevo)
        contenido_layout.addWidget(self._crear_tarjeta_saldo())
        contenido_layout.addLayout(self._crear_tarjetas_resumen())
        contenido_layout.addWidget(self._crear_tarjeta_grafico())
        contenido_layout.addWidget(self._crear_tarjeta_movimientos())
        contenido_layout.addStretch()

        # El resumen es más alto que la ventana en pantallas pequeñas: la barra
        # de desplazamiento evita que el contenido quede recortado y que la
        # ventana crezca por encima del tamaño solicitado.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(contenido)
        layout_pagina.addWidget(self.scroll)

        self.setStyleSheet(
            tema.estilo_pagina() + tema.estilo_boton_primario()
        )

    def _crear_tarjeta_saldo(self) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setStyleSheet(tema.estilo_tarjeta(18, tema.MORADO_CLARO))

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(25, 22, 25, 22)

        titulo = QLabel("💵 Dinero disponible este mes")
        titulo.setStyleSheet(
            f"color: #6546A3; font-size: 14px; font-weight: bold;"
        )

        self.saldo_label = QLabel("$ 0")
        self.saldo_label.setFont(tema.fuente(30, negrita=True))
        self.saldo_label.setStyleSheet("color: #432A73;")

        self.saldo_detalle_label = QLabel("")
        self.saldo_detalle_label.setWordWrap(True)
        self.saldo_detalle_label.setStyleSheet(
            "color: #6546A3; font-size: 12px;"
        )

        layout.addWidget(titulo)
        layout.addWidget(self.saldo_label)
        layout.addWidget(self.saldo_detalle_label)

        return tarjeta

    def _crear_tarjetas_resumen(self) -> QLayout:
        self.ingresos_label = QLabel("$ 0")
        self.gastos_label = QLabel("$ 0")
        self.deudas_label = QLabel("$ 0")

        return tema.fila_de_tarjetas(
            self._crear_card("💰 Ingresos", self.ingresos_label, "Este mes"),
            self._crear_card("💸 Gastos", self.gastos_label, "Este mes"),
            self._crear_card("💳 Deudas", self.deudas_label, "Pendiente"),
        )

    def _crear_card(
        self,
        titulo: str,
        valor_label: QLabel,
        descripcion: str,
    ) -> QFrame:
        card = QFrame()
        card.setStyleSheet(tema.estilo_tarjeta(18))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)

        titulo_label = QLabel(titulo)
        titulo_label.setStyleSheet(
            f"color: {tema.TEXTO_ETIQUETA}; font-size: 13px; font-weight: bold;"
        )

        valor_label.setFont(tema.fuente(20, negrita=True))

        descripcion_label = QLabel(descripcion)
        descripcion_label.setStyleSheet(
            f"color: #9B929F; font-size: 11px;"
        )

        layout.addWidget(titulo_label)
        layout.addWidget(valor_label)
        layout.addWidget(descripcion_label)

        return card

    def _crear_tarjeta_grafico(self) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setStyleSheet(tema.estilo_tarjeta(18))

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(25, 20, 25, 20)

        titulo = QLabel("📊 Gastos del mes")
        titulo.setFont(tema.fuente(16, negrita=True))

        self.grafico_gastos = GraficoGastos()

        layout.addWidget(titulo)
        layout.addWidget(self.grafico_gastos)

        return tarjeta

    def _crear_tarjeta_movimientos(self) -> QFrame:
        self.tarjeta_movimientos = QFrame()
        self.tarjeta_movimientos.setStyleSheet(tema.estilo_tarjeta(18))

        self.movimientos_layout = QVBoxLayout(self.tarjeta_movimientos)
        self.movimientos_layout.setContentsMargins(25, 20, 25, 20)
        self.movimientos_layout.setSpacing(8)

        titulo = QLabel("🧾 Movimientos recientes")
        titulo.setFont(tema.fuente(16, negrita=True))

        self.movimientos_layout.addWidget(titulo)

        return self.tarjeta_movimientos

    # ======================================================
    # ACTUALIZACIÓN
    # ======================================================

    def actualizar(self) -> None:
        """Recalcula los indicadores del resumen.

        Todos los importes del bloque hablan del mes en curso, igual que las
        tarjetas de ingresos y gastos: un pago o un cobro de un mes anterior ya
        pertenece a su propio periodo y no debe mover el dinero disponible de
        hoy. El efectivo del mes sí descuenta los abonos —el dinero salió—, pero
        no aparecen en la tarjeta de gastos porque devolver un compromiso
        contraído no es consumir.

        Del resultado del mes se restan el capital invertido —que está fuera del
        efectivo sin haber sido un gasto— y los cobros de suscripciones aún
        pendientes en el mes.
        """

        efectivo = calcular_saldo_mes()
        invertido = capital_invertido()
        comprometido = comprometido_mes()
        disponible = efectivo - invertido - comprometido

        self.saldo_label.setText(formatear_dinero(disponible))
        self.saldo_label.setStyleSheet(
            "color: #432A73;"
            if disponible >= 0
            else f"color: {tema.NEGATIVO};"
        )
        self.saldo_detalle_label.setText(
            "Efectivo del mes "
            + formatear_dinero(efectivo)
            + "   ·   Invertido "
            + formatear_dinero(invertido)
            + "   ·   Comprometido "
            + formatear_dinero(comprometido)
            + "   ·   Pagado a deudas "
            + formatear_dinero(pagado_a_deudas_mes())
        )

        self.ingresos_label.setText(
            formatear_dinero(obtener_ingresos_mes())
        )
        self.gastos_label.setText(formatear_dinero(obtener_gastos_mes()))
        self.deudas_label.setText(
            formatear_dinero(obtener_total_deudas_pendientes())
        )

        self.grafico_gastos.establecer_datos(
            obtener_gastos_por_categoria_mes()
        )

        self._actualizar_movimientos_recientes()

    def _actualizar_movimientos_recientes(self) -> None:
        self._limpiar_movimientos_recientes()

        movimientos = obtener_movimientos_recientes(
            self.MAXIMO_MOVIMIENTOS_RECIENTES
        )

        if not movimientos:
            mensaje = QLabel(
                "Todavía no tienes movimientos registrados."
            )
            mensaje.setStyleSheet(
                f"color: {tema.TEXTO_TENUE}; font-size: 13px;"
            )
            self.movimientos_layout.addWidget(mensaje)
            return

        for movimiento in movimientos:
            self.movimientos_layout.addWidget(
                self._crear_fila_movimiento(movimiento)
            )

    def _limpiar_movimientos_recientes(self) -> None:
        """Retira las filas previas conservando el título de la tarjeta."""

        while self.movimientos_layout.count() > 1:
            item = self.movimientos_layout.takeAt(1)
            widget = item.widget()

            if widget is not None:
                # El widget se libera en el siguiente ciclo del bucle de
                # eventos; ocultarlo evita que siga pintándose mientras tanto.
                widget.hide()
                widget.deleteLater()

    def _crear_fila_movimiento(self, movimiento: Movimiento) -> QFrame:
        fila = QFrame()
        fila.setStyleSheet(tema.estilo_tarjeta(10, tema.TARJETA_SUAVE))

        layout = QHBoxLayout(fila)
        layout.setContentsMargins(15, 10, 15, 10)

        info = QVBoxLayout()

        titulo = QLabel(movimiento.categoria_mostrada)
        titulo.setFont(tema.fuente(12, negrita=True))

        detalle = QLabel(
            f"{movimiento.fecha.isoformat()} · "
            f"{movimiento.descripcion_mostrada}"
        )
        detalle.setStyleSheet(
            f"color: {tema.TEXTO_TENUE}; font-size: 11px;"
        )

        info.addWidget(titulo)
        info.addWidget(detalle)
        layout.addLayout(info)
        layout.addStretch()

        color = tema.POSITIVO if movimiento.es_ingreso else tema.NEGATIVO
        simbolo = "↑ " if movimiento.es_ingreso else "↓ "

        valor_label = QLabel(
            simbolo + formatear_dinero(movimiento.valor)
        )
        valor_label.setFont(tema.fuente(12, negrita=True))
        valor_label.setStyleSheet(f"color: {color};")
        layout.addWidget(valor_label)

        return fila

    # ======================================================
    # ACCIONES
    # ======================================================

    def _nuevo_movimiento(self) -> None:
        dialogo = MovimientoDialog(self)

        if dialogo.exec():
            self.actualizar()
