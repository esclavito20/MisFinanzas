@echo off
setlocal
set "DATA_DIR=%LOCALAPPDATA%\MisFinanzas\data"
set "BACKUP_DIR=%LOCALAPPDATA%\MisFinanzas\backups_manual"
if not exist "%DATA_DIR%\finanzas.db" (
    echo No se encontro la base de datos en:
    echo %DATA_DIR%\finanzas.db
    pause
    exit /b 1
)
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "STAMP=%%A"
copy /y "%DATA_DIR%\finanzas.db" "%BACKUP_DIR%\finanzas_%STAMP%.db" >nul
if errorlevel 1 (
    echo No fue posible crear el respaldo.
    pause
    exit /b 1
)
echo Respaldo creado correctamente en:
echo %BACKUP_DIR%\finanzas_%STAMP%.db
pause
