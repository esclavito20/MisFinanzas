#!/usr/bin/env bash
#
# Construccion del APK de Mis Finanzas.
#
# REQUISITO DE PLATAFORMA
#   pyside6-android-deploy solo funciona en un host Linux o macOS y PyInstaller
#   no genera APK: en Windows es obligatorio WSL2 con Ubuntu.
#       wsl --install -d Ubuntu      (PowerShell como administrador, y reiniciar)
#   Despues, dentro de Ubuntu:
#       cd /mnt/d/Desarrollo/Programas/Mis_Finanzas/Version_De_Trabajo
#       bash CONSTRUIR_APK.sh
#
# TRABAJO
#   La compilacion se hace en ~/mis_finanzas_android (sistema de archivos de
#   Linux) porque buildozer falla sobre el sistema de archivos montado de
#   Windows. El APK resultante se copia a release/ del proyecto.

set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRABAJO="${HOME}/mis_finanzas_android"
FUENTES="${TRABAJO}/fuentes"
RUEDAS="${TRABAJO}/ruedas"
ENTORNO="${TRABAJO}/entorno"

VERSION="$(tr -d '[:space:]' < "${PROYECTO}/VERSION.txt")"
NOMBRE_APK="MisFinanzas-${VERSION}"

# Solo se empaquetan las fuentes de la aplicacion: nunca la base de datos
# local, los respaldos, los registros ni el entorno virtual de desarrollo.
ELEMENTOS=(
    main.py
    config.py
    VERSION.txt
    assets
    ui
    models
    services
    repositories
    database
    utils
)

paso() {
    printf '\n=====================================================\n'
    printf ' %s\n' "$1"
    printf '=====================================================\n'
}

paso "0/6 Verificando el sistema"

SISTEMA="$(uname -s)"

if [ "${SISTEMA}" != "Linux" ] && [ "${SISTEMA}" != "Darwin" ]; then
    echo "ERROR: pyside6-android-deploy solo funciona en Linux o macOS."
    echo "       En Windows ejecuta este script dentro de WSL2 (ver cabecera)."
    exit 1
fi

case "${PROYECTO}" in
    /mnt/*)
        echo "AVISO: el proyecto esta en el sistema de archivos de Windows."
        echo "       La compilacion se hara en ${FUENTES}."
        ;;
esac

echo "Version de la aplicacion: ${VERSION}"

paso "1/6 Preparando dependencias del sistema"

if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y \
        python3-venv python3-pip openjdk-17-jdk git zip unzip \
        autoconf automake libtool pkg-config build-essential ccache \
        zlib1g-dev libncurses5-dev libncursesw5-dev cmake libffi-dev \
        libssl-dev
else
    echo "AVISO: no hay apt-get. Verifica manualmente que esten instalados:"
    echo "       JDK 17, git, zip, unzip, autoconf, automake, libtool, cmake,"
    echo "       pkg-config, ccache y las cabeceras de desarrollo de OpenSSL."
fi

if ! command -v java >/dev/null 2>&1; then
    echo "ERROR: no se encontro Java. Instala un JDK 17 antes de continuar."
    exit 1
fi

if [ -z "${JAVA_HOME:-}" ]; then
    RUTA_JAVA="$(readlink -f "$(command -v java)" 2>/dev/null || command -v java)"
    JAVA_HOME="$(dirname "$(dirname "${RUTA_JAVA}")")"
    export JAVA_HOME
fi

echo "JAVA_HOME=${JAVA_HOME}"
mkdir -p "${TRABAJO}" "${RUEDAS}"

paso "2/6 Creando el entorno de compilacion"

if [ ! -x "${ENTORNO}/bin/python" ]; then
    python3 -m venv "${ENTORNO}"
fi

# shellcheck disable=SC1091
. "${ENTORNO}/bin/activate"

python -m pip install --upgrade pip
python -m pip install --upgrade pyside6
python -m pip install --upgrade qtpip || echo "AVISO: qtpip no se instalo; los wheels se resolveran manualmente."

if ! command -v pyside6-android-deploy >/dev/null 2>&1; then
    echo "ERROR: esta instalacion de PySide6 no incluye pyside6-android-deploy."
    echo "       Comprueba que la version sea 6.6 o superior y que el host sea"
    echo "       Linux o macOS:"
    echo "       https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-android-deploy.html"
    exit 1
fi

python -c "import PySide6; print('PySide6', PySide6.__version__)"

paso "3/6 Descargando los wheels de Android (aarch64)"

cd "${RUEDAS}"

qtpip download PySide6 --android --arch aarch64 || true

RUEDA_PYSIDE="$(find . -maxdepth 1 -name 'PySide6-*android*.whl' -print -quit)"
RUEDA_SHIBOKEN="$(find . -maxdepth 1 -name 'shiboken6-*android*.whl' -print -quit)"

if [ -z "${RUEDA_SHIBOKEN}" ]; then
    qtpip download shiboken6 --android --arch aarch64 || true
    RUEDA_SHIBOKEN="$(find . -maxdepth 1 -name 'shiboken6-*android*.whl' -print -quit)"
fi

if [ -z "${RUEDA_PYSIDE}" ] || [ -z "${RUEDA_SHIBOKEN}" ]; then
    echo "ERROR: no se encontraron los wheels para Android en ${RUEDAS}."
    echo "       Descargalos a mano desde:"
    echo "       https://download.qt.io/official_releases/QtForPython/pyside6/"
    echo "       y coloca los dos archivos .whl en esa carpeta."
    exit 1
fi

RUEDA_PYSIDE="${RUEDAS}/${RUEDA_PYSIDE#./}"
RUEDA_SHIBOKEN="${RUEDAS}/${RUEDA_SHIBOKEN#./}"

echo "PySide6:   ${RUEDA_PYSIDE}"
echo "Shiboken6: ${RUEDA_SHIBOKEN}"

paso "4/6 Copiando las fuentes y configurando el despliegue"

rm -rf "${FUENTES}"
mkdir -p "${FUENTES}"

for elemento in "${ELEMENTOS[@]}"; do
    if [ ! -e "${PROYECTO}/${elemento}" ]; then
        echo "ERROR: falta ${elemento} en el proyecto."
        exit 1
    fi

    cp -a "${PROYECTO}/${elemento}" "${FUENTES}/"
done

cp "${PROYECTO}/pysidedeploy.spec" "${FUENTES}/pysidedeploy.spec"

# Las rutas de los wheels son absolutas y dependen del usuario: se escriben en
# la copia del spec para no tener que pasarlas por linea de comandos.
python - "${FUENTES}/pysidedeploy.spec" "${RUEDA_PYSIDE}" "${RUEDA_SHIBOKEN}" <<'PY'
import pathlib
import re
import sys

ruta = pathlib.Path(sys.argv[1])
texto = ruta.read_text(encoding="utf-8")

for clave, valor in (
    ("wheel_pyside", sys.argv[2]),
    ("wheel_shiboken", sys.argv[3]),
):
    texto, cambios = re.subn(
        rf"(?m)^{clave}\s*=.*$",
        f"{clave} = {valor}",
        texto,
    )

    if cambios == 0:
        raise SystemExit(f"No se encontro la clave {clave} en el spec.")

ruta.write_text(texto, encoding="utf-8")
print("Configuracion de despliegue lista.")
PY

paso "5/6 Compilando el APK"
echo "La primera compilacion descarga el SDK y el NDK de Android (varios GB)."

cd "${FUENTES}"
pyside6-android-deploy --config-file pysidedeploy.spec

paso "6/6 Publicando el resultado"

APK_ORIGEN="$(find "${FUENTES}" -name '*.apk' -print -quit)"

if [ -z "${APK_ORIGEN}" ]; then
    echo "ERROR: la compilacion termino sin generar un APK."
    echo "       Revisa el registro anterior para localizar el fallo."
    exit 1
fi

mkdir -p "${PROYECTO}/release"
cp "${APK_ORIGEN}" "${PROYECTO}/release/${NOMBRE_APK}.apk"

printf '\nAPK generado:\n  %s\n\n' "${PROYECTO}/release/${NOMBRE_APK}.apk"
ls -lh "${PROYECTO}/release/${NOMBRE_APK}.apk"

cat <<'FIN'

INSTALACION EN EL TELEFONO
1. Copia el APK al telefono (cable, correo o almacenamiento compartido).
2. Abre el archivo desde el telefono y acepta instalar aplicaciones de
   origen desconocido cuando el sistema lo solicite.
3. Al abrir la aplicacion, los datos se crean vacios en el almacenamiento
   privado de la app: es una base independiente de la de escritorio.
FIN
