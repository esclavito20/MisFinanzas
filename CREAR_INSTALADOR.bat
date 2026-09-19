@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "INNO_VERSION=7.1.0"
set "INNO_URL=https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/innosetup-7.1.0-x64.exe"
set "INNO_INSTALLER=%TEMP%\innosetup-%INNO_VERSION%-x64.exe"

 echo.
echo ================================================
echo        MIS FINANZAS - CREAR INSTALADOR
echo ================================================
echo.

rem VERSION.txt es la unica fuente de verdad de la version de la aplicacion.
set "APP_VERSION="
if not exist "VERSION.txt" (
    echo No se encontro VERSION.txt en esta carpeta.
    echo Ese archivo define la version del instalador.
    goto :error
)
for /f "usebackq tokens=* delims=" %%v in ("VERSION.txt") do if not defined APP_VERSION set "APP_VERSION=%%v"
if not defined APP_VERSION (
    echo VERSION.txt esta vacio.
    echo Escribe la version, por ejemplo: 1.1.0
    goto :error
)
echo Version detectada: %APP_VERSION%
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo No se encontro Python en el PATH.
    echo Instala Python desde python.org y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

if not exist ".build_venv\Scripts\python.exe" (
    echo [1/5] Creando entorno de compilacion...
    python -m venv .build_venv
    if errorlevel 1 goto :error
) else (
    echo [1/5] Entorno de compilacion ya existe.
)

echo [2/5] Instalando/actualizando dependencias...
.\.build_venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
.\.build_venv\Scripts\python.exe -m pip install --upgrade PySide6 PyInstaller
if errorlevel 1 goto :error

echo [3/5] Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist release rmdir /s /q release
if not exist release mkdir release

echo [4/5] Generando la aplicacion de Windows...
.\.build_venv\Scripts\python.exe -m PyInstaller --clean --noconfirm MisFinanzas.spec
if errorlevel 1 goto :error
if not exist "dist\MisFinanzas\MisFinanzas.exe" (
    echo.
    echo PyInstaller termino, pero no se encontro: dist\MisFinanzas\MisFinanzas.exe
    goto :error
)
echo    EXE generado correctamente.

echo [5/5] Preparando Inno Setup...
set "ISCC="
if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo    Inno Setup no esta instalado.
    echo    Descargando Inno Setup %INNO_VERSION% desde el sitio oficial...
    echo.

    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%INNO_URL%' -OutFile '%INNO_INSTALLER%' -UseBasicParsing } catch { Write-Host ('ERROR: ' + $_.Exception.Message); exit 1 }"
    if errorlevel 1 (
        echo.
        echo No fue posible descargar Inno Setup.
        echo Puedes descargarlo manualmente desde:
        echo https://jrsoftware.org/isdl.php
        goto :error
    )

    if not exist "%INNO_INSTALLER%" (
        echo No se encontro el instalador descargado.
        goto :error
    )

    echo    Instalando Inno Setup de forma silenciosa...
    "%INNO_INSTALLER%" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    if errorlevel 1 (
        echo.
        echo La instalacion de Inno Setup no pudo completarse.
        echo Intenta instalarlo manualmente desde:
        echo https://jrsoftware.org/isdl.php
        goto :error
    )

    timeout /t 2 /nobreak >nul
    if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
    if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
)

if not defined ISCC (
    echo.
    echo Inno Setup se instalo, pero no se pudo localizar ISCC.exe.
    echo Revisa la instalacion y vuelve a ejecutar este archivo.
    goto :error
)

echo    Compilando instalador...
"%ISCC%" /DMyAppVersion=%APP_VERSION% installer\MisFinanzas.iss
if errorlevel 1 goto :error

if not exist "release\MisFinanzas_Setup_%APP_VERSION%.exe" (
    echo Inno Setup no creo el instalador esperado.
    goto :error
)

if exist "%INNO_INSTALLER%" del /q "%INNO_INSTALLER%" >nul 2>&1

echo.
echo ================================================
echo        INSTALADOR CREADO CORRECTAMENTE
echo ================================================
echo.
echo Archivo: %cd%\release\MisFinanzas_Setup_%APP_VERSION%.exe
echo.
start "" explorer.exe "%cd%\release"
pause
exit /b 0

:error
echo.
echo ================================================
echo       ERROR AL CREAR EL INSTALADOR
echo ================================================
echo.
pause
exit /b 1
