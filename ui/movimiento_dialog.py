"""Diálogo de alta de movimientos."""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLineEdit,
    QMessageBox,
)

from models.movimiento import (
    TIPO_GASTO,
    TIPO_INGRESO,
    Movimiento,
)
from services.categorias_service import obtener_categorias
from services.movimientos_service import guardar_movimiento
from ui.dialogo_formulario import DialogoFormulario


class MovimientoDialog(DialogoFormulario):
    """Formulario de registro de un ingreso o un gasto."""

    # El contenido útil debe conservar el ancho que tenía el formulario antes
    # de adoptar el margen común de los diálogos.
    ANCHO = 420

    def __init__(self, parent=None):
        super().__init__("Nuevo movimiento", parent)

        self._crear_interfaz()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def _crear_interfaz(self) -> None:
        self.tipo = QComboBox()
        self.tipo.addItem("💰 Ingreso", TIPO_INGRESO)
        self.tipo.addItem("💸 Gasto", TIPO_GASTO)

        self.categoria = QComboBox()

        self.valor = QDoubleSpinBox()
        # El mínimo es cero para que el usuario deba escribir el importe: con
        # un mínimo positivo, guardar sin editar el campo registraba un
        # movimiento de un centavo.
        self.valor.setRange(0.0, 9_999_999_999.99)
        self.valor.setDecimals(2)
        self.valor.setPrefix("$ ")
        self.valor.setSingleStep(1000)

        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setDate(QDate.currentDate())

        self.descripcion = QLineEdit()
        self.descripcion.setPlaceholderText(
            "Ejemplo: Salario, almuerzo, transporte..."
        )

        self.formulario.addRow("Tipo:", self.tipo)
        self.formulario.addRow("Categoría:", self.categoria)
        self.formulario.addRow("Valor:", self.valor)
        self.formulario.addRow("Fecha:", self.fecha)
        self.formulario.addRow("Descripción:", self.descripcion)

        self.agregar_formulario()
        self.agregar_botonera("Guardar", self.guardar)

        self.tipo.currentIndexChanged.connect(
            lambda _indice: self._cargar_categorias()
        )

        self._cargar_categorias()
        self.aplicar_estilos()

    # ======================================================
    # COMPORTAMIENTO
    # ======================================================

    def _cargar_categorias(self) -> None:
        """Recarga las categorías disponibles para el tipo seleccionado."""

        self.categoria.clear()

        for categoria in obtener_categorias(self.tipo.currentData()):
            self.categoria.addItem(categoria.nombre, categoria.id)

    def guardar(self) -> None:
        """Valida y persiste el movimiento."""

        categoria_id = self.categoria.currentData()

        if categoria_id is None:
            QMessageBox.warning(
                self,
                "Sin categorías",
                "No hay categorías disponibles para el tipo seleccionado.",
            )
            return

        movimiento = Movimiento(
            fecha=self.fecha.date().toPython(),
            tipo=self.tipo.currentData(),
            valor=self.valor.value(),
            categoria_id=categoria_id,
            descripcion=self.descripcion.text().strip(),
        )

        self.persistir(
            lambda: guardar_movimiento(movimiento),
            descripcion="No se pudo guardar el movimiento.",
        )
