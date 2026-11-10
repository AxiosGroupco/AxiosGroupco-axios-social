"""Comprobaciones que solo tienen sentido en Windows (las corre la compilación automática)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extras

PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
exe = os.path.abspath(sys.argv[1])

r = subprocess.run(PS + [extras._PS_ACCESO], env={**os.environ, "MARCADOR_EXE": exe}, capture_output=True, text=True)
print("acceso directo:", r.returncode, r.stderr.strip())
lnk = subprocess.run(PS + ["Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Marcador Axios.lnk')"],
                     capture_output=True, text=True).stdout.strip()
assert r.returncode == 0 and lnk == "True", "no se creó el acceso directo"

r = subprocess.run(PS + [extras._PS_VOZ], env={**os.environ, "MARCADOR_TEXTO": "Hola"}, capture_output=True, text=True)
print("voz (0 = habló, 2 = sin voz en español):", r.returncode, r.stderr.strip()[:300])
assert r.returncode in (0, 2), "el guion de voz falló"

ok, _ = extras._mci('open "%s" type mpegvideo alias prueba' % os.path.abspath("recursos/musica/01_ascensor.mp3"))
print("abrir mp3 con MCI:", ok)
assert ok, "Windows no pudo abrir el mp3"
extras._mci("close prueba")
