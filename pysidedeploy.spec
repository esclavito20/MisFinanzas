/ Configuracion de despliegue de Mis Finanzas para Android.
/
/ Se consume con:  pyside6-android-deploy --config-file pysidedeploy.spec
/ Requiere un host Linux o macOS (pyside6-android-deploy no funciona en
/ Windows) y las herramientas de Android. El script CONSTRUIR_APK.sh prepara
/ todo lo necesario y rellena las rutas de los wheels antes de invocarlo, y el
/ flujo .github/workflows/construir_apk.yml hace lo mismo en la nube.
/
/ Las claves validas son las declaradas en el archivo default.spec que
/ distribuye PySide6 (scripts/deploy_lib/default.spec).
/
/ ATENCION: los comentarios empiezan por barra, no por almohadilla.
/ pyside6-android-deploy construye su analizador con comment_prefixes="/", de
/ modo que una linea que empiece por "#" no se reconoce como comentario: antes
/ de la primera seccion aborta la lectura con MissingSectionHeaderError y
/ dentro de una seccion se interpreta como una clave sin valor.

[app]

/ Nombre visible de la aplicacion en el telefono.
title = Mis Finanzas

/ Punto de entrada. El despliegue de Android exige que se llame main.py.
input_file = main.py

/ Icono del lanzador: Android requiere PNG, no ICO.
icon = assets/MisFinanzas.png

[python]

/ Python que ejecuta el despliegue. Vacio: el interprete del entorno activo.
python_path =

/ Buildozer y Cython se instalan en ese mismo entorno para empaquetar el APK.
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]

/ La aplicacion solo usa Qt Widgets: no hay archivos QML que recolectar.
qml_files =

modules =

plugins =

[android]

/ Wheels de PySide6 y shiboken6 compilados para Android (aarch64). Los rellenan
/ CONSTRUIR_APK.sh y el flujo de GitHub Actions tras descargarlos del servidor
/ oficial de Qt.
wheel_pyside =

wheel_shiboken =

/ Complementos de Qt que deben copiarse a la carpeta libs del paquete. Las
/ plataformas de Qt (como la de Android) se incluyen por defecto.
plugins =

[buildozer]

/ debug genera un .apk instalable en el telefono; release genera un .aab.
mode = debug

/ Vacio: buildozer descarga el NDK y el SDK que le corresponden.
recipe_dir =

jars_dir =

ndk_path =

sdk_path =

local_libs =

/ Telefonos actuales (64 bits): arquitectura del APK.
arch = aarch64
