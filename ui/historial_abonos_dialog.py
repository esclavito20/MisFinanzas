"""Historial de abonos de una deuda, con corrección y eliminación.

Sustituye al aviso de solo lectura que mostraba los abonos: corregir un importe
o una fecha mal registrada es una operación frecuente, y ahora se hace desde el
mismo historial, sin salir a buscar el movimiento correspondiente.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from models.abono import Abono
from models.deuda import Deuda
from services.deudas_service import (
    eliminar_abono,
    obtener_abonos,
    obtener_deuda,
)
from ui import tema
from ui.abono_dialog import AbonoDialog
from utils.dinero import formatear_dinero
from utils.fechas import formatear_fecha

logger = logging.getLogger(__name__)


class HistorialAbonosDialog(QDialog):
    """Lista los abonos de una deuda y permite corregirlos o retirarlos."""

    ANCHO = 560

    def __init__(self, deuda: Deuda, parent=None):
        super().__init__(parent)

        # La página de deudas refresca sus tarjetas cuando el historial cambió.
        self.cambios = False

        self.deuda = deuda

        self.setWindowTitle(f"Historial de abonos · {deuda.nombre}")
        self.setFixedWidth(tema.ancho_dialogo(self.ANCHO))

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)

        titulo = QLabel(f"🧾 {self.deuda.nombre}")
        titulo.setWordWrap(True)
        titulo.setStyleSheet(tema.estilo_titulo(20))
        layout.addWidget(titulo)

        self.resumen_label = QLabel()
        self.resumen_label.setWordWrap(True)
        self.resumen_label.setStyleSheet(tema.estilo_texto_secundario(13))
        layout.addWidget(self.resumen_label)

        self.contenedor = QFrame()
        self.contenedor.setStyleSheet(tema.estilo_tarjeta(12))

        self.listado = QVBoxLayout(self.contenedor)
        self.listado.setContentsMargins(14, 14, 14, 14)
        self.listado.setSpacing(8)
        self.listado.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.contenedor)
        # El listado se desplaza dentro de un alto acotado: sin tope, un
        # historial largo estiraría el diálogo por encima de la pantalla.
        self.scroll.setMinimumHeight(200)
        self.scroll.setMaximumHeight(340)
        layout.addWidget(self.scroll, 1)

        ayuda = QLabel(
            "Corrige el importe o la fecha de un abono mal registrado, o "
            "retíralo por completo: el saldo de la deuda se recalcula solo."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet(tema.estilo_texto_secundario(12))
        layout.addWidget(ayuda)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setStyleSheet(tema.estilo_boton_secundario())
        boton_cerrar.clicked.connect(self.accept)

        cierre = QHBoxLayout()
        cierre.addStretch()
        cierre.addWidget(boton_cerrar)
        layout.addLayout(cierre)

        self.setStyleSheet(tema.estilo_dialogo())

    # ======================================================
    # CONTENIDO
    # ======================================================

    def actualizar(self) -> None:
        """Recarga la deuda y su historial tras cada corrección."""

        deuda = obtener_deuda(self.deuda.id)

        if deuda is not None:
            self.deuda = deuda

        abonos = obtener_abonos(self.deuda.id)

        self.resumen_label.setText(
            "Abonado "
            + formatear_dinero(self.deuda.total_abonado)
            + f" en {len(abonos)} abono(s)"
            + "   ·   Pendiente "
            + formatear_dinero(self.deuda.saldo_pendiente)
        )

        self._limpiar()

        if not abonos:
            self._agregar_mensaje("Esta deuda todavía no tiene abonos.")
            return

        for abono in abonos:
            self._agregar_fila(abono)

    def _limpiar(self) -> None:
        while self.listado.count() > 1:
            item = self.listado.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _agregar_fila(self, abono: Abono) -> None:
        self.listado.insertWidget(self.listado.count() - 1, self._crear_fila(abono))

    def _agregar_mensaje(self, texto: str) -> None:
        mensaje = QLabel(texto)
        mensaje.setWordWrap(True)
        mensaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mensaje.setStyleSheet(
            f"color: {tema.TEXTO_TENUE}; font-size: 13px; padding: 25px;"
        )
        self.listado.insertWidget(0, mensaje)

    def _crear_fila(self, abono: Abono) -> QFrame:
        fila = QFrame()
        fila.setStyleSheet(tema.estilo_tarjeta(10, tema.TARJETA_SUAVE))

        layout = QHBoxLayout(fila)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)

        valor = QLabel(formatear_dinero(abono.valor))
        valor.setFont(tema.fuente(13, negrita=True))

        detalle = QLabel(
            f"{formatear_fecha(abono.fecha)} · {abono.descripcion_mostrada}"
        )
        detalle.setWordWrap(True)
        detalle.setStyleSheet(f"color: {tema.TEXTO_TENUE}; font-size: 11px;")

        info.addWidget(valor)
        info.addWidget(detalle)
        layout.addLayout(info, 1)

        boton_editar = QPushButton("✏️")
        boton_editar.setToolTip("Modificar el monto y la fecha de este abono")
        boton_editar.setFixedSize(38, 34)
        boton_editar.setStyleSheet(tema.estilo_boton_secundario())
        boton_editar.clicked.connect(
            lambda _evento, item=abono: self._editar(item)
        )
        layout.addWidget(boton_editar)

        boton_eliminar = QPushButton("🗑️")
        boton_eliminar.setToolTip("Eliminar este abono")
        boton_eliminar.setFixedSize(38, 34)
        boton_eliminar.setStyleSheet(
            tema.estilo_boton_peligro()
            + f"QPushButton {{ font-size: 14px; padding: 0; }}"
        )
        boton_eliminar.clicked.connect(
            lambda _evento, item=abono: self._eliminar(item)
        )
        layout.addWidget(boton_eliminar)

        return fila

    # ======================================================
    # ACCIONES
    # ======================================================

    def _editar(self, abono: Abono) -> None:
        dialogo = AbonoDialog(self.deuda, abono=abono, parent=self)

        if not dialogo.exec():
            return

        self.cambios = True
        self.actualizar()

    def _eliminar(self, abono: Abono) -> None:
        respuesta = QMessageBox.question(
            self,
            "Eliminar abono",
            "¿Seguro que quieres eliminar este abono?\n\n"
            f"{formatear_fecha(abono.fecha)}\n"
            f"{formatear_dinero(abono.valor)}\n\n"
            "El saldo pendiente de la deuda volverá a subir por ese importe.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            eliminado = eliminar_abono(self.deuda.id, abono.id)
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo eliminar el abono.")
            QMessageBox.critical(
                self,
                "No se pudo eliminar",
                f"Ocurrió un error al eliminar el abono:\n{error}",
            )
            return

        if not eliminado:
            QMessageBox.warning(
                self,
                "Abono no encontrado",
                "El abono ya no existe en la base de datos.",
            )

        self.cambios = True
        self.actualizar()
