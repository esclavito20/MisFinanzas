"""Vista de movimientos: listado, filtros y eliminación."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from models.movimiento import TIPO_GASTO, TIPO_INGRESO, Movimiento
from services.categorias_service import obtener_categorias
from services.movimientos_service import (
    eliminar_movimiento,
    obtener_movimientos,
)
from ui import tema
from ui.movimiento_dialog import MovimientoDialog
from ui.pagina_listado import PaginaListado
from utils.dinero import formatear_dinero

logger = logging.getLogger(__name__)


def _icono(movimiento: Movimiento) -> str:
    """Icono del movimiento: el abono se distingue de un gasto ordinario."""

    if movimiento.es_abono:
        return "💳"

    return "💰" if movimiento.es_ingreso else "💸"


class MovimientosWidget(PaginaListado):
    """Página de gestión de movimientos."""

    # Las filas de movimiento son más densas que las tarjetas de otras páginas.
    ESPACIADO_TARJETAS = 10

    def __init__(self, parent=None):
        super().__init__(parent)

        self.movimientos: list[Movimiento] = []

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        boton_nuevo = QPushButton("＋ Agregar movimiento")
        boton_nuevo.clicked.connect(self._nuevo_movimiento)

        self.titulo_pagina("💰 Movimientos", boton_nuevo)

        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        self.filtro_tipo = QComboBox()
        self.filtro_tipo.addItem("Todos los tipos", None)
        self.filtro_tipo.addItem("💰 Ingresos", TIPO_INGRESO)
        self.filtro_tipo.addItem("💸 Gastos", TIPO_GASTO)

        self.filtro_categoria = QComboBox()
        self.filtro_categoria.addItem("Todas las categorías", None)

        for categoria in obtener_categorias():
            self.filtro_categoria.addItem(categoria.nombre, categoria.id)

        self.filtro_tipo.currentIndexChanged.connect(
            lambda _indice: self.actualizar()
        )
        self.filtro_categoria.currentIndexChanged.connect(
            lambda _indice: self.actualizar()
        )

        filtros.addWidget(QLabel("Filtrar:"))
        filtros.addWidget(self.filtro_tipo)
        filtros.addWidget(self.filtro_categoria)
        filtros.addStretch()
        self.layout_principal.addLayout(filtros)

        self.resumen_label = QLabel("0 movimientos")
        self.resumen_label.setWordWrap(True)
        self.resumen_label.setStyleSheet(tema.estilo_texto_secundario())
        self.layout_principal.addWidget(self.resumen_label)

        self.agregar_area()
        self.aplicar_estilos()

    def estilos_extra(self) -> str:
        return tema.estilo_selectores() + tema.estilo_boton_primario()

    # ======================================================
    # ACTUALIZACIÓN
    # ======================================================

    def actualizar(self) -> None:
        """Recarga los movimientos y aplica los filtros activos."""

        self.limpiar_listado()

        self.movimientos = obtener_movimientos()

        tipo = self.filtro_tipo.currentData()
        categoria_id = self.filtro_categoria.currentData()

        filtrados = [
            movimiento
            for movimiento in self.movimientos
            if (tipo is None or movimiento.tipo == tipo)
            and (
                categoria_id is None
                or movimiento.categoria_id == categoria_id
            )
        ]

        self.resumen_label.setText(
            f"{len(filtrados)} movimiento(s) mostrado(s) · "
            f"{len(self.movimientos)} registrado(s)"
        )

        if not filtrados:
            self.mostrar_mensaje(
                "No hay movimientos que coincidan con los filtros."
            )
            return

        for movimiento in filtrados:
            self.agregar_tarjeta(self._crear_fila(movimiento))

    def _crear_fila(self, movimiento: Movimiento) -> QFrame:
        fila = QFrame()
        fila.setStyleSheet(tema.estilo_tarjeta(radio=12))

        layout = QHBoxLayout(fila)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(12)

        icono = QLabel(_icono(movimiento))
        icono.setFont(tema.fuente_emoji(18))
        layout.addWidget(icono)

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

        valor_label = QLabel(formatear_dinero(movimiento.valor))
        valor_label.setFont(tema.fuente(12, negrita=True))
        valor_label.setStyleSheet(
            f"color: {tema.POSITIVO};"
            if movimiento.es_ingreso
            else f"color: {tema.NEGATIVO};"
        )
        layout.addWidget(valor_label)

        boton_eliminar = QPushButton("🗑️")
        boton_eliminar.setToolTip("Eliminar movimiento")
        boton_eliminar.setFixedSize(40, 36)
        boton_eliminar.setStyleSheet(
            tema.estilo_boton_peligro()
            + f"QPushButton {{ font-size: 15px; padding: 0; }}"
        )
        boton_eliminar.clicked.connect(
            lambda _evento, mov=movimiento: self._confirmar_eliminacion(mov)
        )
        layout.addWidget(boton_eliminar)

        return fila

    # ======================================================
    # ACCIONES
    # ======================================================

    def _nuevo_movimiento(self) -> None:
        dialogo = MovimientoDialog(self)

        if dialogo.exec():
            self.actualizar()

    def _confirmar_eliminacion(self, movimiento: Movimiento) -> None:
        detalle = (
            movimiento.descripcion
            or movimiento.categoria_mostrada
        )

        if movimiento.es_abono:
            titulo = "Eliminar abono"
            consecuencia = (
                "El saldo pendiente de la deuda volverá a subir por ese "
                "importe."
            )
        else:
            titulo = "Eliminar movimiento"
            consecuencia = "Esta acción no se puede deshacer."

        tipo_texto = "ingreso" if movimiento.es_ingreso else "gasto"
        encabezado = (
            "¿Seguro que quieres eliminar este abono?"
            if movimiento.es_abono
            else f"¿Seguro que quieres eliminar este {tipo_texto}?"
        )

        respuesta = QMessageBox.question(
            self,
            titulo,
            f"{encabezado}\n\n"
            f"{detalle}\n{movimiento.fecha.isoformat()}\n"
            f"{formatear_dinero(movimiento.valor)}\n\n"
            f"{consecuencia}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            eliminado = eliminar_movimiento(movimiento.id)
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo eliminar el movimiento.")
            QMessageBox.critical(
                self,
                "No se pudo eliminar",
                f"Ocurrió un error al eliminar el movimiento:\n{error}",
            )
            return

        if not eliminado:
            QMessageBox.warning(
                self,
                "Movimiento no encontrado",
                "El movimiento ya no existe en la base de datos.",
            )

        self.actualizar()
