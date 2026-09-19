"""Gráfico horizontal de gastos por categoría."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from ui import tema
from utils.dinero import formatear_dinero


class GraficoGastos(QWidget):
    """Barras proporcionales al gasto de cada categoría.

    El excedente de categorías se agrupa para que ninguna barra quede fuera del
    área visible del widget y la altura mínima se ajusta al número de filas.
    """

    ALTURA_FILA = 40
    MARGEN_SUPERIOR = 10
    MARGEN_IZQUIERDO = 130
    MARGEN_DERECHO = 110
    ALTURA_BARRA = 18
    ALTURA_MINIMA = 220
    MAXIMO_CATEGORIAS = 5
    ETIQUETA_RESTO = "Otras categorías"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.datos: list[tuple[str, float]] = []
        self.setMinimumHeight(self.ALTURA_MINIMA)

    def establecer_datos(
        self,
        datos,
        maximo_categorias: int = MAXIMO_CATEGORIAS,
    ) -> None:
        """Recibe los gastos agrupados por categoría y redibuja el gráfico."""

        self.datos = self._agrupar_categorias(datos, maximo_categorias)
        self.setMinimumHeight(self._altura_necesaria())
        self.update()

    @classmethod
    def _agrupar_categorias(
        cls,
        datos,
        maximo_categorias: int,
    ) -> list[tuple[str, float]]:
        categorias = [
            (str(nombre), float(valor or 0))
            for nombre, valor in datos
        ]

        if maximo_categorias <= 1 or len(categorias) <= maximo_categorias:
            return categorias

        visibles = categorias[: maximo_categorias - 1]
        resto = sum(valor for _, valor in categorias[maximo_categorias - 1:])

        return visibles + [(cls.ETIQUETA_RESTO, resto)]

    def _altura_necesaria(self) -> int:
        filas = max(len(self.datos), 1)
        return max(
            self.ALTURA_MINIMA,
            filas * self.ALTURA_FILA + self.MARGEN_SUPERIOR * 2,
        )

    def paintEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.datos:
            self._dibujar_mensaje(painter)
            painter.end()
            return

        maximo = max(valor for _, valor in self.datos)

        if maximo <= 0:
            self._dibujar_mensaje(painter)
            painter.end()
            return

        ancho_barra = max(
            self.width() - self.MARGEN_IZQUIERDO - self.MARGEN_DERECHO,
            20,
        )

        for indice, (categoria, valor) in enumerate(self.datos):
            self._dibujar_fila(
                painter,
                indice,
                categoria,
                valor,
                maximo,
                ancho_barra,
            )

        painter.end()

    def _dibujar_mensaje(self, painter: QPainter) -> None:
        painter.setPen(QColor(tema.TEXTO_TENUE))
        painter.setFont(QFont(tema.FUENTE, 11))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No hay gastos registrados este mes.",
        )

    def _dibujar_fila(
        self,
        painter: QPainter,
        indice: int,
        categoria: str,
        valor: float,
        maximo: float,
        ancho_barra: int,
    ) -> None:
        y = indice * self.ALTURA_FILA + self.MARGEN_SUPERIOR

        painter.setPen(QColor(tema.TEXTO_ETIQUETA))
        painter.setFont(QFont(tema.FUENTE, 10))
        painter.drawText(0, y + 20, self._recortar_nombre(painter, categoria))

        ancho_actual = max(int(ancho_barra * (valor / maximo)), 2)

        painter.setBrush(QColor(tema.BARRA_PROGRESO))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            self.MARGEN_IZQUIERDO,
            y + 7,
            ancho_actual,
            self.ALTURA_BARRA,
            9,
            9,
        )

        painter.setPen(QColor(tema.TEXTO_ETIQUETA))
        painter.setFont(QFont(tema.FUENTE, 10, QFont.Weight.Bold))
        painter.drawText(
            self.MARGEN_IZQUIERDO + ancho_barra + 10,
            y + 21,
            formatear_dinero(valor),
        )

    def _recortar_nombre(self, painter: QPainter, categoria: str) -> str:
        """Ajusta el nombre de la categoría al ancho reservado a la izquierda.

        Sin el recorte, un nombre largo se dibujaría por encima de la barra.
        """

        disponible = max(self.MARGEN_IZQUIERDO - 12, 40)

        return QFontMetrics(painter.font()).elidedText(
            categoria,
            Qt.TextElideMode.ElideRight,
            disponible,
        )
