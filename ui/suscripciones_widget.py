"""Vista de suscripciones: proyección de cobros, pagos y ciclo de facturación."""

from __future__ import annotations

import logging
from datetime import date

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from models.suscripcion import Suscripcion
from services.suscripciones_service import (
    comprometido_mes,
    costo_mensual_equivalente,
    detener_ciclo,
    eliminar_suscripcion,
    obtener_suscripciones,
    pagos_registrados,
    proximo_cobro,
    reactivar_ciclo,
    registrar_pago,
)
from ui import tema
from ui.pagina_listado import PaginaListado
from ui.suscripcion_dialog import NuevaSuscripcionDialog
from utils.dinero import formatear_dinero
from utils.fechas import dias_entre

logger = logging.getLogger(__name__)


class SuscripcionesWidget(PaginaListado):
    """Página de gestión de suscripciones recurrentes."""

    ESPACIADO_PAGINA = 14

    def __init__(self, parent=None):
        super().__init__(parent)

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        boton_nueva = QPushButton("＋ Nueva suscripción")
        boton_nueva.clicked.connect(self._nueva_suscripcion)

        self.titulo_pagina("🔁 Suscripciones", boton_nueva)

        self.resumen_label = QLabel("Comprometido este mes: $ 0")
        self.resumen_label.setWordWrap(True)
        self.resumen_label.setStyleSheet(
            f"color: {tema.TEXTO_ETIQUETA}; font-size: 14px;"
        )
        self.layout_principal.addWidget(self.resumen_label)

        self.proximo_label = QLabel("")
        self.proximo_label.setWordWrap(True)
        self.proximo_label.setStyleSheet(tema.estilo_texto_secundario())
        self.layout_principal.addWidget(self.proximo_label)

        self.agregar_area()
        self.aplicar_estilos()

    def estilos_extra(self) -> str:
        return tema.estilo_boton_primario()

    # ======================================================
    # ACTUALIZACIÓN
    # ======================================================

    def actualizar(self) -> None:
        """Recarga las suscripciones y la proyección de compromisos."""

        self.limpiar_listado()

        suscripciones = obtener_suscripciones()
        pagos = pagos_registrados()

        self.resumen_label.setText(
            "Comprometido este mes: "
            + formatear_dinero(comprometido_mes())
            + "   ·   Costo mensual equivalente: "
            + formatear_dinero(costo_mensual_equivalente())
        )

        self._actualizar_proximo_cobro()

        if not suscripciones:
            self.mostrar_mensaje(
                "Todavía no tienes suscripciones registradas."
            )
            return

        for suscripcion in suscripciones:
            self.agregar_tarjeta(
                self._crear_tarjeta(
                    suscripcion,
                    pagos.get(suscripcion.id, set()),
                )
            )

    def _actualizar_proximo_cobro(self) -> None:
        hoy = date.today()
        siguiente = proximo_cobro(hoy)

        if siguiente is None:
            self.proximo_label.setText(
                "No hay cobros programados con las suscripciones vigentes."
            )
            return

        suscripcion, cobro = siguiente
        self.proximo_label.setText(
            f"Próximo cobro: {suscripcion.nombre} el "
            f"{cobro.strftime('%d/%m/%Y')} "
            f"(en {dias_entre(hoy, cobro)} día(s))"
        )

    # ======================================================
    # TARJETA DE SUSCRIPCIÓN
    # ======================================================

    def _crear_tarjeta(
        self,
        suscripcion: Suscripcion,
        cobros: set[date],
    ) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setStyleSheet(tema.estilo_tarjeta())

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        encabezado = QHBoxLayout()

        nombre = QLabel(suscripcion.nombre)
        nombre.setWordWrap(True)
        nombre.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {tema.TEXTO_TITULO};"
        )
        encabezado.addWidget(nombre)
        encabezado.addStretch()

        estado = QLabel(
            "🟢 Ciclo vigente" if suscripcion.activa else "⏹ Ciclo detenido"
        )
        estado.setStyleSheet(
            f"color: {tema.POSITIVO if suscripcion.activa else tema.TEXTO_TENUE};"
            f" font-weight: bold; font-size: 12px;"
        )
        encabezado.addWidget(estado)
        layout.addLayout(encabezado)

        layout.addLayout(
            tema.rejilla_datos(self._datos_de_tarjeta(suscripcion))
        )

        if suscripcion.descripcion:
            descripcion = QLabel(suscripcion.descripcion)
            descripcion.setWordWrap(True)
            descripcion.setStyleSheet(
                f"color: {tema.TEXTO_TENUE}; font-size: 12px;"
            )
            layout.addWidget(descripcion)

        layout.addLayout(self._crear_botones(suscripcion, cobros))

        return tarjeta

    @staticmethod
    def _datos_de_tarjeta(
        suscripcion: Suscripcion,
    ) -> list[tuple[str, str]]:
        hoy = date.today()
        cobro = suscripcion.proximo_cobro(hoy)

        return [
            ("Costo", formatear_dinero(suscripcion.costo)),
            ("Facturación", suscripcion.etiqueta_periodicidad),
            (
                "Próximo cobro",
                (
                    f"{cobro.strftime('%d/%m/%Y')} "
                    f"(en {dias_entre(hoy, cobro)} día(s))"
                    if cobro is not None
                    else "Sin cobros programados"
                ),
            ),
            ("Equivalente mensual",
             formatear_dinero(suscripcion.costo_mensual_equivalente)),
        ]

    def _crear_botones(
        self,
        suscripcion: Suscripcion,
        cobros: set[date],
    ) -> QLayout:
        ciclo_cobrado = self._fecha_del_ciclo(suscripcion) in cobros

        boton_cobro = QPushButton(
            "✔ Ciclo cobrado" if ciclo_cobrado else "＋ Registrar cobro"
        )
        boton_cobro.setStyleSheet(tema.estilo_boton_primario("9px 15px"))
        boton_cobro.setEnabled(suscripcion.activa and not ciclo_cobrado)
        boton_cobro.clicked.connect(
            lambda _evento, s=suscripcion: self._registrar_cobro(s)
        )

        if suscripcion.activa:
            boton_ciclo = QPushButton("⏹ Detener ciclo")
            boton_ciclo.clicked.connect(
                lambda _evento, s=suscripcion: self._detener_ciclo(s)
            )
        else:
            boton_ciclo = QPushButton("▶ Reactivar ciclo")
            boton_ciclo.clicked.connect(
                lambda _evento, s=suscripcion: self._reactivar_ciclo(s)
            )

        boton_ciclo.setStyleSheet(tema.estilo_boton_secundario())

        boton_eliminar = QPushButton("🗑️ Eliminar")
        boton_eliminar.setStyleSheet(tema.estilo_boton_peligro("9px 15px"))
        boton_eliminar.clicked.connect(
            lambda _evento, s=suscripcion: self._confirmar_eliminacion(s)
        )

        return tema.fila_de_acciones(
            boton_cobro,
            boton_ciclo,
            boton_eliminar,
        )

    # ======================================================
    # ACCIONES
    # ======================================================

    def _nueva_suscripcion(self) -> None:
        dialogo = NuevaSuscripcionDialog(self)

        if dialogo.exec():
            self.actualizar()

    @staticmethod
    def _fecha_del_ciclo(suscripcion: Suscripcion) -> date:
        """Fecha del ciclo vigente: el cobro de este mes o el siguiente.

        Registrar el gasto con la fecha del ciclo (y no con la fecha del clic)
        permite que la comprobación de duplicidad identifique el periodo y que
        el gasto quede contabilizado en el mes que corresponde.
        """

        hoy = date.today()
        cobros = suscripcion.cobros_del_mes(hoy.year, hoy.month)

        if cobros:
            return cobros[0]

        return suscripcion.proximo_cobro(hoy) or hoy

    def _registrar_cobro(self, suscripcion: Suscripcion) -> None:
        fecha_cobro = self._fecha_del_ciclo(suscripcion)

        respuesta = QMessageBox.question(
            self,
            "Registrar cobro",
            f"¿Registrar el cobro de esta suscripción?\n\n"
            f"{suscripcion.nombre}\n"
            f"{formatear_dinero(suscripcion.costo)}\n"
            f"Ciclo: {fecha_cobro.strftime('%d/%m/%Y')}\n\n"
            "Se descontará del dinero disponible como gasto del mes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            registrar_pago(suscripcion.id, fecha_cobro)
        except ValueError as error:
            QMessageBox.warning(self, "Cobro no registrado", str(error))
            return
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo registrar el cobro.")
            QMessageBox.critical(
                self,
                "No se pudo registrar",
                f"Ocurrió un error al registrar el cobro:\n{error}",
            )
            return

        self.actualizar()

    def _detener_ciclo(self, suscripcion: Suscripcion) -> None:
        respuesta = QMessageBox.question(
            self,
            "Detener ciclo de facturación",
            f'¿Detener el ciclo de "{suscripcion.nombre}"?\n\n'
            "Dejará de contar como compromiso del mes. Los cobros ya "
            "registrados se conservan en Movimientos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        detener_ciclo(suscripcion.id)
        self.actualizar()

    def _reactivar_ciclo(self, suscripcion: Suscripcion) -> None:
        respuesta = QMessageBox.question(
            self,
            "Reactivar ciclo de facturación",
            f'¿Reactivar el ciclo de "{suscripcion.nombre}"?\n\n'
            "Volverá a contar como compromiso del mes en curso.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        reactivar_ciclo(suscripcion.id)
        self.actualizar()

    def _confirmar_eliminacion(self, suscripcion: Suscripcion) -> None:
        respuesta = QMessageBox.question(
            self,
            "Eliminar suscripción",
            f'¿Seguro que quieres eliminar "{suscripcion.nombre}"?\n\n'
            "Los gastos ya registrados por sus cobros se conservan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            eliminada = eliminar_suscripcion(suscripcion.id)
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo eliminar la suscripción.")
            QMessageBox.critical(
                self,
                "No se pudo eliminar",
                f"Ocurrió un error al eliminar la suscripción:\n{error}",
            )
            return

        if not eliminada:
            QMessageBox.warning(
                self,
                "Suscripción no encontrada",
                "La suscripción ya no existe en la base de datos.",
            )

        self.actualizar()
