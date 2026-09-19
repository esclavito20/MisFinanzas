"""Diálogo de alta de suscripciones."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
)

from models.suscripcion import (
    DIA_MAXIMO,
    DIA_MINIMO,
    ETIQUETAS_PERIODICIDAD,
    PERIODICIDAD_ANUAL,
    PERIODICIDAD_MENSUAL,
)
from services.suscripciones_service import crear_suscripcion
from ui.dialogo_formulario import DialogoFormulario

MESES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


class NuevaSuscripcionDialog(DialogoFormulario):
    """Formulario de registro de una suscripción recurrente."""

    ANCHO = 470

    def __init__(self, parent=None):
        super().__init__("Nueva suscripción", parent)

        self._crear_interfaz()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        hoy = date.today()

        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Ej: Netflix, Spotify, arriendo...")

        self.costo_input = QDoubleSpinBox()
        # El mínimo es cero para que el costo deba escribirse.
        self.costo_input.setRange(0.0, 9_999_999_999)
        self.costo_input.setDecimals(2)
        self.costo_input.setPrefix("$ ")
        self.costo_input.setSingleStep(10000)

        self.periodicidad_input = QComboBox()
        for periodicidad in (PERIODICIDAD_MENSUAL, PERIODICIDAD_ANUAL):
            self.periodicidad_input.addItem(
                ETIQUETAS_PERIODICIDAD[periodicidad],
                periodicidad,
            )

        self.dia_input = QSpinBox()
        self.dia_input.setRange(DIA_MINIMO, DIA_MAXIMO)
        self.dia_input.setValue(hoy.day)
        self.dia_input.setSuffix(" de cada mes")

        self.mes_input = QComboBox()
        for indice, nombre in enumerate(MESES, start=1):
            self.mes_input.addItem(nombre, indice)
        self.mes_input.setCurrentIndex(hoy.month - 1)

        self.fecha_input = QDateEdit()
        self.fecha_input.setCalendarPopup(True)
        self.fecha_input.setDisplayFormat("dd/MM/yyyy")
        self.fecha_input.setDate(QDate.currentDate())

        self.descripcion_input = QLineEdit()
        self.descripcion_input.setPlaceholderText("Descripción opcional...")

        self.formulario.addRow("Nombre:", self.nombre_input)
        self.formulario.addRow("Costo:", self.costo_input)
        self.formulario.addRow("Facturación:", self.periodicidad_input)
        self.formulario.addRow("Día de pago:", self.dia_input)
        self.formulario.addRow("Mes del cobro:", self.mes_input)
        self.formulario.addRow("Primer cobro desde:", self.fecha_input)
        self.formulario.addRow("Descripción:", self.descripcion_input)

        self.agregar_formulario()

        self.periodicidad_input.currentIndexChanged.connect(
            lambda _indice: self._actualizar_periodicidad()
        )
        self._actualizar_periodicidad()

        self.agregar_botonera("Guardar suscripción", self.guardar_suscripcion)
        self.aplicar_estilos()

    def _actualizar_periodicidad(self) -> None:
        """El mes del cobro solo aplica a los ciclos anuales."""

        es_anual = (
            self.periodicidad_input.currentData() == PERIODICIDAD_ANUAL
        )

        self.formulario.setRowVisible(self.mes_input, es_anual)
        self.dia_input.setSuffix(
            " de cada año" if es_anual else " de cada mes"
        )

    # ======================================================
    # GUARDAR
    # ======================================================

    def guardar_suscripcion(self) -> None:
        self.persistir(
            lambda: crear_suscripcion(
                nombre=self.nombre_input.text(),
                costo=self.costo_input.value(),
                periodicidad=self.periodicidad_input.currentData(),
                dia_facturacion=self.dia_input.value(),
                fecha_inicio=self.fecha_input.date().toPython(),
                mes_facturacion=self.mes_input.currentData(),
                descripcion=self.descripcion_input.text(),
            ),
            descripcion="No se pudo guardar la suscripción.",
        )
