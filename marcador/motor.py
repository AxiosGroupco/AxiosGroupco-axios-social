"""Motor del marcador progresivo: control del celular por adb, reglas de horario
(Ley 2300 de 2023), lectura de listas y registro de resultados. No depende de la
interfaz gráfica, para poder probarlo de forma automática."""
import base64
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata

APP = "MarcadorAxios"
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------------------------------------------------------------- carpetas


def carpeta_datos():
    """Documentos\\MarcadorAxios: resultados visibles para la usuaria."""
    d = os.path.join(os.path.expanduser("~"), "Documents", APP)
    os.makedirs(d, exist_ok=True)
    return d


def carpeta_interna():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, APP)
    os.makedirs(d, exist_ok=True)
    return d


def ruta_log():
    return os.path.join(carpeta_datos(), "resultado_llamadas.csv")


CONFIG_DEFECTO = {"timbre_max_s": 25, "pausa_s": 3, "cobranza": True, "pedir_nota": True, "modo": {},
                  "musica": True, "volumen": 25, "salida": "celular", "bajar_tono": True, "mensajes": True, "llamadas_total": 0, "hitos_dichos": []}


def cargar_config():
    cfg = json.loads(json.dumps(CONFIG_DEFECTO))
    try:
        with open(os.path.join(carpeta_interna(), "config.json"), encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def guardar_config(cfg):
    with open(os.path.join(carpeta_interna(), "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ---------------------------------------------------------------- adb

ARCHIVOS_ADB = ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll")


def preparar_adb():
    """Copia el adb que viene dentro del .exe a una carpeta fija y devuelve su ruta.
    (Se copia porque adb deja un proceso en segundo plano y no puede vivir en la
    carpeta temporal del ejecutable.) Devuelve None si no hay adb disponible."""
    origen = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "adb")
    if os.path.exists(os.path.join(origen, "adb.exe")):
        destino = os.path.join(carpeta_interna(), "adb")
        os.makedirs(destino, exist_ok=True)
        for n in ARCHIVOS_ADB:
            src, dst = os.path.join(origen, n), os.path.join(destino, n)
            try:
                if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
                    shutil.copy2(src, dst)
            except OSError:
                pass  # ya está en uso por un servidor adb anterior: sirve igual
        return os.path.join(destino, "adb.exe")
    return shutil.which("adb")


PRECISO = {"IDLE": 0, "ACTIVE": 1, "HOLDING": 2, "DIALING": 3, "ALERTING": 4,
           "INCOMING": 5, "WAITING": 6, "DISCONNECTED": 7, "DISCONNECTING": 8}
NOMBRE_ESTADO = {1: "ACTIVA", 2: "EN_ESPERA", 3: "MARCANDO", 4: "TIMBRANDO", 5: "ENTRANTE", 6: "ENTRANTE"}
RE_PRECISO = re.compile(r"(?:mForegroundCallState=|Foreground call state:\s*)(-?\d+|[A-Z_]+)")
RE_BASICO = re.compile(r"mCallState=(\d)")


def interpretar_estado(volcado):
    """De la salida de `dumpsys telephony.registry` saca (preciso, ocupado).
    preciso: LIBRE / MARCANDO / TIMBRANDO / ACTIVA..., o None si el equipo no lo informa.
    ocupado: True si hay una llamada en curso, False si no, None si no se sabe."""
    crudos = RE_PRECISO.findall(volcado)
    preciso = None
    if crudos:
        vals = [int(v) if v.lstrip("-").isdigit() else PRECISO.get(v, -1) for v in crudos]
        vivos = [v for v in vals if v in NOMBRE_ESTADO]  # varias SIM: gana la que tenga llamada
        preciso = NOMBRE_ESTADO[vivos[0]] if vivos else "LIBRE"
    basicos = RE_BASICO.findall(volcado)
    ocupado = any(b != "0" for b in basicos) if basicos else None
    return preciso, ocupado


PAQUETE_SONIDO = "co.axiosgroup.marcadorsonido"


class Telefono:
    def __init__(self, adb):
        self.adb = adb

    def _run(self, *args, timeout=10):
        if not self.adb:
            return ""
        try:
            return subprocess.run([self.adb, *args], capture_output=True, text=True, timeout=timeout,
                                  creationflags=NO_WIN, errors="replace").stdout
        except (subprocess.TimeoutExpired, OSError):
            return ""

    def conexion(self):
        """(estado, serial) con estado: sin_adb / ninguno / sin_autorizar / desconectado / listo."""
        if not self.adb:
            return "sin_adb", ""
        lineas = [l.split("\t") for l in self._run("devices", timeout=20).splitlines() if "\t" in l]
        if not lineas:
            return "ninguno", ""
        for serial, est in lineas:
            if est.strip() == "device":
                return "listo", serial
        est = lineas[0][1].strip()
        return ("sin_autorizar" if est == "unauthorized" else "desconectado"), lineas[0][0]

    def preparar(self):
        self._run("shell", "svc", "power", "stayon", "usb")  # pantalla encendida con el cable puesto

    def modelo(self):
        return (self._run("shell", "getprop", "ro.product.manufacturer").strip() + " "
                + self._run("shell", "getprop", "ro.product.model").strip()).strip()

    def estado(self):
        return interpretar_estado(self._run("shell", "dumpsys", "telephony.registry"))

    def marcar(self, num):
        self._run("shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{num}")

    def colgar(self):
        self._run("shell", "input", "keyevent", "KEYCODE_ENDCALL")

    # --- aplicación auxiliar de sonido en el celular ---
    def instalar_sonido(self, apk):
        """Instala (o actualiza) la aplicación auxiliar si hace falta. True si quedó lista."""
        if not (self.adb and os.path.exists(apk)):
            return False
        ruta = self._run("shell", "pm", "path", PAQUETE_SONIDO).strip().replace("package:", "").split("\n")[0]
        if ruta and self._run("shell", "stat", "-c", "%s", ruta).strip() == str(os.path.getsize(apk)):
            return True  # ya está la misma versión
        salida = self._run("install", "-r", apk, timeout=180)
        if "Success" not in salida and ruta:  # firmada con otra llave: quitar la anterior y reinstalar
            self._run("uninstall", PAQUETE_SONIDO, timeout=60)
            salida = self._run("install", apk, timeout=180)
        if "Success" not in salida:
            return False
        self._run("shell", "pm", "grant", PAQUETE_SONIDO, "android.permission.POST_NOTIFICATIONS")
        return True

    def sonido(self, accion, *extra):
        """Ordena PLAY / PAUSE / SAY / STOP a la aplicación auxiliar. True si el celular aceptó."""
        salida = self._run("shell", "am", "start-foreground-service", "-n", f"{PAQUETE_SONIDO}/.Sonido",
                           "-a", accion, *extra)
        return "Starting service" in salida and "Error" not in salida and "Exception" not in salida

    def cerrar_sonido(self):
        """Cierra del todo la aplicación auxiliar (primero devuelve el volumen de llamada)."""
        self.sonido("STOP")
        self._run("shell", "am", "force-stop", PAQUETE_SONIDO)

    def decir(self, texto):
        """Dice el texto con la voz del celular. Devuelve los segundos que conviene esperar, o 0 si falló."""
        t = base64.urlsafe_b64encode(texto.encode("utf-8")).decode("ascii")
        return 3 + len(texto) / 12 if self.sonido("SAY", "--es", "t", t) else 0

    def apagar_servidor(self):
        self._run("kill-server")


# ---------------------------------------------------------------- una llamada

EFECTIVOS = ("CONTESTO", "POSIBLE_BUZON")


def una_llamada(tel, num, timbre_max, ev_colgar, ev_retener, asistido=False,
                al_cambiar=lambda e: None, paso=0.4):
    """Marca y vigila la llamada. Devuelve (resultado, asistido):
    CONTESTO / POSIBLE_BUZON -> la llamada sigue abierta para que la persona hable.
    NO_CONTESTA / NO_CONECTO / ERROR_MARCADO / COLGADO_MANUAL -> ya no hay llamada.
    Si el celular no informa el estado detallado, pasa solo a modo asistido."""
    ev_colgar.clear()
    ev_retener.clear()
    tel.marcar(num)
    t0 = time.monotonic()
    t_timbre = t_ocupado = None
    visto = False
    ultimo = None
    while True:
        if ev_retener.is_set():
            return "CONTESTO", asistido
        if ev_colgar.is_set():
            tel.colgar()
            return "COLGADO_MANUAL", asistido
        preciso, ocupado = tel.estado()
        ahora = time.monotonic()
        trans = ahora - t0
        if ocupado and t_ocupado is None:
            t_ocupado = ahora
        if not asistido and preciso in (None, "LIBRE") and t_ocupado and ahora - t_ocupado > 5:
            asistido = True  # hay llamada pero el equipo no dice en qué va
            al_cambiar("ASISTIDO")
        e = None if asistido else preciso
        if e != ultimo and e:
            ultimo = e
            al_cambiar(e)
        if e in ("MARCANDO", "TIMBRANDO", "ACTIVA") or ocupado:
            visto = True
        if e == "TIMBRANDO" and t_timbre is None:
            t_timbre = ahora
        if e == "ACTIVA":
            # "contestó" sin haber timbrado casi nunca es una persona
            return ("POSIBLE_BUZON" if t_timbre is None and trans < 6 else "CONTESTO"), asistido
        libre = (e == "LIBRE" and not ocupado) if not asistido else (ocupado is False)
        if libre and visto:
            return "NO_CONECTO", asistido  # ocupado, rechazada, apagado o número errado
        if libre and not visto and trans > 8:
            return "ERROR_MARCADO", asistido
        if trans > timbre_max:
            tel.colgar()
            time.sleep(min(1.5, paso * 4))
            return "NO_CONTESTA", asistido
        time.sleep(paso)


def esperar_fin(tel, ev_colgar, detenido, paso=0.7):
    """Espera, sin hacer nada, a que la conversación termine (cuelgan en el celular,
    cuelga la otra persona o se presiona Colgar en la aplicación)."""
    while not detenido.is_set():
        if ev_colgar.is_set():
            tel.colgar()
            return
        preciso, ocupado = tel.estado()
        if ocupado is False or (ocupado is None and preciso == "LIBRE"):
            return
        time.sleep(paso)


# ---------------------------------------------------------------- Ley 2300: horarios y festivos


def _pascua(a):
    g, c = a % 19, a // 100
    h = (c - c // 4 - (8 * c + 13) // 25 + 19 * g + 15) % 30
    i = h - (h // 28) * (1 - (h // 28) * (29 // (h + 1)) * ((21 - g) // 11))
    j = (a + a // 4 + i + 2 - c + c // 4) % 7
    p = i - j
    return dt.date(a, 3 + (p + 40) // 44, p + 28 - 31 * ((3 + (p + 40) // 44) // 4))


def festivos_colombia(anio):
    """Festivos nacionales (Ley 51 de 1983, 'Ley Emiliani')."""
    def lunes(d):
        return d + dt.timedelta(days=(7 - d.weekday()) % 7)
    fijos = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
    movibles = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]
    p = _pascua(anio)
    f = {dt.date(anio, m, d) for m, d in fijos}
    f |= {lunes(dt.date(anio, m, d)) for m, d in movibles}
    f |= {p + dt.timedelta(days=n) for n in (-3, -2, 43, 64, 71)}
    return f


def horario_permitido(a=None):
    """Lunes a viernes 7:00-19:00, sábados 8:00-15:00; nunca domingos ni festivos."""
    a = a or dt.datetime.now()
    if a.weekday() == 6 or a.date() in festivos_colombia(a.year):
        return False
    if a.weekday() == 5:
        return dt.time(8) <= a.time() < dt.time(15)
    return dt.time(7) <= a.time() < dt.time(19)


# ---------------------------------------------------------------- listas y registro


def normalizar(telefono):
    s = str(telefono or "").strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]  # Excel guardó el número como 3001234567.0
    d = re.sub(r"\D", "", s)
    if d.startswith("57") and len(d) == 12:
        d = d[2:]
    return d if len(d) >= 7 else ""


def _clave(txt):
    s = unicodedata.normalize("NFD", str(txt or "").strip().lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


COL_TEL = ("telefono", "celular", "numero", "movil", "tel")
COL_NOM = ("nombre", "cliente", "contacto", "razon social")


def leer_lista(ruta):
    """Lee .xlsx o .csv con columnas de nombre y teléfono. Devuelve (contactos, descartados)."""
    if ruta.lower().endswith(".csv"):
        with open(ruta, encoding="utf-8-sig", errors="replace", newline="") as f:
            muestra = f.read(4096)
            f.seek(0)
            sep = ";" if muestra.count(";") > muestra.count(",") else ","
            filas = list(csv.reader(f, delimiter=sep))
    else:
        import openpyxl
        wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        filas = [list(r) for r in wb.active.iter_rows(values_only=True)]
        wb.close()
    filas = [r for r in filas if any(c not in (None, "") for c in r)]
    if not filas:
        raise ValueError("El archivo está vacío.")
    enc = [_clave(c) for c in filas[0]]
    i_tel = next((i for i, c in enumerate(enc) if c in COL_TEL), None)
    i_nom = next((i for i, c in enumerate(enc) if c in COL_NOM), None)
    if i_tel is None:
        raise ValueError("No encuentro la columna 'telefono'. La primera fila del archivo "
                         "debe tener los títulos: nombre y telefono.")
    contactos, descartados, vistos = [], 0, set()
    for r in filas[1:]:
        num = normalizar(r[i_tel] if i_tel < len(r) else "")
        if not num or num in vistos:
            descartados += 1
            continue
        vistos.add(num)
        nom = r[i_nom] if i_nom is not None and i_nom < len(r) and r[i_nom] else "(sin nombre)"
        contactos.append({"nombre": str(nom).strip(), "telefono": num})
    return contactos, descartados


def crear_plantilla(ruta):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["nombre", "telefono"])
    ws.append(["Ejemplo Pérez", "3001234567"])
    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 18
    wb.save(ruta)


ENCABEZADO = ["fecha_hora", "nombre", "telefono", "resultado", "nota"]


def registrar(nombre, telefono, resultado, nota="", ruta=None):
    """Agrega una fila al registro (evidencia de gestión). Formato que Excel abre directo."""
    ruta = ruta or ruta_log()
    fila = [dt.datetime.now().isoformat(timespec="seconds"), nombre, telefono, resultado, nota]
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8") as f:
        w = csv.writer(f, delimiter=";")
        if nuevo:
            w.writerow(ENCABEZADO)
        w.writerow(fila)
    return fila


def contactado_esta_semana(telefono, ruta=None, hoy=None):
    """Ley 2300: ya hubo un contacto efectivo con este número en la semana en curso."""
    ruta = ruta or ruta_log()
    if not os.path.exists(ruta):
        return False
    semana = (hoy or dt.date.today()).isocalendar()[:2]
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.reader(f, delimiter=";"):
            if len(fila) >= 4 and fila[2] == telefono and fila[3] in EFECTIVOS:
                try:
                    if dt.datetime.fromisoformat(fila[0]).date().isocalendar()[:2] == semana:
                        return True
                except ValueError:
                    pass
    return False


# ---------------------------------------------------------------- mensajes sorpresa

# Cada mensaje: (texto que se muestra, texto que lee la voz). Se dicen una sola vez, al
# completar 5, 15, 50 y 100 llamadas realizadas y luego cada 50 (150, 200, ...).
MENSAJES = [
    ("Hola esposa, veo que estás utilizando la aplicación que con mucho amor hice, sigue así juiciosa "
     "trabajando JAJAJAJA, perdón si te asusté, pasaba solo a recordar que te amo",
     "Hola esposa, veo que estás utilizando la aplicación que con mucho amor hice. Sigue así, juiciosa "
     "trabajando. Ja ja ja ja. Perdón si te asusté, pasaba solo a recordar que te amo."),
    ("Mmm, ¿sigues aquí? Trabajas demasiado JAJAJA deberías tomarte un break o espera, ya me encargué "
     "yo de ello JEJE sigue trabajando, te amo",
     "Mmm, ¿sigues aquí? Trabajas demasiado. Ja ja ja. Deberías tomarte un breik. O espera, ya me "
     "encargué yo de ello. Je je. Sigue trabajando, te amo."),
    ("Uff, hace tiempo que no me escuchabas, ¿verdad? Bueno, qué te digo, pensé que sería muy pesado "
     "si saliera demasiado seguido, solo recuerda que te amo :D",
     "Uf, hace tiempo que no me escuchabas, ¿verdad? Bueno, qué te digo, pensé que sería muy pesado "
     "si saliera demasiado seguido. Solo recuerda que te amo."),
    ("Owo, no me has olvidado, ¿verdad? Ando por acá recordándote que te amo y que tas muy juiciosa "
     "trabajando :D",
     "Oh, no me has olvidado, ¿verdad? Ando por acá recordándote que te amo, y que estás muy juiciosa "
     "trabajando."),
    ("¿Creíste que había desaparecido? Soy omnipresente MUAJAJAJA siempre estoy esperando el momento "
     "para interrumpirte",
     "¿Creíste que había desaparecido? Soy omnipresente. Mua ja ja ja. Siempre estoy esperando el "
     "momento para interrumpirte."),
    ("Bueno bueno, ya se está haciendo aburrido para ti tener que pasar por mis múltiples "
     "interrupciones, ¿verdad? Para mí también es difícil crear tantos mensajes... ¿qué tal si hago "
     "otros 100 y paramos, va? JAJAJA MUAK",
     "Bueno, bueno. Ya se está haciendo aburrido para ti tener que pasar por mis múltiples "
     "interrupciones, ¿verdad? Para mí también es difícil crear tantos mensajes. ¿Qué tal si hago "
     "otros cien y paramos, va? Ja ja ja. Muac."),
    ("Uff, ¡sí que me has usado, eh! Ni yo pensé que llegarías acá, no sé qué más decir la verdad... "
     "mmm, te amo :D sigue trabajando :D",
     "Uf, ¡sí que me has usado, eh! Ni yo pensé que llegarías acá. No sé qué más decir, la verdad. "
     "Mmm, te amo. Sigue trabajando."),
    ("Bueno, de aquí en adelante le pediré a mi asistente que haga mensajes bonitos y yo los aprobaré "
     "xD llevo más escribiendo los mensajes que lo que tardé en programar la app",
     "Bueno, de aquí en adelante le pediré a mi asistente que haga mensajes bonitos, y yo los "
     "aprobaré. Llevo más tiempo escribiendo los mensajes que lo que tardé en programar la aplicación."),
]


# De 350 en adelante: un solo texto; lo que lee la voz se deriva con para_voz().
MENSAJES_SIGUIENTES = [
    # 350
    "Hola otra vez, aquí el asistente de tu esposo reportándose. Me pidió que te dijera algo bonito, pero "
    "la verdad él lo dice mejor: te ama. Yo solo paso el recado JAJAJA",
    "¡Cuatrocientas llamadas! A este paso vas a dejar sin trabajo al celular. Tómate un vasito de agua, "
    "estira las piernas y acuérdate de que alguien te ama mucho",
    "Interrumpimos su jornada laboral para un anuncio importante: tu esposo te ama. Eso es todo, puede "
    "continuar. MUAK",
    "¡Quinientas! Esto ya merece premio. No sé cuál, pregúntale a tu esposo, yo solo soy la voz JEJE. Te "
    "ama, por si se te había olvidado en las últimas cincuenta llamadas",
    "¿Sabes qué es lo mejor de esta aplicación? Que la persona para la que se hizo eres tú. Sigue así de "
    "juiciosa, te amo",
    "Seiscientas llamadas y sigo aquí, fiel como siempre. Bueno, fiel cada cincuenta llamadas JAJAJA. Te "
    "amo, respira hondo y sigue",
    "Pausa de diez segundos patrocinada por tu esposo: cierra los ojos, respira... ya, listo. Te amo. A "
    "trabajar MUAJAJA",
    "Si estás oyendo esto es porque eres la persona más trabajadora que conozco. Estoy muy orgulloso de "
    "ti. Te amo, nos vemos en cincuenta llamadas",
    # 750
    "Setecientas cincuenta. Dato curioso: en todo este tiempo no he dejado de pensar en ti ni una sola "
    "llamada. Bueno, soy una grabación, pero la intención es real JAJAJA. Te amo",
    "Ochocientas llamadas. Si cobraras un beso por cada una, ya te debería ochocientos. Los pago esta "
    "noche, con intereses. MUAK",
    "Reporte del clima: cien por ciento de probabilidad de que tu esposo te ame hoy. Y mañana. Y pasado "
    "mañana. Sigue trabajando",
    "Novecientas. ¿Ya tomaste agua? ¿Ya estiraste la espalda? No me hagas ir hasta allá. Mentira, sí "
    "quiero ir hasta allá. Te amo",
    "Mensaje serio, sin risas: gracias por todo lo que haces. De verdad. Listo, ya, se acabó la seriedad "
    "JAJAJA. Te amo",
    # 1000
    "¡MIL LLAMADAS! Suenen las trompetas. Eres oficialmente una leyenda de esta aplicación. Tu esposo "
    "está orgullosísimo y te ama mil veces, una por cada llamada",
    "Mil cincuenta. Pensé que después de mil me iban a jubilar, pero aquí sigo, interrumpiéndote con "
    "cariño JEJE. Te amo",
    "Mil cien llamadas. Si alguna persona te contestó de mal genio hoy, que sepas que aquí hay alguien "
    "que siempre te contesta con amor",
    "Pregunta rápida: ¿quién es la esposa más juiciosa del mundo? Pista: está oyendo este mensaje. Te "
    "amo, sigue así",
    "Mil doscientas. A estas alturas ya debes conocer mi voz mejor que la de tus clientes JAJAJA. Solo "
    "paso a decirte que te amo",
    "Hora de un mini descanso: mueve los hombros, mira por la ventana y sonríe, que alguien está pensando "
    "en ti ahora mismo. Te amo",
    "Mil trescientas. Yo ya perdí la cuenta, menos mal la aplicación no. Lo que nunca pierdo de vista es "
    "que te amo. MUAK",
    "¿Sigues ahí? Claro que sigues ahí, si eres imparable. Ojalá yo tuviera tu disciplina JEJE. Te amo "
    "mucho",
    "Mil cuatrocientas llamadas. Propongo celebrar con tu comida favorita. Tú eliges, yo invito. Te amo",
    "Recordatorio amistoso: eres más que tu trabajo, y aun así lo haces increíble. Tu esposo te ama y te "
    "admira",
    # 1500
    "¡Mil quinientas! Esto ya es nivel experto. Si hubiera un diploma te lo estaría entregando ahora "
    "mismo, con beso incluido. MUAK",
    "Mil quinientas cincuenta. Te cuento un secreto: cada vez que suena este mensaje, alguien al otro "
    "lado sonríe imaginándote. Ese alguien te ama",
    "Mil seiscientas. No tengo nada nuevo que decir, así que repito lo importante: te amo, te amo, te "
    "amo. Listo, sigue JAJAJA",
    "Pausa activa obligatoria: párate, da una vuelta y vuelve. Yo te espero aquí, no me voy a ningún "
    "lado. Literalmente no puedo JEJE. Te amo",
    "Mil setecientas llamadas. Ya quedan poquitos mensajes, así que este va con doble dosis de cariño: te "
    "amo y te amo",
    "Si hoy fue un día pesado, respira. Lo estás haciendo muy bien. Y cuando termines, aquí hay alguien "
    "esperándote con un abrazo. Te amo",
    "Mil ochocientas. A este ritmo voy a tener que pedirle a mi asistente otro lote de mensajes. Mentira, "
    "ya casi se acaban. Disfrútalos. Te amo",
    "Mil ochocientas cincuenta. Gracias por tu paciencia con los clientes, con el celular, con esta "
    "aplicación y sobre todo conmigo JAJAJA. Te amo",
    "Mil novecientas llamadas. Penúltimo aviso de que alguien te ama con locura. El que sigue es de los "
    "últimos, no llores. Bueno, un poquito sí",
    "Mil novecientas cincuenta. Solo falta un mensaje más. He disfrutado mucho interrumpirte todo este "
    "tiempo. Prepárate para la despedida, te amo",
    # 2000
    "¡Dos mil llamadas! Este es mi último mensaje: mis abogados dicen que seguir interrumpiéndote después "
    "de dos mil llamadas ya cuenta como explotación laboral, y no quiero una demanda JAJAJA. Gracias por "
    "cada llamada. Ya no saldré más por aquí, pero te sigo amando todos los días. MUAK",
]


def para_voz(texto):
    """Adapta un mensaje para que la voz virtual lo lea natural (risas, besos y caritas)."""
    t = re.sub(r"\bMUAJ[AJ]*\b", "mua ja ja ja", texto)
    t = re.sub(r"\b(?:[JH]A){2,}[JH]?\b", "ja ja ja", t)
    t = re.sub(r"\b(?:JE){2,}\b", "je je", t)
    t = re.sub(r"\bMUAK\b", "muac", t)
    t = re.sub(r":D|xD", "", t)
    return re.sub(r"\s+", " ", t).strip()


MENSAJES += [(m, para_voz(m)) for m in MENSAJES_SIGUIENTES]


def indice_hito(n):
    """Posición en MENSAJES que corresponde a la llamada número n, o None si no es un hito."""
    primeros = {5: 0, 15: 1, 50: 2}
    if n in primeros:
        return primeros[n]
    if n >= 100 and n % 50 == 0:
        return 3 + (n - 100) // 50
    return None


def mensaje_para(n, ya_dichos=()):
    i = indice_hito(n)
    if i is None or i >= len(MENSAJES) or n in ya_dichos:
        return None
    return MENSAJES[i]
