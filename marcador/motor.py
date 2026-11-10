"""Motor del marcador progresivo: control del celular por adb, reglas de horario
(Ley 2300 de 2023), lectura de listas y registro de resultados. No depende de la
interfaz gráfica, para poder probarlo de forma automática."""
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


CONFIG_DEFECTO = {"timbre_max_s": 25, "pausa_s": 3, "cobranza": True, "modo": {}}


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
