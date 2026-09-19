"""Definición del esquema SQLite, índices y migraciones.

El esquema se crea de forma idempotente y las bases existentes se migran
preservando siempre los datos del usuario:

* ``movimientos`` se reconstruye para incorporar las claves foráneas
  (``categoria_id -> categorias``, ``abono_id -> abonos ON DELETE CASCADE`` y
  ``suscripcion_id -> suscripciones ON DELETE SET NULL``), ya que SQLite no
  permite añadirlas con ``ALTER TABLE``.
* ``abonos`` se reconstruye si carece de la cascada hacia ``deudas``.
* ``deudas`` incorpora las columnas del recordatorio de pago (``pago_minimo`` y
  ``fecha_proximo_pago``) mediante ``ALTER TABLE``, sin reconstruir la tabla.
* Las estructuras antiguas de deudas (``valor_inicial`` / ``activa``) se
  convierten al esquema vigente sin perder información.

La reconstrucción de una tabla exige desactivar temporalmente las claves
foráneas; por ese motivo las migraciones gestionan su propia transacción en
lugar de usar ``database.conexion.transaccion``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import config
from database import respaldo
from database.conexion import conexion
from utils.dinero import redondear

logger = logging.getLogger(__name__)

CATEGORIA_SIN_ASIGNAR = "Sin categoría"

_DDL_CATEGORIAS = """
CREATE TABLE IF NOT EXISTS categorias (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT    NOT NULL,
    tipo   TEXT    NOT NULL,
    activa INTEGER NOT NULL DEFAULT 1
)
"""

_DDL_DEUDAS = """
CREATE TABLE IF NOT EXISTS deudas (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre             TEXT    NOT NULL,
    monto_inicial      REAL    NOT NULL,
    fecha_creacion     TEXT    NOT NULL,
    descripcion        TEXT    NOT NULL DEFAULT '',
    estado             TEXT    NOT NULL DEFAULT 'pendiente',
    pago_minimo        REAL,
    fecha_proximo_pago TEXT
)
"""

_DDL_ABONOS = """
CREATE TABLE IF NOT EXISTS abonos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    deuda_id    INTEGER NOT NULL,
    fecha       TEXT    NOT NULL,
    valor       REAL    NOT NULL,
    descripcion TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (deuda_id) REFERENCES deudas (id) ON DELETE CASCADE
)
"""

_DDL_SUSCRIPCIONES = """
CREATE TABLE IF NOT EXISTS suscripciones (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT    NOT NULL,
    costo            REAL    NOT NULL,
    periodicidad     TEXT    NOT NULL,
    dia_facturacion  INTEGER NOT NULL,
    mes_facturacion  INTEGER,
    fecha_inicio     TEXT    NOT NULL,
    fecha_fin        TEXT,
    estado           TEXT    NOT NULL DEFAULT 'activa',
    descripcion      TEXT    NOT NULL DEFAULT ''
)
"""

_DDL_INVERSIONES = """
CREATE TABLE IF NOT EXISTS inversiones (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo                 TEXT    NOT NULL,
    entidad              TEXT    NOT NULL DEFAULT '',
    capital              REAL    NOT NULL,
    tasa_ea              REAL    NOT NULL,
    plazo_dias           INTEGER,
    fecha_inicio         TEXT    NOT NULL,
    fecha_vencimiento    TEXT,
    retencion_porcentaje REAL    NOT NULL DEFAULT 4,
    estado               TEXT    NOT NULL DEFAULT 'activa',
    descripcion          TEXT    NOT NULL DEFAULT ''
)
"""


def _ddl_movimientos(
    nombre_tabla: str = "movimientos",
    *,
    si_no_existe: bool = False,
) -> str:
    existencia = "IF NOT EXISTS " if si_no_existe else ""

    return f"""
    CREATE TABLE {existencia}{nombre_tabla} (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha          TEXT    NOT NULL,
        tipo           TEXT    NOT NULL,
        categoria_id   INTEGER,
        descripcion    TEXT    NOT NULL DEFAULT '',
        valor          REAL    NOT NULL,
        abono_id       INTEGER,
        suscripcion_id INTEGER,
        FOREIGN KEY (categoria_id)
            REFERENCES categorias (id) ON DELETE SET NULL,
        FOREIGN KEY (abono_id)
            REFERENCES abonos (id) ON DELETE CASCADE,
        FOREIGN KEY (suscripcion_id)
            REFERENCES suscripciones (id) ON DELETE SET NULL
    )
    """


# Columnas incorporadas después de la primera versión del esquema. Se declaran
# aparte para que la creación de tablas y la migración de las bases existentes
# no puedan divergir.
_COLUMNAS_DEUDAS_AGREGADAS = (
    ("pago_minimo", "REAL"),
    ("fecha_proximo_pago", "TEXT"),
)


def _ddl_abonos(nombre_tabla: str) -> str:
    return f"""
    CREATE TABLE {nombre_tabla} (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        deuda_id    INTEGER NOT NULL,
        fecha       TEXT    NOT NULL,
        valor       REAL    NOT NULL,
        descripcion TEXT    NOT NULL DEFAULT '',
        FOREIGN KEY (deuda_id)
            REFERENCES deudas (id) ON DELETE CASCADE
    )
    """


# Cada índice responde a un predicado real de la capa de repositorios.
_INDICES = (
    # Filtros de los agregados mensuales: tipo = ? AND fecha en rango.
    "CREATE INDEX IF NOT EXISTS idx_movimientos_tipo_fecha "
    "ON movimientos (tipo, fecha)",
    # Orden cronológico de los listados.
    "CREATE INDEX IF NOT EXISTS idx_movimientos_fecha "
    "ON movimientos (fecha)",
    # Filtro por categoría en la vista de movimientos.
    "CREATE INDEX IF NOT EXISTS idx_movimientos_categoria "
    "ON movimientos (categoria_id)",
    # Resolución de la cascada al eliminar un abono.
    "CREATE INDEX IF NOT EXISTS idx_movimientos_abono "
    "ON movimientos (abono_id)",
    # Detección del ciclo ya registrado al cobrar una suscripción.
    "CREATE INDEX IF NOT EXISTS idx_movimientos_suscripcion "
    "ON movimientos (suscripcion_id, fecha)",
    # Agregado del saldo por deuda.
    "CREATE INDEX IF NOT EXISTS idx_abonos_deuda "
    "ON abonos (deuda_id)",
    # Selección de categorías activas por tipo.
    "CREATE INDEX IF NOT EXISTS idx_categorias_tipo "
    "ON categorias (tipo, activa)",
    # Proyección de compromisos: solo se agregan las suscripciones activas.
    "CREATE INDEX IF NOT EXISTS idx_suscripciones_estado "
    "ON suscripciones (estado)",
    # Agregado del capital invertido: solo inversiones activas.
    "CREATE INDEX IF NOT EXISTS idx_inversiones_estado "
    "ON inversiones (estado)",
)


def _tabla_existe(con: sqlite3.Connection, nombre_tabla: str) -> bool:
    fila = con.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (nombre_tabla,),
    ).fetchone()

    return fila is not None


def _columnas(con: sqlite3.Connection, nombre_tabla: str) -> set[str]:
    if not _tabla_existe(con, nombre_tabla):
        return set()

    return {
        fila["name"]
        for fila in con.execute(f"PRAGMA table_info({nombre_tabla})")
    }


def _tiene_clave_foranea(
    con: sqlite3.Connection,
    nombre_tabla: str,
    columna: str,
) -> bool:
    if not _tabla_existe(con, nombre_tabla):
        return False

    return any(
        fila["from"] == columna
        for fila in con.execute(f"PRAGMA foreign_key_list({nombre_tabla})")
    )


@contextmanager
def _claves_foraneas_desactivadas(
    con: sqlite3.Connection,
) -> Iterator[None]:
    """Ejecuta una reconstrucción de tabla en una transacción controlada.

    ``PRAGMA foreign_keys`` no surte efecto dentro de una transacción, por lo
    que se desactiva antes de abrirla y se restaura al finalizar.
    """

    con.execute("PRAGMA foreign_keys = OFF")

    try:
        con.execute("BEGIN IMMEDIATE")

        try:
            yield
        except BaseException:
            con.execute("ROLLBACK")
            raise

        con.execute("COMMIT")
    finally:
        con.execute("PRAGMA foreign_keys = ON")


def _crear_tablas_base(con: sqlite3.Connection) -> None:
    con.execute(_DDL_CATEGORIAS)
    con.execute(_DDL_DEUDAS)
    con.execute(_DDL_ABONOS)
    con.execute(_DDL_SUSCRIPCIONES)
    con.execute(_DDL_INVERSIONES)
    con.execute(_ddl_movimientos(si_no_existe=True))


def _migrar_deudas_legacy(con: sqlite3.Connection) -> None:
    """Convierte la estructura antigua de deudas al esquema vigente."""

    columnas = _columnas(con, "deudas")

    if not columnas or "monto_inicial" in columnas:
        return

    logger.info("Migrando estructura antigua de deudas.")

    deudas_legacy = con.execute(
        """
        SELECT id, nombre, valor_inicial, fecha_creacion, activa
        FROM deudas
        ORDER BY id
        """
    ).fetchall()

    abonos_legacy: list[sqlite3.Row] = []

    if _tabla_existe(con, "abonos_deuda"):
        abonos_legacy = con.execute(
            """
            SELECT id, deuda_id, fecha, valor, descripcion
            FROM abonos_deuda
            ORDER BY id
            """
        ).fetchall()

    # Si ya existía la tabla vigente de abonos con datos, prevalece sobre la
    # estructura antigua para no perder información.
    abonos_vigentes: list[sqlite3.Row] = []

    if _tabla_existe(con, "abonos"):
        columnas_abonos = _columnas(con, "abonos")

        if {"id", "deuda_id", "fecha", "valor"}.issubset(columnas_abonos):
            abonos_vigentes = con.execute(
                """
                SELECT id, deuda_id, fecha, valor, descripcion
                FROM abonos
                ORDER BY id
                """
            ).fetchall()

    origen_abonos = abonos_vigentes or abonos_legacy
    ids_vigentes = {fila["id"] for fila in deudas_legacy}
    hoy = date.today().isoformat()

    with _claves_foraneas_desactivadas(con):
        con.execute("DROP TABLE IF EXISTS abonos")
        con.execute("DROP TABLE IF EXISTS abonos_deuda")
        con.execute("DROP TABLE IF EXISTS deudas")
        con.execute(_DDL_DEUDAS)
        con.execute(_DDL_ABONOS)

        for fila in deudas_legacy:
            con.execute(
                """
                INSERT INTO deudas (
                    id, nombre, monto_inicial,
                    fecha_creacion, descripcion, estado
                )
                VALUES (?, ?, ?, ?, '', ?)
                """,
                (
                    fila["id"],
                    fila["nombre"],
                    redondear(fila["valor_inicial"]),
                    fila["fecha_creacion"] or hoy,
                    "pendiente" if fila["activa"] else "pagada",
                ),
            )

        for fila in origen_abonos:
            if fila["deuda_id"] not in ids_vigentes:
                continue

            con.execute(
                """
                INSERT INTO abonos (
                    id, deuda_id, fecha, valor, descripcion
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    fila["id"],
                    fila["deuda_id"],
                    fila["fecha"] or hoy,
                    redondear(fila["valor"]),
                    fila["descripcion"] or "",
                ),
            )

        # Las deudas antiguas inactivas equivalían a deudas pagadas: se
        # registra el saldo liquidado para que el estado derivado coincida.
        for fila in deudas_legacy:
            if fila["activa"]:
                continue

            abonado = con.execute(
                "SELECT COALESCE(SUM(valor), 0) FROM abonos WHERE deuda_id = ?",
                (fila["id"],),
            ).fetchone()[0]

            restante = redondear(redondear(fila["valor_inicial"]) - abonado)

            if restante > 0:
                con.execute(
                    """
                    INSERT INTO abonos (deuda_id, fecha, valor, descripcion)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        fila["id"],
                        hoy,
                        restante,
                        "Saldo liquidado (migración)",
                    ),
                )


def _asegurar_columnas_deudas(con: sqlite3.Connection) -> None:
    """Agrega a ``deudas`` las columnas posteriores al esquema inicial.

    ``ALTER TABLE ... ADD COLUMN`` incorpora la columna sin reconstruir la tabla
    ni reescribir los registros existentes: las deudas ya guardadas quedan con
    el recordatorio vacío, que es justamente su estado por defecto.
    """

    existentes = _columnas(con, "deudas")

    if not existentes:
        return

    for nombre, tipo in _COLUMNAS_DEUDAS_AGREGADAS:
        if nombre in existentes:
            continue

        con.execute(f"ALTER TABLE deudas ADD COLUMN {nombre} {tipo}")
        logger.info("Columna '%s' agregada a la tabla 'deudas'.", nombre)


def _asegurar_abonos_con_cascada(con: sqlite3.Connection) -> None:
    """Reconstruye ``abonos`` cuando carece de la cascada hacia ``deudas``."""

    if not _tabla_existe(con, "abonos"):
        return

    if _tiene_clave_foranea(con, "abonos", "deuda_id"):
        return

    logger.info("Reconstruyendo 'abonos' para incorporar la cascada.")

    with _claves_foraneas_desactivadas(con):
        con.execute("DROP TABLE IF EXISTS abonos_migracion")
        con.execute(_ddl_abonos("abonos_migracion"))
        con.execute(
            """
            INSERT INTO abonos_migracion (
                id, deuda_id, fecha, valor, descripcion
            )
            SELECT
                a.id,
                a.deuda_id,
                COALESCE(a.fecha, date('now', 'localtime')),
                a.valor,
                COALESCE(a.descripcion, '')
            FROM abonos a
            WHERE EXISTS (
                SELECT 1 FROM deudas d WHERE d.id = a.deuda_id
            )
            """
        )
        con.execute("DROP TABLE abonos")
        con.execute("ALTER TABLE abonos_migracion RENAME TO abonos")


def _asegurar_movimientos_con_claves_foraneas(
    con: sqlite3.Connection,
) -> None:
    """Reconstruye ``movimientos`` cuando le faltan claves foráneas.

    Cubre tanto las bases anteriores a las columnas ``abono_id`` y
    ``suscripcion_id`` como las que las incorporaron mediante ``ALTER TABLE``
    (sin clave foránea asociada). Las columnas ausentes se proyectan como
    ``NULL`` para que la reconstrucción sea válida en cualquier origen.
    """

    columnas = _columnas(con, "movimientos")
    existe_abono = "abono_id" in columnas
    existe_suscripcion = "suscripcion_id" in columnas

    falta_abono = not existe_abono or not _tiene_clave_foranea(
        con, "movimientos", "abono_id"
    )
    falta_suscripcion = not existe_suscripcion or not _tiene_clave_foranea(
        con, "movimientos", "suscripcion_id"
    )

    if not falta_abono and not falta_suscripcion:
        return

    logger.info("Reconstruyendo 'movimientos' con claves foráneas.")

    expresion_abono = (
        "CASE WHEN a.id IS NOT NULL THEN m.abono_id END"
        if existe_abono
        else "NULL"
    )
    expresion_suscripcion = (
        "CASE WHEN s.id IS NOT NULL THEN m.suscripcion_id END"
        if existe_suscripcion
        else "NULL"
    )
    union_abonos = (
        "LEFT JOIN abonos a ON a.id = m.abono_id" if existe_abono else ""
    )
    union_suscripciones = (
        "LEFT JOIN suscripciones s ON s.id = m.suscripcion_id"
        if existe_suscripcion
        else ""
    )

    with _claves_foraneas_desactivadas(con):
        con.execute("DROP TABLE IF EXISTS movimientos_migracion")
        con.execute(_ddl_movimientos("movimientos_migracion"))
        con.execute(
            f"""
            INSERT INTO movimientos_migracion (
                id, fecha, tipo, categoria_id,
                descripcion, valor, abono_id, suscripcion_id
            )
            SELECT
                m.id,
                COALESCE(m.fecha, date('now', 'localtime')),
                CASE WHEN m.tipo = 'ingreso' THEN 'ingreso' ELSE 'gasto' END,
                CASE WHEN c.id IS NOT NULL THEN m.categoria_id END,
                COALESCE(m.descripcion, ''),
                m.valor,
                {expresion_abono},
                {expresion_suscripcion}
            FROM movimientos m
            LEFT JOIN categorias c
                ON c.id = m.categoria_id
            {union_abonos}
            {union_suscripciones}
            """
        )
        con.execute("DROP TABLE movimientos")
        con.execute(
            "ALTER TABLE movimientos_migracion RENAME TO movimientos"
        )


def _eliminar_tablas_obsoletas(con: sqlite3.Connection) -> None:
    """Retira tablas que ya no forman parte del dominio.

    Solo se eliminan cuando están vacías: una tabla con datos nunca se
    descarta de forma automática.
    """

    tabla = "ingresos_recurrentes"

    if not _tabla_existe(con, tabla):
        return

    if con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] > 0:
        return

    with _claves_foraneas_desactivadas(con):
        con.execute(f"DROP TABLE {tabla}")

    logger.info("Tabla obsoleta '%s' eliminada.", tabla)


def _crear_indices(con: sqlite3.Connection) -> None:
    for sentencia in _INDICES:
        con.execute(sentencia)


def inicializar_base_de_datos() -> None:
    """Crea el esquema, aplica migraciones y respalda la base instalada."""

    respaldo.crear_respaldo_automatico()

    with conexion() as con:
        _crear_tablas_base(con)
        _migrar_deudas_legacy(con)
        _asegurar_columnas_deudas(con)
        _asegurar_abonos_con_cascada(con)
        _asegurar_movimientos_con_claves_foraneas(con)
        _eliminar_tablas_obsoletas(con)
        _crear_indices(con)

    logger.info("Base de datos lista en %s", config.RUTA_BASE_DATOS)
