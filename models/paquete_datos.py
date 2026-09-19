"""Modelos del paquete de datos exportable.

El paquete describe **todas** las tablas del dominio con sus columnas, tipos y
orden de dependencia. Esa declaración es el contrato del formato de intercambio:
de ella se derivan la serialización, la validación al importar y la
reconstrucción de las relaciones, de modo que ninguna de las tres pueda
desincronizarse de las otras.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Aplicación que firma el documento: evita importar un JSON ajeno por error.
NOMBRE_APLICACION = "Mis Finanzas"

# Versión del formato de archivo, independiente de la versión de la aplicación.
# Se incrementa cuando cambia la estructura declarada aquí.
#
# Historial:
# * 1: formato inicial (exportación e importación de todas las tablas).
# * 2: ``deudas`` incorpora ``pago_minimo`` y ``fecha_proximo_pago``, ambos
#   opcionales. Un archivo de la versión 1 sigue importándose: las columnas
#   opcionales ausentes se reconstruyen vacías.
FORMATO_VERSION = 2

TIPO_ENTERO = "entero"
TIPO_NUMERO = "numero"
TIPO_TEXTO = "texto"
TIPO_FECHA = "fecha"

# Tipos que se aceptan para cada columna declarada.
TIPOS_VALIDOS = (TIPO_ENTERO, TIPO_NUMERO, TIPO_TEXTO, TIPO_FECHA)


@dataclass(frozen=True)
class Columna:
    """Columna del formato, con su tipo y si admite nulos."""

    nombre: str
    tipo: str
    opcional: bool = False


# Las tablas se declaran en orden de dependencia: cada una referencia a las
# anteriores. Al reconstruir la base se insertan en este orden y se vacían en el
# inverso, porque las claves foráneas están activas.
ESTRUCTURA: dict[str, tuple[Columna, ...]] = {
    "categorias": (
        Columna("id", TIPO_ENTERO),
        Columna("nombre", TIPO_TEXTO),
        Columna("tipo", TIPO_TEXTO),
        Columna("activa", TIPO_ENTERO),
    ),
    "deudas": (
        Columna("id", TIPO_ENTERO),
        Columna("nombre", TIPO_TEXTO),
        Columna("monto_inicial", TIPO_NUMERO),
        Columna("fecha_creacion", TIPO_FECHA),
        Columna("descripcion", TIPO_TEXTO),
        Columna("estado", TIPO_TEXTO),
        Columna("pago_minimo", TIPO_NUMERO, opcional=True),
        Columna("fecha_proximo_pago", TIPO_FECHA, opcional=True),
    ),
    "suscripciones": (
        Columna("id", TIPO_ENTERO),
        Columna("nombre", TIPO_TEXTO),
        Columna("costo", TIPO_NUMERO),
        Columna("periodicidad", TIPO_TEXTO),
        Columna("dia_facturacion", TIPO_ENTERO),
        Columna("mes_facturacion", TIPO_ENTERO, opcional=True),
        Columna("fecha_inicio", TIPO_FECHA),
        Columna("fecha_fin", TIPO_FECHA, opcional=True),
        Columna("estado", TIPO_TEXTO),
        Columna("descripcion", TIPO_TEXTO),
    ),
    "inversiones": (
        Columna("id", TIPO_ENTERO),
        Columna("tipo", TIPO_TEXTO),
        Columna("entidad", TIPO_TEXTO),
        Columna("capital", TIPO_NUMERO),
        Columna("tasa_ea", TIPO_NUMERO),
        Columna("plazo_dias", TIPO_ENTERO, opcional=True),
        Columna("fecha_inicio", TIPO_FECHA),
        Columna("fecha_vencimiento", TIPO_FECHA, opcional=True),
        Columna("retencion_porcentaje", TIPO_NUMERO),
        Columna("estado", TIPO_TEXTO),
        Columna("descripcion", TIPO_TEXTO),
    ),
    "abonos": (
        Columna("id", TIPO_ENTERO),
        Columna("deuda_id", TIPO_ENTERO),
        Columna("fecha", TIPO_FECHA),
        Columna("valor", TIPO_NUMERO),
        Columna("descripcion", TIPO_TEXTO),
    ),
    "movimientos": (
        Columna("id", TIPO_ENTERO),
        Columna("fecha", TIPO_FECHA),
        Columna("tipo", TIPO_TEXTO),
        Columna("categoria_id", TIPO_ENTERO, opcional=True),
        Columna("descripcion", TIPO_TEXTO),
        Columna("valor", TIPO_NUMERO),
        Columna("abono_id", TIPO_ENTERO, opcional=True),
        Columna("suscripcion_id", TIPO_ENTERO, opcional=True),
    ),
}

TABLAS_EN_ORDEN: tuple[str, ...] = tuple(ESTRUCTURA)

ETIQUETAS_TABLA = {
    "categorias": "Categorías",
    "deudas": "Deudas",
    "abonos": "Abonos",
    "suscripciones": "Suscripciones",
    "inversiones": "Inversiones",
    "movimientos": "Movimientos",
}

# Columnas que el CSV añade resolviendo las claves foráneas, para que una hoja
# de cálculo muestre nombres y no identificadores. Cada entrada declara la
# columna de origen, la tabla referenciada, la columna legible y el encabezado.
ETIQUETAS_RESUELTAS = {
    "abonos": (("deuda_id", "deudas", "nombre", "deuda"),),
    "movimientos": (
        ("categoria_id", "categorias", "nombre", "categoria"),
        ("suscripcion_id", "suscripciones", "nombre", "suscripcion"),
    ),
}

CLAVES_OBLIGATORIAS = ("aplicacion", "version_formato", "tablas")


@dataclass(frozen=True)
class ResumenDatos:
    """Cuantificación del contenido de un paquete o de la base actual."""

    conteos: dict[str, int]
    exportado_en: str = ""
    version_aplicacion: str = ""
    version_formato: int = FORMATO_VERSION

    @property
    def total(self) -> int:
        return sum(self.conteos.values())

    @property
    def vacio(self) -> bool:
        return self.total == 0

    def detalle(self) -> str:
        """Lista legible de las tablas con contenido."""

        lineas = [
            f"· {ETIQUETAS_TABLA.get(tabla, tabla)}: {cantidad}"
            for tabla, cantidad in self.conteos.items()
            if cantidad
        ]

        return "\n".join(lineas) if lineas else "· Sin registros"


@dataclass(frozen=True)
class PaqueteDatos:
    """Contenido de un archivo de intercambio ya validado."""

    tablas: dict[str, list[dict]]
    resumen: ResumenDatos


@dataclass(frozen=True)
class ResultadoExportacion:
    """Rutas generadas por una exportación."""

    ruta_json: Path
    rutas_csv: tuple[Path, ...]
    resumen: ResumenDatos


@dataclass(frozen=True)
class ResultadoImportacion:
    """Efecto de una importación, incluido el respaldo de seguridad."""

    resumen: ResumenDatos
    ruta_respaldo: Path | None = None
