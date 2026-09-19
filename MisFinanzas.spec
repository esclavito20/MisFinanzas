# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import PySide6

# La aplicacion solo importa PySide6.QtCore, PySide6.QtGui y PySide6.QtWidgets.
# Declararlos explicitamente era necesario porque la deteccion automatica de
# modulos de Qt no es concluyente, pero recolectar PySide6 completo arrastraba
# QtWebEngine, QtQml, Qt3D y sus recursos: 611 MB de instalacion. Con la lista
# real el paquete baja a la fraccion que corresponde al codigo.
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
]

# Los catalogos de traduccion llegaban como efecto colateral de QtWebEngine.
# Sin el, hay que declararlos: de ellos depende que QMessageBox y los cuadros
# estandar de Qt compongan sus botones en espanol (ver
# ui.tema.instalar_traducciones, que carga el catalogo "qt" para es_CO).
_DIRECTORIO_TRADUCCIONES = Path(PySide6.__file__).parent / 'translations'
_CATALOGOS = ('qt_es.qm', 'qtbase_es.qm')

datas_traducciones = [
    (str(_DIRECTORIO_TRADUCCIONES / nombre), 'PySide6/translations')
    for nombre in _CATALOGOS
    if (_DIRECTORIO_TRADUCCIONES / nombre).exists()
]


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    # La base de datos del usuario no se empaqueta: se crea vacia (esquema y
    # categorias iniciales) en el primer arranque dentro del perfil del usuario.
    datas=[('assets', 'assets'), ('VERSION.txt', '.')] + datas_traducciones,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MisFinanzas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\MisFinanzas.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MisFinanzas',
)
