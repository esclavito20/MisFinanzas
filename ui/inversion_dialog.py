"""Diálogo de alta de inversiones con previsión de rendimiento en vivo."""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
)

from models.inversion import (
    ETIQUETAS_TIPO,
    RETENCION_POR_DEFECTO,
    TIPO_CDT,
    TIPOS_VALIDOS,
    Inversion,
)
from services.inversiones_service import crear_inversion
from ui import tema
from ui.dialogo_formulario import DialogoFormulario
from utils.dinero import formatear_dinero, redondear

PLAZO_MAXIMO_DIAS = 3650
# Horizonte de referencia para ilustrar el rendimiento de las cajitas, que no
# tienen vencimiento pactado.
DIAS_PREVISION_CAJITA = 30


class NuevaInversionDialog(DialogoFormulario):
    """Formulario de registro de un CDT o una cajita de ahorro."""

    ANCHO = 480

    def __init__(self, parent=None):
        super().__init__("Nueva inversión", parent)

        self._crear_interfaz()
        self._actualizar_tipo()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        self.tipo_input = QComboBox()
        for tipo in TIPOS_VALIDOS:
            self.tipo_input.addItem(ETIQUETAS_TIPO[tipo], tipo)

        self.entidad_input = QLineEdit()
        self.entidad_input.setPlaceholderText("Ej: Bancolombia, Nu, Davivienda...")

        self.capital_input = QDoubleSpinBox()
        # El mínimo es cero para que el monto deba escribirse.
        self.capital_input.setRange(0.0, 9_999_999_999)
        self.capital_input.setDecimals(2)
        self.capital_input.setPrefix("$ ")
        self.capital_input.setSingleStep(100000)

        self.tasa_input = QDoubleSpinBox()
        self.tasa_input.setRange(0.0, 100.0)
        self.tasa_input.setDecimals(2)
        self.tasa_input.setSuffix(" % E.A.")
        self.tasa_input.setSingleStep(0.5)

        self.plazo_input = QSpinBox()
        self.plazo_input.setRange(1, PLAZO_MAXIMO_DIAS)
        self.plazo_input.setValue(180)
        self.plazo_input.setSuffix(" días")

        self.fecha_input = QDateEdit()
        self.fecha_input.setCalendarPopup(True)
        self.fecha_input.setDisplayFormat("dd/MM/yyyy")
        self.fecha_input.setDate(QDate.currentDate())

        self.retencion_input = QDoubleSpinBox()
        self.retencion_input.setRange(0.0, 99.0)
        self.retencion_input.setDecimals(2)
        self.retencion_input.setValue(RETENCION_POR_DEFECTO)
        self.retencion_input.setSuffix(" %")
        self.retencion_input.setToolTip(
            "Retención en la fuente sobre el rendimiento. "
            "Verifica la tasa vigente antes de darla por definitiva."
        )

        self.descripcion_input = QLineEdit()
        self.descripcion_input.setPlaceholderText("Descripción opcional...")

        self.formulario.addRow("Tipo:", self.tipo_input)
        self.formulario.addRow("Entidad:", self.entidad_input)
        self.formulario.addRow("Monto invertido:", self.capital_input)
        self.formulario.addRow("Rentabilidad:", self.tasa_input)
        self.formulario.addRow("Plazo:", self.plazo_input)
        self.formulario.addRow("Fecha de inicio:", self.fecha_input)
        self.formulario.addRow("Retención:", self.retencion_input)
        self.formulario.addRow("Descripción:", self.descripcion_input)

        self.agregar_formulario()

        self.prevision_label = QLabel()
        self.prevision_label.setWordWrap(True)
        self.prevision_label.setStyleSheet(
            f"color: {tema.TEXTO_TITULO}; background-color: {tema.MORADO_CLARO};"
            f" border-radius: 10px; padding: 10px; font-size: 12px;"
        )
        self.layout_principal.addWidget(self.prevision_label)

        self.tipo_input.currentIndexChanged.connect(
            lambda _indice: self._actualizar_tipo()
        )

        for campo in (
            self.capital_input,
            self.tasa_input,
            self.retencion_input,
        ):
            campo.valueChanged.connect(
                lambda _valor: self._actualizar_prevision()
            )

        self.plazo_input.valueChanged.connect(
            lambda _valor: self._actualizar_prevision()
        )

        self.agregar_botonera("Guardar inversión", self.guardar_inversion)
        self.aplicar_estilos()

    # ======================================================
    # CÁLCULO EN VIVO
    # ======================================================

    def _es_plazo_fijo(self) -> bool:
        return self.tipo_input.currentData() == TIPO_CDT

    def _actualizar_tipo(self) -> None:
        """El plazo solo aplica a productos con vencimiento pactado."""

        self.formulario.setRowVisible(self.plazo_input, self._es_plazo_fijo())
        self._actualizar_prevision()

    def _inversion_provisional(self) -> Inversion:
        """Instancia sin persistir con los datos actuales del formulario."""

        return Inversion(
            id=0,
            tipo=self.tipo_input.currentData(),
            capital=redondear(self.capital_input.value()),
            tasa_ea=self.tasa_input.value(),
            fecha_inicio=self.fecha_input.date().toPython(),
            entidad=self.entidad_input.text().strip(),
            plazo_dias=(
                self.plazo_input.value() if self._es_plazo_fijo() else None
            ),
            retencion_porcentaje=self.retencion_input.value(),
        )

    def _actualizar_prevision(self) -> None:
        """Muestra el rendimiento estimado mientras se edita el formulario."""

        inversion = self._inversion_provisional()

        if inversion.capital <= 0 or inversion.tasa_ea <= 0:
            self.prevision_label.setText(
                "Escribe el monto y la rentabilidad para ver el cálculo "
                "del rendimiento."
            )
            return

        if self._es_plazo_fijo():
            bruto = inversion.rendimiento_bruto_proyectado()
            neto = inversion.rendimiento_proyectado()
            self.prevision_label.setText(
                f"📈 Al vencimiento ({inversion.plazo_dias} días): "
                f"{formatear_dinero(neto)} de rendimiento neto "
                f"· bruto {formatear_dinero(bruto)} "
                f"· valor final {formatear_dinero(inversion.valor_proyectado())}"
            )
            return

        bruto = redondear(
            inversion.valor_futuro(DIAS_PREVISION_CAJITA) - inversion.capital
        )
        neto = redondear(
            bruto * (1 - inversion.retencion_porcentaje / 100)
        )
        self.prevision_label.setText(
            f"📈 Rendimiento estimado en {DIAS_PREVISION_CAJITA} días: "
            f"{formatear_dinero(neto)} neto · bruto {formatear_dinero(bruto)}"
        )

    # ======================================================
    # GUARDAR
    # ======================================================

    def guardar_inversion(self) -> None:
        self.persistir(
            lambda: crear_inversion(
                tipo=self.tipo_input.currentData(),
                capital=self.capital_input.value(),
                tasa_ea=self.tasa_input.value(),
                fecha_inicio=self.fecha_input.date().toPython(),
                entidad=self.entidad_input.text(),
                plazo_dias=(
                    self.plazo_input.value() if self._es_plazo_fijo() else None
                ),
                retencion_porcentaje=self.retencion_input.value(),
                descripcion=self.descripcion_input.text(),
            ),
            descripcion="No se pudo guardar la inversión.",
        )
