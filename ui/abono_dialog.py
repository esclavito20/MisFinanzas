"""Diálogo de registro y corrección de abonos sobre una deuda."""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLabel,
    QTextEdit,
)

from models.abono import Abono
from models.deuda import (
    DESPLAZAMIENTOS,
    PERIODO_MENSUAL,
    PERIODO_QUINCENAL,
    PERIODO_SEMANAL,
    Deuda,
    siguiente_vencimiento,
)
from services.deudas_service import (
    QUITAR_RECORDATORIO,
    SIN_CAMBIO,
    actualizar_abono,
    registrar_abono,
)
from ui import tema
from ui.dialogo_formulario import DialogoFormulario
from utils.dinero import formatear_dinero, redondear
from utils.fechas import formatear_fecha


class AbonoDialog(DialogoFormulario):
    """Formulario para aplicar o corregir un pago sobre una deuda.

    Con un abono recibido, el formulario pasa a modo corrección: el tope del
    importe es entonces el saldo pendiente más lo que ese mismo abono aportaba,
    porque corregirlo al alza no puede llevar el total abonado por encima del
    monto inicial de la deuda.
    """

    ANCHO = 450

    # El abono y el padre se reciben por nombre: el primer argumento posicional
    # es la deuda, y un segundo posicional se leería como el abono a editar.
    def __init__(
        self,
        deuda: Deuda,
        *,
        abono: Abono | None = None,
        parent=None,
    ):
        super().__init__("Editar abono" if abono else "Registrar abono", parent)

        self.deuda = deuda
        self.abono = abono

        self._crear_interfaz()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        self.agregar_titulo(f"💳 {self.deuda.nombre}")

        pendiente = QLabel(
            "Saldo pendiente: "
            + formatear_dinero(self.deuda.saldo_pendiente)
        )
        pendiente.setStyleSheet(tema.estilo_texto_secundario(14))
        self.layout_principal.addWidget(pendiente)

        self.valor_input = QDoubleSpinBox()
        # El límite superior conserva los centavos del saldo: al truncarlos a
        # enteros, una deuda con centavos nunca podía liquidarse por completo.
        # El mínimo es cero para que el importe deba escribirse.
        self.valor_input.setRange(0.0, self._maximo())
        self.valor_input.setDecimals(2)
        self.valor_input.setPrefix("$ ")
        self.valor_input.setSingleStep(10000)

        self.fecha_input = QDateEdit()
        self.fecha_input.setCalendarPopup(True)
        self.fecha_input.setDisplayFormat("dd/MM/yyyy")
        self.fecha_input.setDate(QDate.currentDate())

        self.descripcion_input = QTextEdit()
        self.descripcion_input.setPlaceholderText("Ej: Abono mensual...")
        self.descripcion_input.setFixedHeight(75)

        self.formulario.addRow("Valor del abono:", self.valor_input)
        self.formulario.addRow("Fecha:", self.fecha_input)
        self.formulario.addRow("Descripción:", self.descripcion_input)

        self.reprogramacion_input: QComboBox | None = None

        if self._puede_reprogramar():
            self.formulario.addRow(
                "Próximo pago:",
                self._crear_reprogramacion(),
            )

        self.agregar_formulario()
        self.agregar_botonera(
            "Guardar cambios" if self.abono else "Guardar abono",
            self.guardar_abono,
        )

        if self.abono is not None:
            self._cargar_abono()

        self.aplicar_estilos()

    def _puede_reprogramar(self) -> bool:
        """Solo al registrar: corregir un abono no mueve el próximo pago."""

        return self.abono is None and self.deuda.fecha_proximo_pago is not None

    def _crear_reprogramacion(self) -> QComboBox:
        """Selector del próximo pago, con la fecha resultante a la vista."""

        self.reprogramacion_input = QComboBox()
        self.reprogramacion_input.setToolTip(
            "Al guardar se avanza al menos un periodo y se busca siempre una "
            "fecha futura, para no volver a deber el mismo pago."
        )

        for modalidad, etiqueta in (
            (PERIODO_MENSUAL, "Avanzar un mes"),
            (PERIODO_QUINCENAL, "Avanzar 15 días"),
            (PERIODO_SEMANAL, "Avanzar una semana"),
            (SIN_CAMBIO, "Mantener la fecha"),
            (QUITAR_RECORDATORIO, "Quitar el recordatorio"),
        ):
            self.reprogramacion_input.addItem(
                self._etiqueta_reprogramacion(modalidad, etiqueta),
                modalidad,
            )

        return self.reprogramacion_input

    def _etiqueta_reprogramacion(self, modalidad: str, etiqueta: str) -> str:
        """Añade a la opción la fecha en la que quedaría el recordatorio."""

        if modalidad not in DESPLAZAMIENTOS:
            return etiqueta

        meses, dias = DESPLAZAMIENTOS[modalidad]

        return f"{etiqueta} → " + formatear_fecha(
            siguiente_vencimiento(self.deuda.fecha_proximo_pago, meses, dias)
        )

    def _reprogramacion_elegida(self) -> str:
        if self.reprogramacion_input is None:
            return SIN_CAMBIO

        return self.reprogramacion_input.currentData() or SIN_CAMBIO

    def _maximo(self) -> float:
        """Importe máximo admitido, según se registre o se corrija."""

        disponible = self.deuda.saldo_pendiente

        if self.abono is not None:
            disponible += self.abono.valor

        return max(redondear(disponible), 0.0)

    def _cargar_abono(self) -> None:
        """Vuelca en el formulario los datos del abono que se corrige."""

        self.valor_input.setValue(self.abono.valor)
        self.fecha_input.setDate(QDate(self.abono.fecha))
        self.descripcion_input.setPlainText(self.abono.descripcion)

    # ======================================================
    # GUARDAR
    # ======================================================

    def guardar_abono(self) -> None:
        valor = self.valor_input.value()
        fecha = self.fecha_input.date().toPython()
        descripcion = self.descripcion_input.toPlainText().strip()

        if self.abono is None:
            self.persistir(
                lambda: registrar_abono(
                    deuda_id=self.deuda.id,
                    valor=valor,
                    fecha=fecha,
                    descripcion=descripcion,
                    reprogramar=self._reprogramacion_elegida(),
                ),
                descripcion="No se pudo guardar el abono.",
                titulo_validacion="Abono no válido",
            )
            return

        self.persistir(
            lambda: actualizar_abono(
                self.deuda.id,
                self.abono.id,
                valor=valor,
                fecha=fecha,
                descripcion=descripcion,
            ),
            descripcion="No se pudo guardar el abono.",
            titulo_validacion="Abono no válido",
        )
