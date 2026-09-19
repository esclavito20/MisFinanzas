MIS FINANZAS - CREAR INSTALADOR

1. Descomprime esta carpeta en Windows.
2. Haz doble clic en CREAR_INSTALADOR.bat.
3. El script crea un entorno de compilacion, instala PySide6 y PyInstaller, genera MisFinanzas.exe y crea el instalador con Inno Setup.
4. Si Inno Setup no esta instalado y winget no existe, el script descarga automaticamente Inno Setup 7.1.0 x64 desde el repositorio oficial de Inno Setup y lo instala.
5. Al terminar, el instalador queda en:
   release\MisFinanzas_Setup_<version>.exe
   (la version se lee de VERSION.txt)

La aplicacion instalada guarda los datos de usuario en %LOCALAPPDATA%\MisFinanzas para no depender de permisos dentro de Archivos de programa.

REQUISITO:
- Python instalado y disponible en PATH.
- Conexion a Internet solamente durante la primera compilacion, para instalar PySide6/PyInstaller y, si hace falta, Inno Setup.

Uso del programa instalado:
- Una vez instalado Mis Finanzas, no necesitas Visual Studio Code ni Python para ejecutarlo.

INNO SETUP:
- Version usada por el script: 7.1.0 x64
- Descarga oficial: https://jrsoftware.org/isdl.php


ACTUALIZACIONES SEGURAS
-----------------------
- La base de datos del usuario se guarda fuera de la carpeta de instalacion, en %LOCALAPPDATA%\MisFinanzas\data.
- Al iniciar una version instalada, la aplicacion crea un respaldo automatico previo de la base de datos antes de ejecutar la inicializacion y migraciones.
- Se conservan los 10 respaldos mas recientes en %LOCALAPPDATA%\MisFinanzas\backups.
- El instalador conserva el mismo AppId para actualizar la instalacion existente en lugar de crear otra.
- Al actualizar, Inno Setup solicita/cierra MisFinanzas.exe para evitar reemplazar archivos en uso y puede volver a abrir la aplicacion.
- El desinstalador no elimina la carpeta de datos del usuario.

IMPORTANTE PARA PUBLICAR UNA NUEVA VERSION
------------------------------------------
1. Cambia la version en VERSION.txt (unica fuente de verdad).
2. Ejecuta CREAR_INSTALADOR.bat.
3. Publica la release en GitHub (ver el apartado siguiente) con el instalador
   release\MisFinanzas_Setup_<version>.exe adjunto.
Los datos del usuario permanecen en LocalAppData y no se incluyen en el instalador.
El instalador ya no empaqueta la base de datos: en el primer arranque la
aplicacion crea el esquema y las categorias iniciales en el perfil del usuario.


ACTUALIZACION AUTOMATICA (desde la version 2.2)
-----------------------------------------------
La aplicacion consulta una vez por arranque, en segundo plano, si el repositorio
tiene una version mas reciente, y tambien cuando se pulsa
Configuracion > Buscar actualizaciones. Si no hay red, el fallo es silencioso.

ORIGEN:
- Se declara en config.py, constante REPOSITORIO_ACTUALIZACIONES, con el formato
  "usuario/repositorio". Si queda vacia, la busqueda de actualizaciones se
  desactiva por completo.
- La aplicacion solo consulta la API publica de GitHub; no necesita servidor ni
  token mientras el repositorio sea publico.

PUBLICAR UNA VERSION QUE LOS USUARIOS PUEDAN INSTALAR:
1. Crea la release con la etiqueta de la version, por ejemplo v2.2.0.
2. Adjunta como asset el instalador, con el nombre MisFinanzas_Setup_<version>.exe.
   Ese prefijo tiene preferencia en la busqueda; si un dia cambia el nombre, la
   aplicacion acepta cualquier otro .exe adjunto.
3. Escribe en las notas de la release el resumen de cambios: la aplicacion las
   muestra en el dialogo de actualizacion.

VERIFICACION DE LA DESCARGA:
- El instalador se descarga en %LOCALAPPDATA%\MisFinanzas\updates y su SHA-256 se
  calcula mientras llega, comparandose con el resumen que GitHub publica en el
  campo digest de cada asset.
- Si la release no declara ese resumen, la descarga no puede verificarse y la
  aplicacion NO la ejecuta: ofrece abrir la publicacion en el navegador.
- Si el resumen no coincide, el archivo se descarta de inmediato.

APLICACION DE LA ACTUALIZACION:
- Solo la aplicacion instalada se actualiza a si misma. Ejecutando desde el codigo
  fuente, la aplicacion descarga y verifica el instalador, pero avisa de que debe
  abrirse manualmente.
- Antes de instalar se crea un respaldo manual de la base de datos en
  %LOCALAPPDATA%\MisFinanzas\backups_manual.
- El instalador se ejecuta en modo silencioso (Windows pedira elevacion por UAC),
  cierra la aplicacion y la vuelve a abrir al terminar.

EN ANDROID:
- La actualizacion automatica esta desactivada: la version nueva se instala
  abriendo el APK descargado.


EXPORTAR E IMPORTAR DATOS
-------------------------
Se accede desde Configuracion > Exportar datos / Importar datos.

EXPORTAR:
- Genera un archivo JSON (MisFinanzas_datos_<fecha>.json) con todos los registros:
  categorias, deudas, abonos, suscripciones, inversiones y movimientos.
- Junto a el crea la carpeta <nombre>_csv con una hoja de calculo por tabla. Las
  hojas anaden columnas resueltas (categoria, suscripcion, deuda) para revisarlas
  en Excel o Google Sheets; se escriben con separador ";" y decimales con coma,
  de modo que Excel en espanol las abra directamente. Son de solo lectura: no se
  importan.
- El JSON conserva identificadores y relaciones, de modo que volver a importarlo
  deja la base exactamente igual.

IMPORTAR:
- Reemplaza TODOS los datos actuales por los del archivo, despues de confirmarlo y
  de crear un respaldo previo en %LOCALAPPDATA%\MisFinanzas\backups_manual.
- El archivo se valida antes de tocar la base: aplicacion de origen, version del
  formato, columnas, tipos de dato, fechas, identificadores repetidos y relaciones
  inexistentes. Si algo no cuadra, se informa del motivo y no se modifica nada.
- La escritura se hace en una sola transaccion: o se aplica completa, o la base
  queda tal como estaba.

USO TIPICO:
- Pasar los datos del computador al telefono: exportar en el escritorio e importar
  ese mismo JSON desde la aplicacion instalada en Android, donde la base es
  independiente.
- Archivar los datos de forma legible e independiente de la version del programa.

NOTA DE COMPATIBILIDAD:
- Un archivo JSON exportado con la version 2.2 (formato 1) se sigue importando sin
  cambios: las columnas nuevas quedan vacias. Un archivo generado por una version
  posterior a la instalada se rechaza con un aviso.


SINCRONIZACION ENTRE EQUIPOS (desde la version 3.0)
---------------------------------------------------
Se accede desde Configuracion > Sincronizacion.

COMO FUNCIONA:
- Se elige una carpeta del servicio de almacenamiento del usuario (Google Drive,
  OneDrive, Dropbox). La aplicacion escribe ahi un unico archivo
  (MisFinanzas_datos.json) y el servicio se encarga de replicarlo entre equipos.
- No se guardan credenciales ni se depende de una API externa, asi que funciona
  igual sin conexion: el archivo se replica cuando el servicio recupere la red.
- La carpeta elegida se recuerda en %LOCALAPPDATA%\MisFinanzas\sincronizacion.json.

OPERACIONES:
- Enviar: publica el contenido de este equipo en la carpeta compartida. Si la copia
  compartida es mas reciente, se avisa antes de reemplazarla.
- Traer: adopta la copia compartida como contenido de este equipo. Reemplaza todos
  los datos locales y, antes de hacerlo, crea un respaldo en backups_manual.
- El dialogo muestra que contiene cada lado y cual cambio despues de la ultima
  sincronizacion, para decidir la direccion con la informacion a la vista.
- La sincronizacion es de un solo sentido por operacion y siempre manual: no se
  fusionan dos bases automaticamente, porque combinar fila a fila podria duplicar
  o perder registros sin que se note.


NOVEDADES DE LA VERSION 3.0
---------------------------
DEUDAS:
- Cada deuda admite un recordatorio de proximo pago, con fecha y valor minimo
  esperado. Ambos son opcionales y se configuran al crearla o despues, con el boton
  Editar de su tarjeta.
- La tarjeta de la deuda muestra la fecha en que se registro, el proximo pago y su
  plazo ("vencio hace 2 dias", "vence en 5 dias") y, si esta definido, el minimo.
- Cuando hay pagos vencidos o por vencer (5 dias de antelacion) aparece un aviso al
  principio de la pagina; las deudas pagadas no generan alerta.
- Al registrar un abono se ofrece reprogramar el recordatorio: avanzar un mes, quince
  dias o una semana, mantener la fecha o retirarlo. Cada opcion muestra la fecha en la
  que quedaria, y la aplicacion avanza siempre al menos un periodo hasta dar con una
  fecha futura, de modo que un recordatorio olvidado durante meses recupera el proximo
  pago realmente pendiente en lugar de repetir una fecha ya pasada. Si el abono es
  parcial o no corresponde al pago programado, la opcion de mantener la fecha lo deja
  como estaba. Corregir un abono desde el historial nunca mueve el recordatorio.
- El historial de abonos pasa a ser una ventana con una fila por abono, desde la que
  se puede corregir el monto y la fecha o eliminar el abono. El saldo pendiente se
  recalcula solo y el movimiento asociado se mantiene en sincronia.

DINERO DISPONIBLE:
- Los abonos dejan de contarse como gasto. Pagar una deuda no es consumir, asi que
  ya no aparecen en la tarjeta "Gastos", en la pagina de Analisis ni en el grafico
  por categorias.
- El bloque "Dinero disponible este mes" habla del mes en curso, igual que las
  tarjetas de ingresos y gastos: ingresos menos gastos (los abonos cuentan como
  salida, porque el dinero salio de la cuenta) menos lo comprometido del mes y el
  capital invertido. Un pago o un cobro de un mes anterior pertenece a su propio
  periodo y no altera el dinero disponible de hoy; al registrar un abono antiguo la
  deuda si baja, pero el disponible del mes no cambia.
- El detalle del bloque desglosa el efectivo del mes, lo invertido, lo comprometido
  y lo pagado a deudas en el mismo periodo.
- La pagina de Analisis da el mismo resultado: bajo sus tarjetas de ingresos y gastos
  muestra el pagado a deudas del mes y su "Resultado" es la misma cifra que el
  efectivo del mes del inicio, asi que ambas paginas no pueden discrepar.
- En Movimientos los abonos siguen apareciendo, identificados como "Abono a deuda" y
  con su propio icono, para no confundirlos con un gasto ordinario.


APLICACION PARA ANDROID (APK)
-----------------------------
La interfaz incluye un modo compacto: cuando se ejecuta en Android, la barra
lateral se sustituye por una barra de navegacion inferior, los datos de cada
tarjeta se reparten en dos columnas y los dialogos se ajustan al ancho de la
pantalla. En escritorio nada de esto cambia.

REQUISITO DE PLATAFORMA (importante):
- La herramienta oficial pyside6-android-deploy solo funciona en Linux o macOS.
  PyInstaller (el usado para el .exe) no genera APK.
- En Windows hay que usar WSL2 con Ubuntu:
      1) Abre PowerShell como administrador y ejecuta:  wsl --install -d Ubuntu
      2) Reinicia el equipo y crea el usuario de Ubuntu.
      3) Dentro de Ubuntu, instala el script y compila.

COMPILACION:
   cd /mnt/d/Desarrollo/Programas/Mis_Finanzas/Version_De_Trabajo
   bash CONSTRUIR_APK.sh

El script:
- Instala las dependencias del sistema (JDK 17, herramientas de compilacion).
- Crea un entorno de Python propio en ~/mis_finanzas_android/entorno.
- Descarga los wheels de PySide6 y shiboken6 para Android (aarch64).
- Copia solo las fuentes de la aplicacion (nunca la base de datos, los
  respaldos, los registros ni el entorno virtual) a ~/mis_finanzas_android.
  La compilacion se hace en el sistema de archivos de Linux porque buildozer
  falla sobre las carpetas montadas de Windows.
- Ejecuta pyside6-android-deploy con pysidedeploy.spec.
- Copia el APK resultante a:  release\MisFinanzas-<version>.apk

La primera compilacion descarga el SDK y el NDK de Android (varios GB) y puede
tardar bastante. Las siguientes reutilizan esa descarga.

INSTALACION EN EL TELEFONO:
1. Pasa el APK al telefono (cable, correo o almacenamiento compartido).
2. Abre el archivo en el telefono y acepta el aviso de "origen desconocido".
3. La aplicacion crea su propia base de datos, independiente de la de
   escritorio: el APK no incluye los datos del PC y todavia no hay
   sincronizacion entre ambos.

CONFIGURACION:
- pysidedeploy.spec contiene el nombre, el icono, la arquitectura (aarch64),
  los paquetes de empaquetado y el modo de buildozer (debug = .apk).
- El icono del lanzador es assets\MisFinanzas.png (512x512). El .ico de
  escritorio no sirve para Android.
