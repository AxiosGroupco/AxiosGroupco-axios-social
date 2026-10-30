"""Genera la voz del guion con Piper y la línea de tiempo para animar la boca.

Uso: python voz.py guion.json voz.onnx salida_dir
Escribe salida_dir/voz.wav y salida_dir/tiempos.json (inicio y fin de cada línea, y la
apertura de boca por cuadro a 30 fps).
"""
import json, subprocess, sys, wave
from pathlib import Path

import numpy as np

FPS, INICIO, PAUSA, COLA = 30, 0.35, 0.18, 1.6

guion, modelo, salida = sys.argv[1], sys.argv[2], Path(sys.argv[3])
salida.mkdir(parents=True, exist_ok=True)
piper = str(Path(sys.executable).with_name('piper'))
lineas = json.load(open(guion, encoding='utf-8'))['lineas']

tasa, partes, tiempos, t = None, [], [], INICIO
for i, l in enumerate(lineas):
    tmp = salida / f'_l{i}.wav'
    subprocess.run([piper, '-m', modelo, '-f', str(tmp), '--length-scale', '0.92'],
                   input=l['voz'].encode(), check=True, capture_output=True)
    with wave.open(str(tmp)) as w:
        tasa = w.getframerate()
        partes.append(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16))
    dur = len(partes[-1]) / tasa
    tiempos.append({'inicio': round(t, 3), 'fin': round(t + dur, 3)})
    t += dur + PAUSA
    tmp.unlink()

total = t - PAUSA + COLA
audio = np.zeros(int(total * tasa), dtype=np.int16)
for parte, tm in zip(partes, tiempos):
    a = int(tm['inicio'] * tasa)
    audio[a:a + len(parte)] = parte

with wave.open(str(salida / 'voz.wav'), 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(tasa); w.writeframes(audio.tobytes())

# Apertura de boca: energía RMS por cuadro, normalizada y suavizada.
n = int(total * FPS)
paso = tasa // FPS
rms = np.array([np.sqrt(np.mean(audio[i * paso:(i + 1) * paso].astype(float) ** 2) + 1e-9) for i in range(n)])
boca = np.clip(rms / np.percentile(rms[rms > 50], 90), 0, 1) if (rms > 50).any() else rms * 0
boca = np.convolve(boca, [0.25, 0.5, 0.25], mode='same')

json.dump({'duracion': round(total, 3), 'lineas': tiempos, 'boca': [round(float(x), 3) for x in boca]},
          open(salida / 'tiempos.json', 'w', encoding='utf-8'))
print('duración', round(total, 2), 's ·', len(tiempos), 'líneas')
