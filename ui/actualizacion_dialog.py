"""Diálogo de actualizaciones: consulta, descarga verificada e instalación.

Toda la actividad de red ocurre de forma asíncrona con
``QNetworkAccessManager``: ni la consulta ni la descarga de más de cien
megabytes bloquean el bucle de eventos, y no se necesita ningún hilo adicional.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

import config
from database import respaldo
from models.actualizacion import InfoActualizacion
from services import actualizaciones_service as servicio
from ui import tema

logger = logging.getLogger(__name__)

CARACTERES_DE_NOTAS = 1200
NOMBRE_USUARIO = f"MisFinanzas/{config.VERSION}"


def formatear_tamano(bytes_totales: int) -> str:
    """Presenta un tamaño en megabytes con la convención decimal local."""

    if bytes_totales <= 0:
        return "tamaño desconocido"

    return f"{bytes_totales / (1024 * 1024):.1f} MB".replace(".", ",")


# =========================================================================
# Consulta de la última publicación
# =========================================================================


class _ConsultaRelease(QObject):
    """Consulta asíncrona de la última publicación del repositorio."""

    encontrada = Signal(object)
    sin_novedad = Signal(object)
    fallo = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._gestor = QNetworkAccessManager(self)
        self._gestor.finished.connect(self._al_terminar)

    def iniciar(self) -> None:
        """Lanza la consulta y emite el resultado por señal."""

        try:
            direccion = servicio.url_consulta()
        except servicio.ErrorActualizacion as error:
            self.fallo.emit(str(error))
            return

        peticion = self._preparar_peticion(QUrl(direccion))

        self._gestor.get(peticion)

    def _preparar_peticion(self, direccion: QUrl) -> QNetworkRequest:
        peticion = QNetworkRequest(direccion)

        for nombre, valor in servicio.cabeceras().items():
            peticion.setRawHeader(nombre.encode("ascii"), valor.encode("utf-8"))

        peticion.setTransferTimeout(config.TIEMPO_ESPERA_CONSULTA_MS)

        return peticion

    def _al_terminar(self, respuesta: QNetworkReply) -> None:
        try:
            info = servicio.interpretar_release(self._leer(respuesta))
        except servicio.ErrorActualizacion as error:
            self.fallo.emit(str(error))
            return
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.exception("Respuesta ilegible de la API de GitHub.")
            self.fallo.emit("La respuesta del servidor no se pudo interpretar.")
            return
        finally:
            respuesta.deleteLater()

        if info.supera_a(servicio.version_local()):
            self.encontrada.emit(info)
        else:
            self.sin_novedad.emit(info)

    def _leer(self, respuesta: QNetworkReply) -> object:
        if respuesta.error() != QNetworkReply.NetworkError.NoError:
            raise servicio.ErrorActualizacion(_mensaje_de_red(respuesta))

        return json.loads(bytes(respuesta.readAll().data()).decode("utf-8"))


def _mensaje_de_red(respuesta: QNetworkReply) -> str:
    """Traduce el fallo a un mensaje comprensible.

    Qt clasifica los estados HTTP de error como fallos de red, por lo que el
    código de estado es el primer dato que debe consultarse: sin él, un 404
    llegaría al usuario como un mensaje técnico del servidor.
    """

    estado = respuesta.attribute(
        QNetworkRequest.Attribute.HttpStatusCodeAttribute
    )

    if estado == 404:
        return (
            "No se pudo acceder a la última versión publicada: el repositorio "
            "no existe, es privado o todavía no tiene publicaciones. La "
            "aplicación solo puede consultar repositorios públicos."
        )

    if estado == 403:
        return (
            "GitHub limitó temporalmente las consultas. Inténtalo de nuevo más "
            "tarde."
        )

    if isinstance(estado, int) and estado >= 400:
        return f"El servidor de actualizaciones respondió con el estado {estado}."

    errores = QNetworkReply.NetworkError

    if respuesta.error() in (
        errores.TimeoutError,
        errores.TemporaryNetworkFailureError,
    ):
        return "La consulta tardó demasiado. Revisa la conexión e inténtalo."

    if respuesta.error() in (
        errores.HostNotFoundError,
        errores.UnknownNetworkError,
        errores.NetworkSessionFailedError,
    ):
        return "No hay conexión con el servidor de actualizaciones."

    if respuesta.error() == errores.SslHandshakeFailedError:
        return "No se pudo establecer una conexión segura con el servidor."

    return f"No fue posible consultar las actualizaciones: {respuesta.errorString()}"


# =========================================================================
# Descarga del instalador
# =========================================================================


class _DescargaInstalador(QObject):
    """Descarga asíncrona con verificación incremental del resumen SHA-256."""

    progreso = Signal(int)
    verificada = Signal(str)
    fallo = Signal(str)

    def __init__(self, info: InfoActualizacion, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._info = info
        self._destino = servicio.ruta_descarga(info)
        self._gestor = QNetworkAccessManager(self)
        self._respuesta: QNetworkReply | None = None
        self._archivo = None
        self._verificador = servicio.VerificadorDescarga(info)

    def iniciar(self) -> None:
        try:
            self._destino.parent.mkdir(parents=True, exist_ok=True)
            self._archivo = self._destino.open("wb")
        except OSError as error:
            self.fallo.emit(f"No se pudo preparar la descarga: {error}")
            return

        peticion = QNetworkRequest(QUrl(self._info.url_descarga))
        peticion.setRawHeader(b"User-Agent", NOMBRE_USUARIO.encode("ascii"))
        peticion.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        peticion.setTransferTimeout(config.TIEMPO_ESPERA_DESCARGA_MS)

        self._respuesta = self._gestor.get(peticion)
        self._respuesta.readyRead.connect(self._escribir)
        self._respuesta.downloadProgress.connect(self._informar_progreso)
        self._respuesta.finished.connect(self._al_terminar)

    def detener(self) -> None:
        """Interrumpe la descarga y descarta el archivo parcial."""

        if self._respuesta is not None:
            self._respuesta.abort()

        self._cerrar_archivo()
        self._descartar_parcial()

    def _escribir(self) -> None:
        if self._respuesta is None or self._archivo is None:
            return

        datos = bytes(self._respuesta.readAll().data())

        if not datos:
            return

        self._archivo.write(datos)
        self._verificador.agregar(datos)

    def _informar_progreso(self, recibidos: int, totales: int) -> None:
        if totales <= 0:
            return

        self.progreso.emit(min(int(recibidos * 100 / totales), 100))

    def _al_terminar(self) -> None:
        respuesta = self._respuesta

        self._cerrar_archivo()

        if respuesta is None:
            return

        if respuesta.error() != QNetworkReply.NetworkError.NoError:
            self._descartar_parcial()
            self.fallo.emit(_mensaje_de_red(respuesta))
            return

        try:
            self._verificador.comprobar()
        except servicio.ErrorActualizacion as error:
            self._descartar_parcial()
            self.fallo.emit(str(error))
            return

        logger.info("Instalador disponible en %s", self._destino)
        self.verificada.emit(str(self._destino))

    def _cerrar_archivo(self) -> None:
        if self._archivo is not None:
            self._archivo.close()
            self._archivo = None

    def _descartar_parcial(self) -> None:
        try:
            self._destino.unlink(missing_ok=True)
        except OSError:
            logger.warning("No se pudo descartar la descarga parcial.")


# =========================================================================
# Diálogo
# =========================================================================


class ActualizacionDialog(QDialog):
    """Informa del estado de las actualizaciones y las aplica."""

    def __init__(
        self,
        parent=None,
        info_inicial: InfoActualizacion | None = None,
    ) -> None:
        super().__init__(parent)

        self._consulta: _ConsultaRelease | None = None
        self._descarga: _DescargaInstalador | None = None
        self._info: InfoActualizacion | None = None

        self.setWindowTitle("Actualizaciones")
        self.setFixedWidth(tema.ancho_dialogo(560))

        self._crear_interfaz()

        if info_inicial is not None:
            self._mostrar_disponible(info_inicial)
        else:
            self.buscar()

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------

    def _crear_interfaz(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        titulo = QLabel("⬆️ Actualizaciones")
        titulo.setStyleSheet(tema.estilo_titulo(20))
        layout.addWidget(titulo)

        self.version_label = QLabel(
            f"Versión instalada: {servicio.version_local()}"
        )
        self.version_label.setStyleSheet(tema.estilo_texto_secundario())
        layout.addWidget(self.version_label)

        self.mensaje_label = QLabel()
        self.mensaje_label.setWordWrap(True)
        layout.addWidget(self.mensaje_label)

        self.notas_label = QLabel()
        self.notas_label.setWordWrap(True)
        self.notas_label.setStyleSheet(
            f"color: {tema.TEXTO_SECUNDARIO}; font-size: 12px;"
        )
        layout.addWidget(self.notas_label)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setVisible(False)
        self.barra.setStyleSheet(tema.estilo_barra_progreso())
        layout.addWidget(self.barra)

        self.boton_descargar = QPushButton("⬇️ Descargar e instalar")
        self.boton_descargar.setStyleSheet(tema.estilo_boton_primario())
        self.boton_descargar.clicked.connect(self._descargar)

        self.boton_buscar = QPushButton("🔄 Buscar de nuevo")
        self.boton_buscar.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_buscar.clicked.connect(self.buscar)

        self.boton_pagina = QPushButton("🌐 Abrir la publicación")
        self.boton_pagina.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_pagina.clicked.connect(self._abrir_publicacion)

        self.boton_cerrar = QPushButton("Cerrar")
        self.boton_cerrar.setStyleSheet(tema.estilo_boton_secundario())
        self.boton_cerrar.clicked.connect(self.reject)

        layout.addLayout(
            tema.fila_de_acciones(
                self.boton_descargar,
                self.boton_buscar,
                self.boton_pagina,
            )
        )

        cierre = QHBoxLayout()
        cierre.addStretch()
        cierre.addWidget(self.boton_cerrar)
        layout.addLayout(cierre)

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {tema.FONDO};
            }}

            QLabel {{
                color: {tema.TEXTO};
                background-color: transparent;
            }}
            """
        )

        self._mostrar_consulta()

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------

    def _mostrar_consulta(self) -> None:
        self.mensaje_label.setText(
            "Comprobando si hay una versión más reciente…"
        )
        self.notas_label.clear()
        self._mostrar_botones(
            descargar=False,
            buscar=False,
            pagina=False,
            barra=False,
        )

    def _mostrar_disponible(self, info: InfoActualizacion) -> None:
        self._info = info
        self.mensaje_label.setText(
            f"Hay una versión nueva disponible: <b>{info.version}</b> "
            f"(tienes la {servicio.version_local()})."
        )
        self.version_label.setText(
            f"Versión instalada: {servicio.version_local()} · "
            f"publicada: {self._detalle_de_publicacion(info)}"
        )

        detalle = self._notas_para_mostrar(info)

        if not info.verificable:
            detalle += (
                "\n\nLa publicación no declara el resumen SHA-256 del "
                "instalador, por lo que la descarga no puede verificarse y la "
                "aplicación no la ejecutará. Usa «Abrir la publicación» para "
                "descargarla manualmente."
            )

        self.notas_label.setText(detalle)

        self._mostrar_botones(
            descargar=info.verificable and bool(info.url_descarga),
            buscar=True,
            pagina=bool(info.direccion_publicacion),
            barra=False,
        )

    def _mostrar_al_dia(self, info: InfoActualizacion) -> None:
        self.mensaje_label.setText(
            f"Tienes la última versión disponible ({info.version})."
        )
        self.notas_label.clear()
        self._mostrar_botones(
            descargar=False,
            buscar=True,
            pagina=bool(info.direccion_publicacion),
            barra=False,
        )

    def _mostrar_fallo(
        self,
        mensaje: str,
        detalle: str = "",
        mostrar_pagina: bool = False,
    ) -> None:
        self.mensaje_label.setText(mensaje)
        self.notas_label.setText(detalle)

        self._mostrar_botones(
            descargar=False,
            buscar=True,
            pagina=mostrar_pagina,
            barra=False,
        )

    def _mostrar_botones(
        self,
        descargar: bool,
        buscar: bool,
        pagina: bool,
        barra: bool,
    ) -> None:
        self.boton_descargar.setVisible(descargar)
        self.boton_buscar.setVisible(buscar)
        self.boton_pagina.setVisible(pagina)
        self.barra.setVisible(barra)

    def _notas_para_mostrar(self, info: InfoActualizacion) -> str:
        notas = info.notas_limpias

        if not notas:
            return f"Instalador: {formatear_tamano(info.tamano)}"

        if len(notas) > CARACTERES_DE_NOTAS:
            notas = notas[:CARACTERES_DE_NOTAS].rstrip() + "…"

        return f"{notas}\n\nInstalador: {formatear_tamano(info.tamano)}"

    def _detalle_de_publicacion(self, info: InfoActualizacion) -> str:
        return (info.publicada or "").split("T")[0] or "sin fecha"

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def buscar(self) -> None:
        """Consulta el repositorio en segundo plano."""

        if not servicio.disponible():
            self._mostrar_fallo(
                "La búsqueda de actualizaciones está desactivada: no se ha "
                "declarado el repositorio en config.REPOSITORIO_ACTUALIZACIONES."
            )
            return

        self._mostrar_consulta()

        self._consulta = _ConsultaRelease(self)
        self._consulta.encontrada.connect(self._mostrar_disponible)
        self._consulta.sin_novedad.connect(self._mostrar_al_dia)
        self._consulta.fallo.connect(self._mostrar_fallo)
        self._consulta.iniciar()

    def _descargar(self) -> None:
        if self._info is None:
            return

        respuesta = QMessageBox.question(
            self,
            "Instalar actualización",
            f"Se descargará la versión {self._info.version} "
            f"({formatear_tamano(self._info.tamano)}) y se instalará en modo "
            "silencioso.\n\nAl terminar la instalación, la aplicación se "
            "cerrará y volverá a abrirse sola.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        self.mensaje_label.setText(
            f"Descargando la versión {self._info.version}…"
        )
        self.barra.setValue(0)
        self._mostrar_botones(
            descargar=False,
            buscar=False,
            pagina=False,
            barra=True,
        )

        self._descarga = _DescargaInstalador(self._info, self)
        self._descarga.progreso.connect(self.barra.setValue)
        self._descarga.verificada.connect(self._instalar)
        self._descarga.fallo.connect(self._descarga_fallida)
        self._descarga.iniciar()

    def _descarga_fallida(self, mensaje: str) -> None:
        self._mostrar_fallo(
            mensaje,
            "Puedes descargar el instalador manualmente desde la publicación.",
            mostrar_pagina=bool(self._info and self._info.direccion_publicacion),
        )

    def _instalar(self, ruta_descargada: str) -> None:
        ruta = Path(ruta_descargada)

        self.mensaje_label.setText("Instalador verificado. Instalando…")
        self.barra.setVisible(False)

        if not servicio.puede_instalarse():
            self._mostrar_instalacion_manual(ruta)
            return

        respaldo.crear_respaldo_manual()

        QMessageBox.information(
            self,
            "Actualización lista",
            "La aplicación se cerrará ahora para instalar la versión "
            f"{self._info.version if self._info else ''} y volverá a abrirse "
            "sola al terminar.",
        )

        try:
            servicio.aplicar(ruta)
        except servicio.ErrorActualizacion as error:
            self._mostrar_fallo(str(error))
            return

        QApplication.quit()

    def _mostrar_instalacion_manual(self, ruta: Path) -> None:
        """Informa cuando la aplicación no puede reemplazarse a sí misma."""

        self.mensaje_label.setText(
            "El instalador se descargó y se verificó correctamente, pero esta "
            "ejecución no está instalada, así que no puede actualizarse sola."
        )
        self.notas_label.setText(
            f"Ábrelo manualmente para instalar la versión nueva:\n{ruta}"
        )
        self._mostrar_botones(
            descargar=False,
            buscar=True,
            pagina=bool(self._info and self._info.direccion_publicacion),
            barra=False,
        )

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta.parent)))

    def _abrir_publicacion(self) -> None:
        if self._info is None or not self._info.direccion_publicacion:
            return

        QDesktopServices.openUrl(QUrl(self._info.direccion_publicacion))

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def closeEvent(self, evento) -> None:
        if self._descarga is not None:
            self._descarga.detener()

        super().closeEvent(evento)

    def reject(self) -> None:
        if self._descarga is not None:
            self._descarga.detener()

        super().reject()


# =========================================================================
# Comprobación automática
# =========================================================================


def verificar_al_arrancar(ventana) -> None:
    """Comprueba en segundo plano si hay versión nueva y avisa si la hay.

    Es deliberadamente discreta: cualquier fallo —falta de red, repositorio sin
    publicaciones, límite de consultas alcanzado— se registra y no interrumpe el
    trabajo del usuario.
    """

    if not servicio.disponible():
        return

    consulta = _ConsultaRelease(ventana)

    def al_encontrar(info: InfoActualizacion) -> None:
        logger.info("Actualización disponible: %s", info.version)
        ActualizacionDialog(ventana, info_inicial=info).exec()

    consulta.encontrada.connect(al_encontrar)
    consulta.fallo.connect(
        lambda mensaje: logger.info(
            "Comprobación de actualizaciones sin resultado: %s", mensaje
        )
    )

    consulta.iniciar()
