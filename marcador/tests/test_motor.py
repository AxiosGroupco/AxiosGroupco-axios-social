import datetime as dt
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import motor


class Falso:
    """Celular simulado: una secuencia de (preciso, ocupado) por cada consulta."""
    def __init__(self, guion):
        self.guion, self.i, self.colgadas, self.marcados = guion, 0, 0, []

    def marcar(self, n): self.marcados.append(n)
    def colgar(self): self.colgadas += 1

    def estado(self):
        e = self.guion[min(self.i, len(self.guion) - 1)]
        self.i += 1
        return e


def llamar(guion, timbre=1.0, asistido=False, retener=False):
    t, col, ret = Falso(guion), threading.Event(), threading.Event()
    if retener:
        threading.Timer(0.15, ret.set).start()
    res = motor.una_llamada(t, "3001234567", timbre, col, ret, asistido=asistido, paso=0.02)
    return res, t


M, T, A, L = ("MARCANDO", True), ("TIMBRANDO", True), ("ACTIVA", True), ("LIBRE", False)


def test_contesta_se_detiene_sin_colgar():
    (res, asis), t = llamar([L, M, T, T, T, A])
    assert res == "CONTESTO" and not asis and t.colgadas == 0 and t.marcados == ["3001234567"]


def test_no_contesta_cuelga_y_sigue():
    (res, _), t = llamar([M] + [T] * 500, timbre=0.3)
    assert res == "NO_CONTESTA" and t.colgadas == 1


def test_ocupado_o_rechazada():
    (res, _), t = llamar([M, T, L])
    assert res == "NO_CONECTO" and t.colgadas == 0


def test_activa_sin_timbrar_es_posible_buzon():
    (res, _), _t = llamar([M, A])
    assert res == "POSIBLE_BUZON"


def test_asistido_boton_retiene():
    (res, asis), t = llamar([(None, True)] * 500, timbre=2, asistido=True, retener=True)
    assert res == "CONTESTO" and asis and t.colgadas == 0


def test_asistido_no_contesta():
    (res, _), t = llamar([(None, None)] * 500, timbre=0.2, asistido=True)
    assert res == "NO_CONTESTA" and t.colgadas == 1


def test_cambia_solo_a_asistido(monkeypatch):
    reloj = iter(x * 0.5 for x in range(10_000))
    monkeypatch.setattr(motor.time, "monotonic", lambda: next(reloj))
    monkeypatch.setattr(motor.time, "sleep", lambda s: None)
    (res, asis), t = llamar([("LIBRE", True)] * 10_000, timbre=25)
    assert asis and res == "NO_CONTESTA" and t.colgadas == 1


def test_esperar_fin():
    t = Falso([A, A, A, L])
    motor.esperar_fin(t, threading.Event(), threading.Event(), paso=0.01)
    assert t.i == 4 and t.colgadas == 0


def test_interpretar_estado():
    nuevo = "mCallState=2\n mForegroundCallState=4\n mCallState=0\n mForegroundCallState=0\n"
    assert motor.interpretar_estado(nuevo) == ("TIMBRANDO", True)
    assert motor.interpretar_estado("Foreground call state: ACTIVE\nmCallState=2") == ("ACTIVA", True)
    assert motor.interpretar_estado("mCallState=0\nmForegroundCallState=-1") == ("LIBRE", False)
    assert motor.interpretar_estado("nada") == (None, None)


def test_festivos_2026():
    esperado = {(1, 1), (1, 12), (3, 23), (4, 2), (4, 3), (5, 1), (5, 18), (6, 8), (6, 15), (6, 29),
                (7, 20), (8, 7), (8, 17), (10, 12), (11, 2), (11, 16), (12, 8), (12, 25)}
    assert {(d.month, d.day) for d in motor.festivos_colombia(2026)} == esperado


def test_horario():
    h = motor.horario_permitido
    assert h(dt.datetime(2026, 11, 10, 7, 0)) and not h(dt.datetime(2026, 11, 10, 19, 0))
    assert h(dt.datetime(2026, 11, 14, 14, 59)) and not h(dt.datetime(2026, 11, 14, 15, 0))
    assert not h(dt.datetime(2026, 11, 15, 10, 0))      # domingo
    assert not h(dt.datetime(2026, 11, 16, 10, 0))      # festivo (lunes)


def test_normalizar():
    n = motor.normalizar
    assert n("+57 300 123 4567") == "3001234567" and n("3001234567.0") == "3001234567"
    assert n("(601) 123-4567") == "6011234567" and n("abc") == "" and n(None) == ""


def test_lista_y_registro(tmp_path):
    csv_ = tmp_path / "l.csv"
    csv_.write_text("Nombre;Teléfono\nAna;300 123 4567\nAna2;3001234567\nSin;\nLuis;+573109876543\n", encoding="utf-8")
    cs, desc = motor.leer_lista(str(csv_))
    assert [c["telefono"] for c in cs] == ["3001234567", "3109876543"] and desc == 2
    x = tmp_path / "p.xlsx"
    motor.crear_plantilla(str(x))
    assert motor.leer_lista(str(x))[0] == [{"nombre": "Ejemplo Pérez", "telefono": "3001234567"}]
    log = str(tmp_path / "r.csv")
    motor.registrar("Ana", "3001234567", "NO_CONTESTA", ruta=log)
    assert not motor.contactado_esta_semana("3001234567", ruta=log)
    motor.registrar("Ana", "3001234567", "CONTESTO", "pagará; el viernes", ruta=log)
    assert motor.contactado_esta_semana("3001234567", ruta=log)
    assert not motor.contactado_esta_semana("3001234567", ruta=log, hoy=dt.date.today() + dt.timedelta(days=7))


def test_hitos_de_mensajes():
    hitos = [n for n in range(1, 2201) if motor.indice_hito(n) is not None]
    assert hitos[:8] == [5, 15, 50, 100, 150, 200, 250, 300] and hitos[-5:] == [2000, 2050, 2100, 2150, 2200]
    assert [motor.indice_hito(n) for n in hitos[:8]] == list(range(8))
    assert motor.mensaje_para(5)[0].startswith("Hola esposa")
    assert motor.mensaje_para(300)[0].startswith("Bueno, de aquí en adelante")
    assert motor.mensaje_para(350)[0].startswith("Hola otra vez")
    assert motor.mensaje_para(1000)[0].startswith("¡MIL LLAMADAS!")
    assert "explotación laboral" in motor.mensaje_para(2000)[0]
    assert all(motor.mensaje_para(n) for n in hitos if n <= 2000)
    assert motor.mensaje_para(2050) is None                  # después de 2000 no hay más
    assert motor.mensaje_para(5, ya_dichos=[5]) is None      # una sola vez
    assert motor.mensaje_para(6) is None


def test_para_voz():
    v = motor.para_voz("yo solo paso el recado JAJAJA")
    assert v.endswith("ja ja ja") and "JAJAJA" not in v
    assert motor.para_voz("A trabajar MUAJAJA") == "A trabajar mua ja ja ja"
    assert motor.para_voz("puede continuar. MUAK") == "puede continuar. muac"
    for _texto, voz in motor.MENSAJES[8:]:
        assert not any(x in voz for x in ("JAJA", "JEJE", "MUAK", "MUAJ", ":D"))


class AdbFalso(motor.Telefono):
    def __init__(self, respuestas):
        super().__init__("adb")
        self.respuestas, self.ordenes = respuestas, []

    def _run(self, *args, timeout=10):
        self.ordenes.append(args)
        for clave, resp in self.respuestas.items():
            if clave in " ".join(args):
                return resp
        return ""


def test_sonido_del_celular(tmp_path):
    apk = tmp_path / "a.apk"
    apk.write_bytes(b"x" * 100)
    t = AdbFalso({"pm path": "package:/data/app/base.apk\n", "stat": "100\n"})
    assert t.instalar_sonido(str(apk)) and not any(o[0] == "install" for o in t.ordenes)   # ya instalada
    t = AdbFalso({"install": "Performing Streamed Install\nSuccess\n"})
    assert t.instalar_sonido(str(apk)) and any(o[0] == "install" for o in t.ordenes)
    assert not AdbFalso({"install": "Failure [INSTALL_FAILED_USER_RESTRICTED]"}).instalar_sonido(str(apk))
    ok = AdbFalso({"start-foreground-service": "Starting service: Intent { act=PLAY }"})
    assert ok.sonido("PLAY", "--ei", "vol", "25") and ok.decir("Hola, ¿cómo estás?") > 3
    assert "--es" in ok.ordenes[-1] and " " not in ok.ordenes[-1][-1]      # el texto viaja codificado
    assert not AdbFalso({"start-foreground-service": "Error: app is in background"}).sonido("PLAY")


def test_cerrar_sonido_del_celular():
    t = AdbFalso({"start-foreground-service": "Starting service: Intent { act=STOP }"})
    t.cerrar_sonido()
    assert "STOP" in t.ordenes[0] and "force-stop" in t.ordenes[1]
