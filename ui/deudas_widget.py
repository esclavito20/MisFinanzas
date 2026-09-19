"""Vista de deudas: tarjetas de progreso, recordatorios de pago e historial."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from models.deuda import (
    ALERTA_NINGUNA,
    ALERTA_PROXIMA,
    ALERTA_VENCIDA,
    Deuda,
)
from services.deudas_service import (
    eliminar_deuda,
    obtener_deudas,
)
from ui import tema
from ui.abono_dialog import AbonoDialog
from ui.deuda_dialog import NuevaDeudaDialog
from ui.historial_abonos_dialog import HistorialAbonosDialog
from ui.pagina_listado import PaginaListado
from utils.dinero import formatear_dinero, formatear_porcentaje
from utils.fechas import formatear_fecha

logger = logging.getLogger(__name__)

# Recordatorios que se nombran en el aviso antes de resumir el resto.
MAXIMO_ALERTAS_NOMBRADAS = 3


def _contar(cantidad: int, singular: str, plural: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _plazo(deuda: Deuda) -> str:
    """Describe en palabras la distancia al próximo pago."""

    dias = deuda.dias_para_pago()

    if dias is None:
        return ""

    if dias < 0:
        atras = abs(dias)
        return "venció ayer" if atras == 1 else f"venció hace {atras} días"

    if dias == 0:
        return "vence hoy"

    return "vence mañana" if dias == 1 else f"vence en {dias} días"


def _descripcion_alerta(deuda: Deuda) -> str:
    """Nombre, plazo y pago mínimo de una deuda con recordatorio pendiente."""

    detalle = f"{deuda.nombre} ({_plazo(deuda)}"

    if deuda.pago_minimo:
        detalle += f", mínimo {formatear_dinero(deuda.pago_minimo)}"

    return detalle + ")"


def _color_alerta(deuda: Deuda) -> str:
    """Color del recordatorio según su urgencia."""

    if deuda.alerta() == ALERTA_VENCIDA:
        return tema.NEGATIVO

    if deuda.alerta() == ALERTA_PROXIMA:
        return tema.PELIGRO_TEXTO

    return tema.TEXTO_ETIQUETA


class DeudasWidget(PaginaListado):
    """Página de gestión de deudas."""

    ESPACIADO_PAGINA = 20

    def __init__(self, parent=None):
        super().__init__(parent)

        self._crear_interfaz()
        self.actualizar()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        boton_nueva = QPushButton("＋ Nueva deuda")
        boton_nueva.clicked.connect(self._nueva_deuda)

        self.titulo_pagina("💳 Mis deudas", boton_nueva)

        self.alerta_label = QLabel()
        self.alerta_label.setWordWrap(True)
        self.alerta_label.setVisible(False)
        self.layout_principal.addWidget(self.alerta_label)

        self.resumen_label = QLabel("Total pendiente: $ 0")
        self.resumen_label.setWordWrap(True)
        self.resumen_label.setStyleSheet(
            f"color: {tema.TEXTO_ETIQUETA}; font-size: 14px;"
        )
        self.layout_principal.addWidget(self.resumen_label)

        self.agregar_area()
        self.aplicar_estilos()

    def estilos_extra(self) -> str:
        return tema.estilo_boton_primario()

    # ======================================================
    # ACTUALIZACIÓN
    # ======================================================

    def actualizar(self) -> None:
        """Recarga las deudas, su resumen y sus recordatorios."""

        self.limpiar_listado()

        deudas = obtener_deudas()

        total_pendiente = sum(
            deuda.saldo_pendiente for deuda in deudas if not deuda.pagada
        )

        self.resumen_label.setText(
            "Total pendiente: " + formatear_dinero(total_pendiente)
        )

        self._actualizar_alerta(deudas)

        if not deudas:
            self.mostrar_mensaje("Todavía no tienes deudas registradas.")
            return

        for deuda in deudas:
            self.agregar_tarjeta(self._crear_tarjeta(deuda))

    def _actualizar_alerta(self, deudas: list[Deuda]) -> None:
        """Resume en un aviso las deudas con pago vencido o por vencer."""

        alertadas = [deuda for deuda in deudas if deuda.requiere_atencion()]

        if not alertadas:
            self.alerta_label.setVisible(False)
            return

        vencidas = sum(
            1 for deuda in alertadas if deuda.alerta() == ALERTA_VENCIDA
        )
        por_vencer = len(alertadas) - vencidas

        partes = []

        if vencidas:
            partes.append(_contar(vencidas, "vencido", "vencidos"))

        if por_vencer:
            partes.append(_contar(por_vencer, "por vencer", "por vencer"))

        nombradas = "; ".join(
            _descripcion_alerta(deuda)
            for deuda in alertadas[:MAXIMO_ALERTAS_NOMBRADAS]
        )

        restantes = len(alertadas) - MAXIMO_ALERTAS_NOMBRADAS

        if restantes > 0:
            nombradas += f" y {_contar(restantes, 'más', 'más')}"

        self.alerta_label.setText(
            f"⏰ {_contar(len(alertadas), 'pago requiere', 'pagos requieren')} "
            f"atención ({' y '.join(partes)}): {nombradas}"
        )
        self.alerta_label.setStyleSheet(
            _estilo_alerta(bool(vencidas))
        )
        self.alerta_label.setVisible(True)

    # ======================================================
    # TARJETA DE DEUDA
    # ======================================================

    def _crear_tarjeta(self, deuda: Deuda) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setStyleSheet(tema.estilo_tarjeta())

        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        nombre = QLabel(f"💳 {deuda.nombre}")
        nombre.setWordWrap(True)
        nombre.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {tema.TEXTO_TITULO};"
        )
        layout.addWidget(nombre)

        layout.addLayout(
            tema.rejilla_datos(
                (
                    ("Deuda inicial", formatear_dinero(deuda.monto_inicial)),
                    ("Abonado", formatear_dinero(deuda.total_abonado)),
                    ("Pendiente", formatear_dinero(deuda.saldo_pendiente)),
                    ("Creada", formatear_fecha(deuda.fecha_creacion)),
                )
            )
        )

        progreso = QProgressBar()
        progreso.setRange(0, 100)
        progreso.setValue(int(deuda.porcentaje))
        progreso.setTextVisible(True)
        progreso.setFormat(formatear_porcentaje(deuda.porcentaje))
        progreso.setStyleSheet(tema.estilo_barra_progreso())
        layout.addWidget(progreso)

        alerta = self._crear_alerta(deuda)

        if alerta is not None:
            layout.addWidget(alerta)

        boton_abono = QPushButton("＋ Registrar abono")
        boton_abono.setStyleSheet(tema.estilo_boton_primario("9px 15px"))

        if deuda.pagada:
            boton_abono.setEnabled(False)
            boton_abono.setText("✅ Deuda pagada")
        else:
            boton_abono.clicked.connect(
                lambda _evento, d=deuda: self._registrar_abono(d)
            )

        boton_historial = QPushButton("🧾 Historial")
        boton_historial.setStyleSheet(tema.estilo_boton_secundario())
        boton_historial.clicked.connect(
            lambda _evento, d=deuda: self._mostrar_historial(d)
        )

        boton_editar = QPushButton("✏️ Editar")
        boton_editar.setToolTip(
            "Corregir los datos de la deuda y su recordatorio de pago"
        )
        boton_editar.setStyleSheet(tema.estilo_boton_secundario())
        boton_editar.clicked.connect(
            lambda _evento, d=deuda: self._editar_deuda(d)
        )

        boton_eliminar = QPushButton("🗑️ Eliminar")
        boton_eliminar.setStyleSheet(tema.estilo_boton_peligro("9px 15px"))
        boton_eliminar.clicked.connect(
            lambda _evento, d=deuda: self._confirmar_eliminacion(d)
        )

        layout.addLayout(
            tema.fila_de_acciones(
                boton_abono,
                boton_historial,
                boton_eliminar,
                boton_editar,
            )
        )

        if deuda.pagada:
            estado = QLabel("🟢 Deuda pagada")
            estado.setStyleSheet(
                f"color: {tema.POSITIVO}; font-weight: bold;"
            )
            layout.addWidget(estado)

        return tarjeta

    def _crear_alerta(self, deuda: Deuda) -> QLabel | None:
        """Línea de recordatorio de la tarjeta, o ``None`` si no hay alerta."""

        if deuda.alerta() == ALERTA_NINGUNA:
            return None

        texto = (
            "⏰ Próximo pago: "
            f"{formatear_fecha(deuda.fecha_proximo_pago)} ({_plazo(deuda)})"
        )

        if deuda.pago_minimo:
            texto += " · Mínimo " + formatear_dinero(deuda.pago_minimo)

        aviso = QLabel(texto)
        aviso.setWordWrap(True)
        aviso.setStyleSheet(
            f"color: {_color_alerta(deuda)}; font-size: 12px; font-weight: bold;"
        )

        return aviso

    # ======================================================
    # ACCIONES
    # ======================================================

    def _nueva_deuda(self) -> None:
        if NuevaDeudaDialog(parent=self).exec():
            self.actualizar()

    def _editar_deuda(self, deuda: Deuda) -> None:
        if NuevaDeudaDialog(deuda, parent=self).exec():
            self.actualizar()

    def _registrar_abono(self, deuda: Deuda) -> None:
        dialogo = AbonoDialog(deuda, parent=self)

        if dialogo.exec():
            self.actualizar()

    def _mostrar_historial(self, deuda: Deuda) -> None:
        dialogo = HistorialAbonosDialog(deuda, self)
        dialogo.exec()

        if dialogo.cambios:
            self.actualizar()

    def _confirmar_eliminacion(self, deuda: Deuda) -> None:
        respuesta = QMessageBox.question(
            self,
            "Eliminar deuda",
            f'¿Seguro que quieres eliminar "{deuda.nombre}"?\n\n'
            "Se eliminará también su historial de abonos y los movimientos "
            "registrados por esos abonos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        try:
            eliminada = eliminar_deuda(deuda.id)
        except Exception as error:  # pragma: no cover - error de persistencia
            logger.exception("No se pudo eliminar la deuda.")
            QMessageBox.critical(
                self,
                "No se pudo eliminar",
                f"Ocurrió un error al eliminar la deuda:\n{error}",
            )
            return

        if not eliminada:
            QMessageBox.warning(
                self,
                "Deuda no encontrada",
                "La deuda ya no existe en la base de datos.",
            )

        self.actualizar()


def _estilo_alerta(vencida: bool) -> str:
    """Hoja del aviso superior, atenuado cuando no hay nada vencido."""

    if vencida:
        return (
            f"background-color: {tema.PELIGRO_FONDO};"
            f" color: {tema.PELIGRO_TEXTO};"
            " border-radius: 12px; padding: 12px; font-size: 13px;"
            " font-weight: bold;"
        )

    return (
        f"background-color: {tema.MORADO_CLARO};"
        f" color: {tema.TEXTO_TITULO};"
        " border-radius: 12px; padding: 12px; font-size: 13px;"
    )
