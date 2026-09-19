"""Diálogo de alta y edición de deudas."""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QWidget,
)

from models.deuda import Deuda
from services.deudas_service import actualizar_deuda, crear_deuda
from ui import tema
from ui.dialogo_formulario import DialogoFormulario
from utils.dinero import formatear_dinero

# Antelación propuesta al programar un recordatorio nuevo.
DIAS_RECORDATORIO_POR_DEFECTO = 15


class NuevaDeudaDialog(DialogoFormulario):
    """Formulario de registro y de corrección de una deuda.

    El mismo formulario sirve para las dos operaciones: al editar se recibe la
    deuda y se rellenan sus valores. La alerta de próximo pago se configura
    aquí, tanto al crear una deuda como después, que es el caso habitual.
    """

    ANCHO = 470

    # El padre se recibe por nombre: el primer argumento posicional es la deuda
    # que se edita, y un segundo posicional se leería como si lo fuera.
    def __init__(self, deuda: Deuda | None = None, *, parent=None):
        super().__init__("Editar deuda" if deuda else "Nueva deuda", parent)

        self.deuda = deuda

        self._crear_interfaz()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText(
            "Ej: Nequi, Addi, préstamo..."
        )

        self.monto_input = QDoubleSpinBox()
        # El mínimo es cero para que el importe deba escribirse: un mínimo
        # positivo dejaba un valor por defecto que se guardaba sin querer.
        # Los dos decimales son los mismos con los que se persiste el importe:
        # con ningún decimal, editar una deuda registrada con centavos la
        # redondearía en silencio al guardarla.
        self.monto_input.setRange(0.0, 9_999_999_999)
        self.monto_input.setDecimals(2)
        self.monto_input.setPrefix("$ ")
        self.monto_input.setSingleStep(10000)

        self.fecha_input = QDateEdit()
        self.fecha_input.setCalendarPopup(True)
        self.fecha_input.setDisplayFormat("dd/MM/yyyy")
        self.fecha_input.setDate(QDate.currentDate())

        self.descripcion_input = QTextEdit()
        self.descripcion_input.setPlaceholderText("Descripción opcional...")
        self.descripcion_input.setFixedHeight(75)

        self.pago_minimo_input = QDoubleSpinBox()
        self.pago_minimo_input.setRange(0.0, 9_999_999_999)
        self.pago_minimo_input.setDecimals(2)
        self.pago_minimo_input.setPrefix("$ ")
        self.pago_minimo_input.setSingleStep(10000)
        # Con el valor mínimo, el campo anuncia que no hay pago mínimo exigido
        # en lugar de mostrar un cero ambiguo.
        self.pago_minimo_input.setSpecialValueText("Sin mínimo")
        self.pago_minimo_input.setToolTip(
            "Importe que esperas pagar en el próximo vencimiento. "
            "Opcional."
        )

        self.formulario.addRow("Nombre:", self.nombre_input)
        self.formulario.addRow("Monto inicial:", self.monto_input)
        self.formulario.addRow("Fecha de creación:", self.fecha_input)
        self.formulario.addRow("Descripción:", self.descripcion_input)
        self.formulario.addRow("Pago mínimo:", self.pago_minimo_input)
        self.formulario.addRow("Recordatorio:", self._crear_recordatorio())

        self.agregar_formulario()
        self._agregar_resumen_abonado()
        self.agregar_botonera(
            "Guardar cambios" if self.deuda else "Guardar deuda",
            self.guardar_deuda,
        )

        if self.deuda is not None:
            self._cargar_deuda()

        self.aplicar_estilos()

    def _crear_recordatorio(self) -> QWidget:
        """Casilla que habilita la fecha y campo de fecha del aviso."""

        self.recordatorio_check = QCheckBox("Avisar del próximo pago")
        self.recordatorio_check.setToolTip(
            "Sin fecha no se muestra ninguna alerta."
        )

        self.proximo_pago_input = QDateEdit()
        self.proximo_pago_input.setCalendarPopup(True)
        self.proximo_pago_input.setDisplayFormat("dd/MM/yyyy")
        self.proximo_pago_input.setDate(
            QDate.currentDate().addDays(DIAS_RECORDATORIO_POR_DEFECTO)
        )
        self.proximo_pago_input.setEnabled(False)

        self.recordatorio_check.toggled.connect(
            self.proximo_pago_input.setEnabled
        )

        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(10)
        fila.addWidget(self.recordatorio_check)
        fila.addWidget(self.proximo_pago_input, 1)

        return contenedor

    def _agregar_resumen_abonado(self) -> None:
        """Nota con lo ya abonado, que acota el monto inicial editable."""

        if self.deuda is None or self.deuda.total_abonado <= 0:
            return

        abonado = QLabel(
            "Abonado hasta ahora: "
            + formatear_dinero(self.deuda.total_abonado)
            + ". El monto inicial no puede quedar por debajo de esa cifra."
        )
        abonado.setWordWrap(True)
        abonado.setStyleSheet(tema.estilo_texto_secundario(12))
        self.layout_principal.addWidget(abonado)

    def _cargar_deuda(self) -> None:
        """Vuelca en el formulario los datos de la deuda que se edita."""

        deuda = self.deuda

        self.nombre_input.setText(deuda.nombre)
        self.monto_input.setValue(deuda.monto_inicial)
        self.descripcion_input.setPlainText(deuda.descripcion)

        if deuda.fecha_creacion is not None:
            self.fecha_input.setDate(QDate(deuda.fecha_creacion))

        if deuda.pago_minimo:
            self.pago_minimo_input.setValue(deuda.pago_minimo)

        if deuda.fecha_proximo_pago is not None:
            self.recordatorio_check.setChecked(True)
            self.proximo_pago_input.setDate(QDate(deuda.fecha_proximo_pago))

    # ======================================================
    # GUARDAR
    # ======================================================

    def guardar_deuda(self) -> None:
        nombre = self.nombre_input.text().strip()

        if not nombre:
            QMessageBox.warning(
                self,
                "Falta información",
                "Por favor, escribe el nombre de la deuda.",
            )
            self.nombre_input.setFocus()
            return

        datos = {
            "nombre": nombre,
            "monto_inicial": self.monto_input.value(),
            "fecha_creacion": self.fecha_input.date().toPython(),
            "descripcion": self.descripcion_input.toPlainText().strip(),
            "pago_minimo": self.pago_minimo_input.value(),
            "fecha_proximo_pago": (
                self.proximo_pago_input.date().toPython()
                if self.recordatorio_check.isChecked()
                else None
            ),
        }

        if self.deuda is None:
            self.persistir(
                lambda: crear_deuda(**datos),
                descripcion="No se pudo guardar la deuda.",
            )
            return

        self.persistir(
            lambda: actualizar_deuda(self.deuda.id, **datos),
            descripcion="No se pudo guardar la deuda.",
        )
