"""Vista de análisis mensual: ingresos, gastos, abonos y resultado.

El «Resultado» es el mismo dinero disponible que muestra el inicio: se calcula
con la misma función, de modo que las dos páginas no puedan dar cifras
distintas. Los abonos restan porque el dinero salió de la cuenta, aunque no
cuenten como gasto de consumo.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from services.deudas_service import pagado_a_deudas_mes
from services.movimientos_service import (
    calcular_saldo_mes,
    obtener_gastos_mes,
    obtener_gastos_por_categoria_mes,
    obtener_ingresos_mes,
)
from ui import tema
from utils.dinero import formatear_dinero, formatear_porcentaje

MAXIMO_CATEGORIAS_VISIBLES = 5


class AnalisisWidget(QWidget):
    """Página de resumen mensual."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        tema.preparar_pagina(self)

        layout = QVBoxLayout(self)
        margen = tema.margen_pagina()
        layout.setContentsMargins(margen, margen, margen, margen)
        layout.setSpacing(18)

        titulo = QLabel("📊 Análisis")
        titulo.setStyleSheet(tema.estilo_titulo())
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Un vistazo rápido a cómo se está moviendo tu dinero este mes"
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(tema.estilo_texto_secundario())
        layout.addWidget(subtitulo)

        self.ingresos_label = QLabel("$ 0")
        self.gastos_label = QLabel("$ 0")
        self.balance_label = QLabel("$ 0")

        layout.addLayout(
            tema.fila_de_tarjetas(
                self._crear_card("💰 Ingresos", self.ingresos_label, "Este mes"),
                self._crear_card("💸 Gastos", self.gastos_label, "Este mes"),
                self._crear_card(
                    "💜 Resultado",
                    self.balance_label,
                    "Ingresos - gastos - abonos",
                ),
            )
        )

        # Los abonos van en su propia línea y no en una tarjeta: una cuarta
        # tarjeta obligaría a ensanchar la ventana para que las cifras cupieran.
        self.abonos_label = QLabel()
        self.abonos_label.setWordWrap(True)
        self.abonos_label.setStyleSheet(tema.estilo_texto_secundario(13))
        layout.addWidget(self.abonos_label)

        self.estado_label = QLabel("")
        self.estado_label.setWordWrap(True)
        layout.addWidget(self.estado_label)

        tarjeta_categorias = QFrame()
        tarjeta_categorias.setStyleSheet(tema.estilo_tarjeta())

        self.categorias_layout = QVBoxLayout(tarjeta_categorias)
        self.categorias_layout.setContentsMargins(22, 20, 22, 20)
        self.categorias_layout.setSpacing(9)

        encabezado = QLabel("💡 En qué estás gastando")
        encabezado.setFont(tema.fuente(16, negrita=True))
        self.categorias_layout.addWidget(encabezado)

        layout.addWidget(tarjeta_categorias)
        layout.addStretch()

        self.setStyleSheet(tema.estilo_pagina())

    def _crear_card(
        self,
        titulo: str,
        valor_label: QLabel,
        descripcion: str,
    ) -> QFrame:
        card = QFrame()
        card.setStyleSheet(tema.estilo_tarjeta())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)

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

    # ======================================================
    # ACTUALIZACIÓN
    # ======================================================

    def actualizar(self) -> None:
        ingresos = obtener_ingresos_mes()
        gastos = obtener_gastos_mes()
        abonos = pagado_a_deudas_mes()
        # Misma fuente que el «Efectivo del mes» del inicio: las dos páginas
        # muestran siempre la misma cifra.
        resultado = calcular_saldo_mes()

        self.ingresos_label.setText(formatear_dinero(ingresos))
        self.gastos_label.setText(formatear_dinero(gastos))
        self.abonos_label.setText(
            "💳 Pagado a deudas este mes: " + formatear_dinero(abonos)
        )
        self.balance_label.setText(formatear_dinero(resultado))

        self._actualizar_estado(resultado)
        self._actualizar_categorias()

    def _actualizar_estado(self, resultado: float) -> None:
        if resultado > 0:
            self.estado_label.setText(
                "✅ Este mes te queda dinero después de gastos y deudas."
            )
            color = tema.POSITIVO
        elif resultado < 0:
            self.estado_label.setText(
                "⚠️ Este mes tus gastos y tus deudas superan tus ingresos."
            )
            color = tema.NEGATIVO
        else:
            self.estado_label.setText(
                "ℹ️ Este mes ingresos, gastos y deudas están equilibrados."
            )
            color = tema.TEXTO_ETIQUETA

        self.estado_label.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold;"
        )

    def _actualizar_categorias(self) -> None:
        while self.categorias_layout.count() > 1:
            item = self.categorias_layout.takeAt(1)
            widget = item.widget()

            if widget is not None:
                # El widget se libera en el siguiente ciclo del bucle de
                # eventos; ocultarlo evita que siga pintándose mientras tanto.
                widget.hide()
                widget.deleteLater()

        categorias = obtener_gastos_por_categoria_mes()

        if not categorias:
            mensaje = QLabel(
                "Todavía no hay gastos registrados este mes."
            )
            mensaje.setStyleSheet(
                f"color: {tema.TEXTO_TENUE}; font-size: 13px;"
            )
            self.categorias_layout.addWidget(mensaje)
            return

        total = sum(valor for _, valor in categorias)

        for categoria, valor in categorias[:MAXIMO_CATEGORIAS_VISIBLES]:
            self.categorias_layout.addWidget(
                self._crear_fila_categoria(categoria, valor, total)
            )

        if len(categorias) > MAXIMO_CATEGORIAS_VISIBLES:
            restante = sum(
                valor
                for _, valor in categorias[MAXIMO_CATEGORIAS_VISIBLES:]
            )
            aviso = QLabel(
                f"+ {len(categorias) - MAXIMO_CATEGORIAS_VISIBLES} "
                f"categoría(s) más por {formatear_dinero(restante)}"
            )
            aviso.setStyleSheet(
                f"color: {tema.TEXTO_TENUE}; font-size: 11px;"
            )
            self.categorias_layout.addWidget(aviso)

    def _crear_fila_categoria(
        self,
        categoria: str,
        valor: float,
        total: float,
    ) -> QWidget:
        porcentaje = (valor / total * 100) if total else 0

        nombre = QLabel(categoria)
        nombre.setStyleSheet("font-size: 13px;")

        porcentaje_label = QLabel(formatear_porcentaje(porcentaje))
        porcentaje_label.setStyleSheet(
            f"color: {tema.MORADO}; font-weight: bold;"
        )

        monto = QLabel(formatear_dinero(valor))
        monto.setFont(tema.fuente(12, negrita=True))

        fila = QHBoxLayout()
        fila.addWidget(nombre)
        fila.addStretch()
        fila.addWidget(porcentaje_label)
        fila.addWidget(monto)

        contenedor = QWidget()
        contenedor.setLayout(fila)

        return contenedor
