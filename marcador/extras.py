"""Extras de Windows: música mientras timbra, voz de los mensajes sorpresa y acceso
directo en el escritorio. Fuera de Windows todo esto no hace nada (y no falla)."""
import glob
import os
import random
import shutil
import subprocess
import sys

import motor

ES_WINDOWS = os.name == "nt"


def _mci(orden):
    """Envía una orden al reproductor multimedia de Windows (MCI). Devuelve (ok, respuesta)."""
    if not ES_WINDOWS:
        return False, ""
    import ctypes
    buf = ctypes.create_unicode_buffer(256)
    err = ctypes.windll.winmm.mciSendStringW(orden, buf, 255, 0)
    return err == 0, buf.value


def carpeta_musica_propia():
    d = os.path.join(motor.carpeta_datos(), "musica")
    os.makedirs(d, exist_ok=True)
    return d


class Musica:
    """Lista de reproducción en orden aleatorio. Usar siempre desde el hilo de la interfaz
    (MCI exige que abra y controle el sonido el mismo hilo)."""
    ALIAS = "marcador_musica"

    def __init__(self, carpeta_incluida):
        self.carpetas = [carpeta_incluida, carpeta_musica_propia()]
        self.cola, self.abierta, self.sonando, self.volumen = [], False, False, 25

    def _siguiente(self):
        if not self.cola:
            self.cola = [p for c in self.carpetas for p in glob.glob(os.path.join(c, "*.mp3"))]
            random.shuffle(self.cola)
        return self.cola.pop() if self.cola else None

    def _abrir_otra(self):
        if self.abierta:
            _mci(f"close {self.ALIAS}")
            self.abierta = False
        for _ in range(3):  # si un archivo no abre, prueba con otro
            ruta = self._siguiente()
            if not ruta:
                return False
            if _mci(f'open "{ruta}" type mpegvideo alias {self.ALIAS}')[0]:
                self.abierta = True
                self.poner_volumen(self.volumen)
                return True
        return False

    def poner_volumen(self, porcentaje):
        self.volumen = max(0, min(100, int(porcentaje)))
        if self.abierta:
            _mci(f"setaudio {self.ALIAS} volume to {self.volumen * 10}")

    def sonar(self):
        """Empieza o continúa la música donde iba."""
        self.sonando = True
        if self.abierta or self._abrir_otra():
            _mci(f"play {self.ALIAS}")

    def callar(self):
        self.sonando = False
        if self.abierta:
            _mci(f"pause {self.ALIAS}")

    def latido(self):
        """Llamar cada segundo: cuando una pieza termina, pasa a la siguiente."""
        if self.sonando and self.abierta and _mci(f"status {self.ALIAS} mode")[1] == "stopped":
            if self._abrir_otra():
                _mci(f"play {self.ALIAS}")

    def cerrar(self):
        self.sonando = False
        if self.abierta:
            _mci(f"close {self.ALIAS}")
            self.abierta = False


_PS_VOZ = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = @($s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'es*' })
if ($v.Count -eq 0) { exit 2 }
$h = @($v | Where-Object { $_.VoiceInfo.Gender -eq 'Male' })
if ($h.Count -gt 0) { $v = $h }
$s.SelectVoice($v[0].VoiceInfo.Name)
$s.Rate = -1
$s.Speak($env:MARCADOR_TEXTO)
"""


def decir(texto, numero=None):
    """Dice el mensaje y espera a que termine (llamar desde el hilo de trabajo).
    Si existe una grabación propia en Documentos\\MarcadorAxios\\mensajes\\<numero>.mp3 o .wav,
    suena esa en lugar de la voz virtual. Devuelve True si algo sonó."""
    if not ES_WINDOWS:
        return False
    if numero is not None:
        for ext, tipo in (("mp3", "mpegvideo"), ("wav", "waveaudio")):
            ruta = os.path.join(motor.carpeta_datos(), "mensajes", f"{numero}.{ext}")
            if os.path.exists(ruta) and _mci(f'open "{ruta}" type {tipo} alias marcador_voz')[0]:
                _mci("play marcador_voz wait")
                _mci("close marcador_voz")
                return True
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_VOZ],
                           env={**os.environ, "MARCADOR_TEXTO": texto}, timeout=120,
                           creationflags=motor.NO_WIN, capture_output=True)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_PS_ACCESO = r"""
$escritorio = [Environment]::GetFolderPath('Desktop')
$a = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $escritorio 'Marcador Axios.lnk'))
$a.TargetPath = $env:MARCADOR_EXE
$a.WorkingDirectory = Split-Path $env:MARCADOR_EXE
$a.IconLocation = "$($env:MARCADOR_EXE),0"
$a.Description = 'Marcador Axios: llamadas una por una'
$a.Save()
"""


def instalar():
    """Deja una copia del programa en Documentos\\MarcadorAxios (junto a los registros) y
    un acceso directo en el escritorio. Solo actúa cuando corre como .exe. Si se abre un
    .exe más nuevo desde otra carpeta, actualiza la copia instalada."""
    if not (ES_WINDOWS and getattr(sys, "frozen", False)):
        return
    try:
        origen = os.path.abspath(sys.executable)
        destino = os.path.join(motor.carpeta_datos(), "MarcadorAxios.exe")
        if os.path.normcase(origen) != os.path.normcase(destino):
            a = os.stat(origen)
            if not os.path.exists(destino) or (os.path.getsize(destino), int(os.path.getmtime(destino))) != (
                    a.st_size, int(a.st_mtime)):
                shutil.copy2(origen, destino)
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_ACCESO],
                       env={**os.environ, "MARCADOR_EXE": destino if os.path.exists(destino) else origen},
                       timeout=60, creationflags=motor.NO_WIN, capture_output=True)
    except (OSError, subprocess.TimeoutExpired):
        pass  # sin acceso directo la aplicación funciona igual
