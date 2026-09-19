"""Exportación e importación de todos los datos registrados.

Se manejan dos formatos con propósitos distintos:

* El **documento JSON** es el formato de intercambio. Conserva identificadores,
  relaciones y estados, de modo que exportar e importar devuelve la base al
  mismo estado; incluye un manifiesto con la versión del formato para poder
  evolucionar sin romper archivos antiguos.
* Los **CSV** son una salida de solo lectura, una por tabla, para revisar los
  datos en una hoja de cálculo. No se importan.

La importación **reemplaza** todo el contenido. Por ese motivo valida el archivo
por completo antes de tocar nada, crea un respaldo previo y aplica los cambios
dentro de una única transacción: un archivo defectuoso no puede dejar la base a
medias ni sin posibilidad de revertir.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime
from pathlib import Path

import config
from database import respaldo
from database.conexion import conexion, transaccion
from models.paquete_datos import (
    CLAVES_OBLIGATORIAS,
    ESTRUCTURA,
    ETIQUETAS_RESUELTAS,
    FORMATO_VERSION,
    NOMBRE_APLICACION,
    TABLAS_EN_ORDEN,
    TIPO_ENTERO,
    TIPO_FECHA,
    TIPO_NUMERO,
    PaqueteDatos,
    ResultadoExportacion,
    ResultadoImportacion,
    ResumenDatos,
)

logger = logging.getLogger(__name__)

NOMBRE_ARCHIVO = "MisFinanzas_datos"
SUFIJO_CSV = "_csv"
# Los CSV existen únicamente para revisarlos en una hoja de cálculo, así que se
# escriben con la convención regional española: punto y coma como separador de
# campos y coma como separador decimal. Con el estándar anglosajón (coma y
# punto) Excel en español abriría todo el contenido en una sola columna. El
# formato de intercambio con precisión completa es el JSON.
DELIMITADOR_CSV = ";"
DECIMALES_CSV = 2
CODIFICACION = "utf-8"
# El BOM inicial permite que Excel reconozca los acentos sin configuración.
CODIFICACION_CSV = "utf-8-sig"

# Relaciones que la validación debe comprobar antes de escribir nada.
# (tabla, columna, tabla referenciada, admite nulos)
REFERENCIAS = (
    ("abonos", "deuda_id", "deudas", False),
    ("movimientos", "categoria_id", "categorias", True),
    ("movimientos", "abono_id", "abonos", True),
    ("movimientos", "suscripcion_id", "suscripciones", True),
)


class ErrorDatos(Exception):
    """Falla controlada de una exportación o una importación."""


class ArchivoInvalido(ErrorDatos):
    """El archivo no corresponde al formato de intercambio."""


# =========================================================================
# Exportación
# =========================================================================


def nombre_sugerido(momento: date | None = None) -> str:
    """Nombre de archivo propuesto al usuario."""

    return f"{NOMBRE_ARCHIVO}_{(momento or date.today()).isoformat()}.json"


def exportar(ruta_json: Path, con_csv: bool = True) -> ResultadoExportacion:
    """Escribe todos los datos en el archivo indicado y, si se pide, en CSV."""

    tablas = _leer_tablas()
    momento = datetime.now().isoformat(timespec="seconds")
    resumen = ResumenDatos(
        conteos={tabla: len(filas) for tabla, filas in tablas.items()},
        exportado_en=momento,
        version_aplicacion=config.VERSION,
    )

    documento = {
        "aplicacion": NOMBRE_APLICACION,
        "version_aplicacion": config.VERSION,
        "version_formato": FORMATO_VERSION,
        "exportado_en": momento,
        "conteos": resumen.conteos,
        "tablas": tablas,
    }

    try:
        ruta_json.parent.mkdir(parents=True, exist_ok=True)
        ruta_json.write_text(
            json.dumps(documento, ensure_ascii=False, indent=2),
            encoding=CODIFICACION,
        )
    except OSError as error:
        raise ErrorDatos(
            f"No se pudo escribir el archivo de datos: {error}"
        ) from error

    rutas_csv = _exportar_csv(ruta_json, tablas) if con_csv else ()

    logger.info(
        "Datos exportados en %s (%s registros)",
        ruta_json,
        resumen.total,
    )

    return ResultadoExportacion(
        ruta_json=ruta_json,
        rutas_csv=rutas_csv,
        resumen=resumen,
    )


def resumen_actual() -> ResumenDatos:
    """Cuantifica el contenido de la base en uso, sin escribir archivo alguno.

    Permite contrastar el estado local con el de una copia compartida antes de
    decidir en qué dirección sincronizar. No se fija ``exportado_en`` porque
    nada se ha exportado: el resumen describe la base tal como está ahora.
    """

    return ResumenDatos(
        conteos=_contar_tablas(),
        version_aplicacion=config.VERSION,
    )


def _contar_tablas() -> dict[str, int]:
    """Cuenta los registros de cada tabla sin llegar a leerlos.

    El resumen de la sincronización solo necesita cantidades: materializar todas
    las filas para contarlas costaría memoria proporcional al tamaño de la base,
    que puede crecer sin límite con los años de movimientos.
    """

    with conexion() as con:
        _asegurar_esquema_compatible(con)

        return {
            tabla: con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            for tabla in TABLAS_EN_ORDEN
        }


def _leer_tablas() -> dict[str, list[dict]]:
    """Instantánea consistente de todas las tablas, en orden de dependencia."""

    with conexion() as con:
        _asegurar_esquema_compatible(con)

        return {
            tabla: [
                {columna.nombre: fila[columna.nombre] for columna in ESTRUCTURA[tabla]}
                for fila in con.execute(f"SELECT * FROM {tabla} ORDER BY id")
            ]
            for tabla in TABLAS_EN_ORDEN
        }


def _asegurar_esquema_compatible(con) -> None:
    """Comprueba que la base tiene exactamente el esquema que declara el formato.

    Exportar columnas que el formato no declara produciría un archivo que su
    propio lector rechazaría, y omitir columnas existentes perdería datos.
    """

    for tabla in TABLAS_EN_ORDEN:
        reales = {
            fila["name"] for fila in con.execute(f"PRAGMA table_info({tabla})")
        }
        declaradas = {columna.nombre for columna in ESTRUCTURA[tabla]}

        if reales != declaradas:
            raise ErrorDatos(
                f"La tabla «{tabla}» no coincide con el formato declarado "
                f"(columnas ausentes: {sorted(declaradas - reales) or 'ninguna'}; "
                f"columnas no declaradas: {sorted(reales - declaradas) or 'ninguna'})."
            )


def _exportar_csv(
    ruta_json: Path,
    tablas: dict[str, list[dict]],
) -> tuple[Path, ...]:
    """Escribe una hoja por tabla junto al archivo de intercambio."""

    directorio = ruta_json.with_name(f"{ruta_json.stem}{SUFIJO_CSV}")

    try:
        directorio.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ErrorDatos(
            f"No se pudo crear la carpeta de hojas de cálculo: {error}"
        ) from error

    indice = {
        tabla: {fila["id"]: fila for fila in filas}
        for tabla, filas in tablas.items()
    }

    rutas: list[Path] = []

    for tabla in TABLAS_EN_ORDEN:
        ruta = directorio / f"{tabla}.csv"

        try:
            with ruta.open("w", encoding=CODIFICACION_CSV, newline="") as archivo:
                escritor = csv.writer(archivo, delimiter=DELIMITADOR_CSV)
                escritor.writerow(_encabezado_csv(tabla))

                for fila in tablas[tabla]:
                    escritor.writerow(_fila_csv(tabla, fila, indice))
        except OSError as error:
            raise ErrorDatos(
                f"No se pudo escribir la hoja «{tabla}.csv»: {error}"
            ) from error

        rutas.append(ruta)

    return tuple(rutas)


def _encabezado_csv(tabla: str) -> list[str]:
    return [columna.nombre for columna in ESTRUCTURA[tabla]] + [
        encabezado for _, _, _, encabezado in ETIQUETAS_RESUELTAS.get(tabla, ())
    ]


def _fila_csv(
    tabla: str,
    fila: dict,
    indice: dict[str, dict[int, dict]],
) -> list[object]:
    valores = [
        _valor_csv(columna, fila[columna.nombre])
        for columna in ESTRUCTURA[tabla]
    ]

    for columna, destino, legible, _ in ETIQUETAS_RESUELTAS.get(tabla, ()):
        referencia = fila[columna]
        relacionada = indice.get(destino, {}).get(referencia) if referencia else None
        valores.append(relacionada[legible] if relacionada else "")

    return valores


def _valor_csv(columna, valor: object) -> object:
    """Presenta un valor con la convención decimal local."""

    if valor is None:
        return ""

    if columna.tipo == TIPO_NUMERO:
        return f"{float(valor):.{DECIMALES_CSV}f}".replace(".", ",")

    return valor


# =========================================================================
# Lectura y validación del archivo de intercambio
# =========================================================================


def leer_paquete(ruta: Path) -> PaqueteDatos:
    """Lee y valida un archivo de intercambio."""

    if not ruta.exists():
        raise ErrorDatos(f"El archivo no existe: {ruta}")

    try:
        texto = ruta.read_text(encoding=CODIFICACION)
    except (OSError, UnicodeDecodeError) as error:
        raise ArchivoInvalido(f"No se pudo leer el archivo: {error}") from error

    try:
        documento = json.loads(texto)
    except json.JSONDecodeError as error:
        raise ArchivoInvalido(
            f"El archivo no es un documento JSON válido (línea {error.lineno})."
        ) from error

    tablas, resumen = _validar_documento(documento)

    return PaqueteDatos(tablas=tablas, resumen=resumen)


def _validar_documento(documento: object) -> tuple[dict[str, list[dict]], ResumenDatos]:
    if not isinstance(documento, dict):
        raise ArchivoInvalido(
            "El contenido no corresponde a un paquete de datos de "
            f"{NOMBRE_APLICACION}."
        )

    faltantes = [clave for clave in CLAVES_OBLIGATORIAS if clave not in documento]

    if faltantes:
        raise ArchivoInvalido(
            f"Al archivo le falta la sección «{faltantes[0]}»."
        )

    aplicacion = documento.get("aplicacion")

    if aplicacion != NOMBRE_APLICACION:
        raise ArchivoInvalido(
            f"El archivo lo generó «{aplicacion}», no {NOMBRE_APLICACION}."
        )

    version = documento.get("version_formato")

    if not isinstance(version, int) or isinstance(version, bool):
        raise ArchivoInvalido("El archivo no declara una versión de formato válida.")

    if version > FORMATO_VERSION:
        raise ArchivoInvalido(
            "El archivo se generó con una versión más reciente de la "
            "aplicación. Actualízala antes de importarlo."
        )

    tablas_crudas = documento.get("tablas")

    if not isinstance(tablas_crudas, dict):
        raise ArchivoInvalido("La sección «tablas» del archivo no es válida.")

    ausentes = [tabla for tabla in TABLAS_EN_ORDEN if tabla not in tablas_crudas]

    if ausentes:
        raise ArchivoInvalido(
            f"El archivo no contiene la tabla «{ausentes[0]}»."
        )

    desconocidas = [tabla for tabla in tablas_crudas if tabla not in ESTRUCTURA]

    if desconocidas:
        raise ArchivoInvalido(
            f"El archivo contiene la tabla desconocida «{desconocidas[0]}»."
        )

    tablas = {
        tabla: _validar_tabla(tabla, tablas_crudas[tabla])
        for tabla in TABLAS_EN_ORDEN
    }

    _validar_referencias(tablas)

    resumen = ResumenDatos(
        conteos={tabla: len(filas) for tabla, filas in tablas.items()},
        exportado_en=str(documento.get("exportado_en") or ""),
        version_aplicacion=str(documento.get("version_aplicacion") or ""),
        version_formato=version,
    )

    return tablas, resumen


def _validar_tabla(tabla: str, filas: object) -> list[dict]:
    if not isinstance(filas, list):
        raise ArchivoInvalido(f"La tabla «{tabla}» no es una lista de registros.")

    columnas = ESTRUCTURA[tabla]
    esperadas = {columna.nombre for columna in columnas}
    obligatorias = {
        columna.nombre for columna in columnas if not columna.opcional
    }
    identificadores: set[int] = set()
    validadas: list[dict] = []

    for numero, fila in enumerate(filas, start=1):
        if not isinstance(fila, dict):
            raise ArchivoInvalido(
                f"El registro {numero} de «{tabla}» no es un objeto de datos."
            )

        # Un archivo de una versión anterior del formato puede carecer de las
        # columnas opcionales incorporadas después; se reconstruyen vacías. Las
        # columnas desconocidas, en cambio, se rechazan: indican que el archivo
        # no corresponde a este formato.
        presentes = set(fila)
        ausentes = obligatorias - presentes
        desconocidas = presentes - esperadas

        if ausentes or desconocidas:
            raise ArchivoInvalido(
                f"El registro {numero} de «{tabla}» no tiene las columnas "
                "esperadas "
                f"(faltan: {sorted(ausentes) or 'ninguna'}; "
                f"sobran: {sorted(desconocidas) or 'ninguna'})."
            )

        valores = {
            columna.nombre: _convertir(
                tabla,
                columna,
                fila.get(columna.nombre),
                numero,
            )
            for columna in columnas
        }

        if valores["id"] in identificadores:
            raise ArchivoInvalido(
                f"El identificador {valores['id']} está repetido en «{tabla}»."
            )

        identificadores.add(valores["id"])
        validadas.append(valores)

    return validadas


def _convertir(tabla: str, columna, valor: object, numero: int) -> object:
    """Comprueba el tipo de un valor y lo normaliza."""

    if valor is None:
        if columna.opcional:
            return None

        raise ArchivoInvalido(
            f"El campo «{columna.nombre}» del registro {numero} de «{tabla}» "
            "no admite vacío."
        )

    if columna.tipo == TIPO_ENTERO:
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise _error_de_tipo(tabla, columna, numero, "un número entero")

        return valor

    if columna.tipo == TIPO_NUMERO:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise _error_de_tipo(tabla, columna, numero, "un número")

        return float(valor)

    if columna.tipo == TIPO_FECHA:
        if not isinstance(valor, str):
            raise _error_de_tipo(tabla, columna, numero, "una fecha ISO")

        try:
            date.fromisoformat(valor)
        except ValueError as error:
            raise ArchivoInvalido(
                f"La fecha «{valor}» del registro {numero} de «{tabla}» no está "
                "en formato AAAA-MM-DD."
            ) from error

        return valor

    if not isinstance(valor, str):
        raise _error_de_tipo(tabla, columna, numero, "texto")

    return valor


def _error_de_tipo(tabla: str, columna, numero: int, esperado: str) -> ArchivoInvalido:
    return ArchivoInvalido(
        f"El campo «{columna.nombre}» del registro {numero} de «{tabla}» debe "
        f"ser {esperado}."
    )


def _validar_referencias(tablas: dict[str, list[dict]]) -> None:
    """Comprueba que ninguna relación apunte a un registro inexistente."""

    for tabla, columna, destino, opcional in REFERENCIAS:
        existentes = {fila["id"] for fila in tablas[destino]}

        for numero, fila in enumerate(tablas[tabla], start=1):
            valor = fila[columna]

            if valor is None:
                continue

            if valor not in existentes:
                raise ArchivoInvalido(
                    f"El registro {numero} de «{tabla}» referencia un "
                    f"«{destino}» inexistente ({valor})."
                )

        if not opcional and any(fila[columna] is None for fila in tablas[tabla]):
            raise ArchivoInvalido(
                f"La tabla «{tabla}» tiene registros sin «{columna}»."
            )


# =========================================================================
# Importación
# =========================================================================


def importar(paquete: PaqueteDatos) -> ResultadoImportacion:
    """Reemplaza todos los datos por los del paquete.

    El respaldo se crea antes de borrar nada y los cambios se aplican en una
    sola transacción, de modo que la base siempre contiene el estado anterior
    completo o el nuevo completo.
    """

    _validar_referencias(paquete.tablas)

    seguridad = respaldo.crear_respaldo_manual()

    with transaccion() as con:
        # El vaciado respeta el orden inverso de dependencia; las claves
        # foráneas están activas durante toda la operación.
        for tabla in reversed(TABLAS_EN_ORDEN):
            con.execute(f"DELETE FROM {tabla}")

        for tabla in TABLAS_EN_ORDEN:
            _insertar(con, tabla, paquete.tablas[tabla])

    logger.info(
        "Datos importados: %s registros%s",
        paquete.resumen.total,
        f" (respaldo en {seguridad})" if seguridad else " (sin respaldo previo)",
    )

    return ResultadoImportacion(resumen=paquete.resumen, ruta_respaldo=seguridad)


def _insertar(con, tabla: str, filas: list[dict]) -> None:
    """Inserta los registros conservando sus identificadores."""

    if not filas:
        return

    columnas = [columna.nombre for columna in ESTRUCTURA[tabla]]
    marcadores = ", ".join("?" * len(columnas))

    con.executemany(
        f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({marcadores})",
        [tuple(fila[columna] for columna in columnas) for fila in filas],
    )
