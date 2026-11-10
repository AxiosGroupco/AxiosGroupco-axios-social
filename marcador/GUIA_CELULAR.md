# Marcador Axios – guía rápida

## En el celular (una sola vez)

1. **Ajustes → Acerca del teléfono** → toque 7 veces **Número de compilación** hasta que diga
   «Ya eres desarrollador».
2. **Ajustes → Sistema → Opciones de desarrollador** → active **Depuración USB**.
   En Xiaomi / Redmi / POCO active también **Depuración USB (ajustes de seguridad)**;
   sin eso el programa no puede colgar.
3. Si el celular tiene dos SIM: **Ajustes → SIM → Llamadas** → elija la SIM corporativa como
   predeterminada (si queda en «Preguntar siempre», el marcado se detiene en cada llamada).
4. Conecte los audífonos (Bluetooth o de cable) **al celular**, no al computador.

## Cada día

1. Conecte el celular al computador con el cable USB y desbloquéelo.
2. Abra **MarcadorAxios.exe**. La primera vez el celular pregunta «¿Permitir depuración USB?»:
   marque **Permitir siempre desde este equipo** y toque **Permitir**.
   Arriba en la ventana debe aparecer en verde **✔ Celular conectado y listo**.
3. **Cargar lista**: un Excel con los títulos `nombre` y `telefono` en la primera fila
   (el botón **Plantilla de lista** crea uno de ejemplo).
4. **Iniciar llamadas**. El programa llama solo:
   - Si **no contestan**, cuelga y sigue con el siguiente.
   - Si **contestan**, suena un aviso y la pantalla se pone en verde: hable con calma, el programa
     no hace nada. Al terminar, cuelgue en el celular (o con **Colgar**), escriba una nota si quiere
     y presione **Guardar y llamar al siguiente**.
5. **Ver resultados** abre el registro de todas las llamadas
   (`Documentos\MarcadorAxios\resultado_llamadas.csv`).

## Qué hace cada botón

| Botón | Para qué sirve |
|---|---|
| **Cargar lista** | Elegir el Excel o CSV con los contactos. |
| **▶ Iniciar llamadas** | Empezar a llamar. Si antes hace clic en una fila, empieza desde ese contacto. |
| **⏸ Pausar / ▶ Reanudar** | Detener el marcado al terminar la llamada actual y continuarlo después. |
| **✖ Colgar** | Colgar la llamada actual: al terminar de hablar o para saltar un número. |
| **☎ ¡Contestaron!** | Solo aparece si el celular no avisa cuándo contestan: presiónelo al oír que contestan. |
| **Guardar y llamar al siguiente** | Guarda la nota de la llamada y continúa. Solo aparece si la nota está activada. |
| **Ver resultados** | Abre en Excel el registro de todas las llamadas. |
| **Plantilla de lista** | Crea un Excel de ejemplo para llenar con los contactos. |
| **📁 Carpeta** | Abre `Documentos\MarcadorAxios`, donde queda todo: el programa, los registros, la plantilla y la subcarpeta `musica`. |
| **? Ayuda** | Muestra el recorrido paso a paso (se abre solo la primera vez). |
| **⚙ Ajustes** | Segundos de timbre, pedir o no la nota al terminar cada llamada, llamadas de cobranza y modo de detección. |

Con la nota **desactivada** en Ajustes, al terminar una llamada contestada el programa sigue solo
con el siguiente contacto a los pocos segundos; use **Pausar** si necesita un respiro.

## Acceso directo, música y mensajes

- La primera vez que se abre, el programa se copia a `Documentos\MarcadorAxios` y crea el acceso
  directo **Marcador Axios** en el escritorio. Desde entonces se abre desde ahí.
- Mientras el celular timbra suena música suave por los parlantes del computador y se calla cuando
  contestan. Se apaga o se le cambia el volumen en **Ajustes**. Para agregar música propia, copie
  archivos `.mp3` en la subcarpeta `musica`.
- Música incluida: Kevin MacLeod (incompetech.com), licencia Creative Commons Atribución 4.0.

## Si algo falla

| Lo que ve | Qué hacer |
|---|---|
| «Conecte el celular…» en rojo | Revise el cable (debe ser de datos, no solo de carga), cambie de puerto USB y confirme que la Depuración USB esté activa. En algunos equipos hay que instalar el controlador USB del fabricante. |
| «Mire la pantalla del celular…» | Acepte el mensaje «Permitir depuración USB» en el celular. |
| Aparece el botón **¡Contestaron!** | Ese celular no informa cuándo contestan. El programa sigue marcando y colgando solo, pero cuando oiga que contestan debe presionar ese botón para que no cuelgue. |
| «Fuera de horario» | La Ley 2300 de 2023 solo permite llamar L–V 7:00 a.m.–7:00 p.m. y sábados 8:00 a.m.–3:00 p.m.; nunca domingos ni festivos. |
| Windows muestra «Windows protegió su PC» al abrir | Clic en **Más información → Ejecutar de todas formas** (el programa no tiene firma digital). |
