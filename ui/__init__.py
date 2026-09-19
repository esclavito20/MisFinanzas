"""Capa de presentación (PySide6).

Expone las ventanas, páginas y diálogos que componen la interfaz, además de las
dos bases de las que derivan —:class:`~ui.pagina_listado.PaginaListado` y
:class:`~ui.dialogo_formulario.DialogoFormulario`—, de modo que el resto de la
aplicación encuentre aquí el catálogo de piezas disponibles. El módulo
:mod:`ui.tema` permanece accesible como submódulo.
"""

from ui.abono_dialog import AbonoDialog
from ui.actualizacion_dialog import ActualizacionDialog
from ui.analisis_widget import AnalisisWidget
from ui.configuracion_dialog import ConfiguracionDialog
from ui.dashboard_widget import DashboardWidget
from ui.deuda_dialog import NuevaDeudaDialog
from ui.deudas_widget import DeudasWidget
from ui.dialogo_formulario import DialogoFormulario
from ui.grafico_gastos import GraficoGastos
from ui.historial_abonos_dialog import HistorialAbonosDialog
from ui.inversion_dialog import NuevaInversionDialog
from ui.inversiones_widget import InversionesWidget
from ui.movimiento_dialog import MovimientoDialog
from ui.movimientos_widget import MovimientosWidget
from ui.pagina_listado import PaginaListado
from ui.sincronizacion_dialog import SincronizacionDialog
from ui.suscripcion_dialog import NuevaSuscripcionDialog
from ui.suscripciones_widget import SuscripcionesWidget
from ui.ventana_principal import VentanaPrincipal

__all__ = [
    "AbonoDialog",
    "ActualizacionDialog",
    "AnalisisWidget",
    "ConfiguracionDialog",
    "DashboardWidget",
    "DeudasWidget",
    "DialogoFormulario",
    "GraficoGastos",
    "HistorialAbonosDialog",
    "InversionesWidget",
    "MovimientoDialog",
    "MovimientosWidget",
    "NuevaDeudaDialog",
    "NuevaInversionDialog",
    "NuevaSuscripcionDialog",
    "PaginaListado",
    "SincronizacionDialog",
    "SuscripcionesWidget",
    "VentanaPrincipal",
]
