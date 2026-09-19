"""Vista de inversiones: rentabilidad devengada, vencimientos y retiro."""

from __future__ import annotations

import logging
from datetime import date

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from models.inversion import Inversion
from services.inversiones_service import (
    capital_invertido,
    eliminar_inversion,
    finalizar_inversion,
    obtener_inversiones,
    rendimiento_acumulado,
)
from ui import tema
from ui.inversion_dialog import NuevaInversionDialog
from ui.pagina_listado import PaginaListado
from utils.dinero import formatear_dinero, formatear_porcentaje
from utils.fechas import dias_entre

logger = logging.getLogger(__name__)


class InversionesWidget(PaginaListado):
    """Página de gestión de inversiones y su rendimiento."""

    ESPACIADO_PAGINA = 14

    def __init__(self, parent=None):
        super().__init__(parent)

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        boton_nueva = QPushButton("＋ Nueva inversión")
        boton_nueva.clicked.connect(self._nueva_inversion)

        self.titulo_pagina("📈 Inversiones", boton_nueva)

        self.resumen_label = QLabel("Capital invertido: $ 0")
        self.resumen_label.setWordWrap(True)
        self.resumen_label.setStyleSheet(
            f"color: {tema.TEXTO_ETIQUETA}; font-size: 14px;"
        )
        self.layout_principal.addWidget(self.resumen_label)

        self.nota_label = QLabel(
            "El capital invertido resta del dinero disponible sin contarse "
            "como gasto: es un traslado de efectivo y sigue siendo patrimonio."
        )
        self.nota_label.setWordWrap(True)
        self.nota_label.setStyleSheet(tema.estilo_texto_secundario(12))
        self.layout_principal.addWidget(self.nota_label)

        self.agregar_area()
        self.aplicar_estilos()

    def estilos_extra(self) -> str:
        return tema.estilo_boton_primario()

    # ======================================================
    # ACTUALIZACIÓN
    # ======================================================

    def actualizar(self) -> None:
        """Recalcula el capital vigente y el rendimiento devengado."""

        self.limpiar_listado()

        inversiones = obtener_inversiones()

        self.resumen_label.setText(
            "Capital invertido: "
            + formatear_dinero(capital_invertido())
            + "   ·   Rendimiento acumulado: "
            + formatear_dinero(rendimiento_acumulado())
        )

        if not inversiones:
            self.mostrar_mensaje(
                "Todavía no tienes inversiones registradas."
            )
            return

        for inversion in inversiones:
            self.agregar_tarjeta(self._crear_tarjeta(inversion))

    # ======================================================
    # TARJETA DE INVERSIÓN
    # ======================================================

    def _crear_tarjeta(self, inversion: Inversion) -> QFrame:
        hoy = date.today()

        tarjeta = QFrame()
        tarjeta.setStyleSheet(tema.estilo_tarjeta())

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        encabezado = QHBoxLayout()

        nombre = QLabel(inversion.etiqueta_tipo)
        nombre.setWordWrap(True)
        nombre.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {tema.TEXTO_TITULO};"
        )
        encabezado.addWidget(nombre)

        if inversion.entidad:
            entidad = QLabel(f"· {inversion.entidad}")
            entidad.setStyleSheet(
                f"color: {tema.TEXTO_ETIQUETA}; font-size: 15px;"
            )
            encabezado.addWidget(entidad)

        encabezado.addStretch()
        encabezado.addWidget(self._crear_estado(inversion, hoy))
        layout.addLayout(encabezado)

        layout.addLayout(
            tema.rejilla_datos(self._datos_de_tarjeta(inversion, hoy))
        )

        if inversion.es_plazo_fijo:
            progreso = QProgressBar()
            progreso.setRange(0, 100)
            progreso.setValue(int(inversion.progreso(hoy)))
            progreso.setTextVisible(True)
            progreso.setFormat(
                "Avance del plazo: "
                + formatear_porcentaje(inversion.progreso(hoy), 0)
            )
            progreso.setStyleSheet(tema.estilo_barra_progreso())
            layout.addWidget(progreso)

        layout.addWidget(self._crear_bloque_rendimiento(inversion, hoy))
        layout.addLayout(self._crear_botones(inversion))

        return tarjeta

    @staticmethod
    def _crear_estado(inversion: Inversion, hoy: date) -> QLabel:
        if not inversion.activa:
            texto, color = "✔ Retirada", tema.TEXTO_TENUE
        elif inversion.vencida(hoy):
            texto, color = "⏰ Vencida", tema.NEGATIVO
        else:
            texto, color = "🟢 Vigente", tema.POSITIVO

        estado = QLabel(texto)
        estado.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 12px;"
        )

        return estado

    @staticmethod
    def _datos_de_tarjeta(
        inversion: Inversion,
        hoy: date,
    ) -> list[tuple[str, str]]:
        if inversion.fecha_vencimiento is None:
            vencimiento = "Abierta (sin plazo)"
        elif inversion.vencida(hoy):
            vencimiento = f"{inversion.fecha_vencimiento.strftime('%d/%m/%Y')} (vencida)"
        else:
            vencimiento = (
                f"{inversion.fecha_vencimiento.strftime('%d/%m/%Y')} "
                f"(en {dias_entre(hoy, inversion.fecha_vencimiento)} día(s))"
            )

        return [
            ("Invertido", formatear_dinero(inversion.capital)),
            (
                "Rentabilidad",
                formatear_porcentaje(inversion.tasa_ea, 2) + " E.A.",
            ),
            ("Inicio", inversion.fecha_inicio.strftime("%d/%m/%Y")),
            ("Vencimiento", vencimiento),
        ]

    def _crear_bloque_rendimiento(
        self,
        inversion: Inversion,
        hoy: date,
    ) -> QFrame:
        bloque = QFrame()
        bloque.setStyleSheet(tema.estilo_tarjeta(10, tema.TARJETA_SUAVE))

        layout = QVBoxLayout(bloque)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(4)

        neto = inversion.rendimiento_neto(hoy)
        bruto = inversion.rendimiento_bruto(hoy)
        retenida = inversion.retencion(hoy)

        principal = QLabel(
            f"Rendimiento generado: {formatear_dinero(neto)} "
            f"· valor actual {formatear_dinero(inversion.valor_actual(hoy))}"
        )
        principal.setWordWrap(True)
        principal.setStyleSheet(
            f"color: {tema.POSITIVO}; font-size: 13px; font-weight: bold;"
        )
        layout.addWidget(principal)

        detalle = QLabel(
            f"Bruto {formatear_dinero(bruto)} − retención "
            f"{formatear_dinero(retenida)} "
            f"({formatear_porcentaje(inversion.retencion_porcentaje)} sobre "
            "el rendimiento)"
        )
        detalle.setWordWrap(True)
        detalle.setStyleSheet(
            f"color: {tema.TEXTO_TENUE}; font-size: 11px;"
        )
        layout.addWidget(detalle)

        if inversion.es_plazo_fijo:
            proyeccion = QLabel(
                "Proyectado al vencimiento: "
                f"{formatear_dinero(inversion.rendimiento_proyectado())} "
                f"de rendimiento neto · valor final "
                f"{formatear_dinero(inversion.valor_proyectado())}"
            )
            proyeccion.setWordWrap(True)
            proyeccion.setStyleSheet(
                f"color: {tema.TEXTO_TITULO}; font-size: 12px;"
            )
            layout.addWidget(proyeccion)

        return bloque

    def _crear_botones(self, inversion: Inversion) -> QLayout:
        boton_retiro = QPushButton("💵 Retirar inversión")
        boton_retiro.setStyleSheet(tema.estilo_boton_primario("9px 15px"))
        boton_retiro.setEnabled(inversion.activa)
        boton_retiro.clicked.connect(
            lambda _evento, i=inversion: self._retirar_inversion(i)
        )

        boton_eliminar = QPushButton("🗑️ Eliminar")
        boton_eliminar.setStyleSheet(tema.estilo_boton_peligro("9px 15px"))
        boton_eliminar.clicked.connect(
            lambda _evento, i=inversion: self._confirmar_eliminacion(i)
        )

        return tema.fila_de_acciones(boton_retiro, None, boton_eliminar)

    # ======================================================
    # ACCIONES
    # ======================================================

    def _nueva_inversion(self) -> None:
        dialogo = NuevaInversionDialog(self)

        if dialogo.exec():
            self.actualizar()

    def _retirar_inversion(self, inversion: Inversion) -> None:
        hoy = date.today()
        rendimiento = inversion.rendimiento_neto(hoy)
        entidad = f" · {inversion.entidad}" if inversion.entidad else ""

        respuesta = QMessageBox.question(
            self,
            "Retirar inversión",
            f"¿Retirar esta inversión?\n\n"
            f"{inversion.etiqueta_tipo}{entidad}\n"
            f"Capital: {formatear_dinero(inversion.capital)}\n"
            f"Rendimiento neto: {formatear_dinero(rendimiento)}\n"
            f"Total a recibir: "
            f"{formatear_dinero(inversion.valor_actual(hoy))}\n\n"
            "El capital vuelve al dinero disponible y el rendimiento se "
            "registra como ingreso.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            finalizar_inversion(inversion.id)
        except ValueError as error:
            QMessageBox.warning(self, "Retiro no aplicado", str(error))
            return
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo retirar la inversión.")
            QMessageBox.critical(
                self,
                "No se pudo retirar",
                f"Ocurrió un error al retirar la inversión:\n{error}",
            )
            return

        self.actualizar()

    def _confirmar_eliminacion(self, inversion: Inversion) -> None:
        respuesta = QMessageBox.question(
            self,
            "Eliminar inversión",
            f"¿Seguro que quieres eliminar esta inversión del registro?\n\n"
            f"{inversion.etiqueta_tipo} · "
            f"{formatear_dinero(inversion.capital)}\n\n"
            "Los rendimientos ya acreditados se conservan en Movimientos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            eliminada = eliminar_inversion(inversion.id)
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo eliminar la inversión.")
            QMessageBox.critical(
                self,
                "No se pudo eliminar",
                f"Ocurrió un error al eliminar la inversión:\n{error}",
            )
            return

        if not eliminada:
            QMessageBox.warning(
                self,
                "Inversión no encontrada",
                "La inversión ya no existe en la base de datos.",
            )

        self.actualizar()
