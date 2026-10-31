"""Prepara la voz grabada y calcula los tiempos del video.

1. Limpia el audio con ffmpeg: quita ruidos graves, reduce el ruido de fondo, comprime y
   normaliza a -14 LUFS (el nivel que usan TikTok e Instagram).
2. Transcribe con Whisper (faster-whisper, modelo "small", en español) con tiempos por palabra.
3. Ubica el inicio de cada escena buscando su `inicio_texto` (escenas.json) en la transcripción.
4. Calcula la apertura de boca por cuadro (30 fps) a partir del volumen de la voz.

Uso: python audio_a_tiempos.py voz_original.m4a salida_dir
Escribe salida_dir/voz_limpia.wav, salida_dir/tiempos.json y salida_dir/transcripcion.txt.
"""
import json
import subprocess
import sys
import unicodedata
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

FPS = 30
AQUI = Path(__file__).resolve().parent

entrada, salida = sys.argv[1], Path(sys.argv[2])
salida.mkdir(parents=True, exist_ok=True)
limpia = salida / 'voz_limpia.wav'

filtro = ('highpass=f=80,afftdn=nf=-25,'
          'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,'
          'areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.3,areverse,'
          'acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-14:TP=-1.5:LRA=9')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', entrada, '-af', filtro, '-ar', '48000', '-ac', '1', str(limpia)], check=True)

modelo = WhisperModel('small', device='cpu', compute_type='int8')
segmentos, _ = modelo.transcribe(str(limpia), language='es', word_timestamps=True, vad_filter=True)
palabras = []
for seg in segmentos:
    for w in seg.words:
        palabras.append({'w': w.word.strip(), 'ini': round(w.start, 3), 'fin': round(w.end, 3)})
(salida / 'transcripcion.txt').write_text(' '.join(p['w'] for p in palabras), encoding='utf-8')

def norm(t):
    t = unicodedata.normalize('NFD', t.lower())
    return ''.join(c for c in t if c.isalnum() or c == ' ').replace('  ', ' ').strip()

with wave.open(str(limpia)) as w:
    tasa = w.getframerate(); audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
duracion = len(audio) / tasa

escenas = json.loads((AQUI / 'escenas.json').read_text(encoding='utf-8'))['escenas']
lista = [norm(p['w']) for p in palabras]
inicios, desde = [], 0
for e in escenas:
    objetivo = norm(e['inicio_texto']).split()
    hallado = None
    for k in range(desde, len(lista) - len(objetivo) + 1):
        if lista[k:k + len(objetivo)] == objetivo:
            hallado = k; break
    if hallado is None:
        print('No encontré el inicio de la escena', e['id'], '->', e['inicio_texto'])
        hallado = desde
    inicios.append(palabras[hallado]['ini'] if palabras else 0.0)
    desde = hallado + 1
inicios[0] = 0.0
tiempos_escenas = [{'inicio': round(a, 3), 'fin': round(b, 3)} for a, b in zip(inicios, inicios[1:] + [duracion])]

paso = tasa // FPS
n = int(duracion * FPS)
rms = np.array([np.sqrt(np.mean(audio[i * paso:(i + 1) * paso] ** 2) + 1e-9) for i in range(n)])
ref = np.percentile(rms[rms > np.percentile(rms, 30)], 90) if n else 1
boca = np.convolve(np.clip(rms / ref, 0, 1), [0.25, 0.5, 0.25], mode='same')

json.dump({'duracion': round(duracion + 1.5, 3), 'escenas': tiempos_escenas, 'palabras': palabras,
           'boca': [round(float(x), 3) for x in boca]}, open(salida / 'tiempos.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'duración {duracion:.1f} s · {len(palabras)} palabras · escenas en', [e['inicio'] for e in tiempos_escenas])
