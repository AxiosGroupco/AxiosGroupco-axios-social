"""Calcula los tiempos del video a partir de la voz ya procesada (ver voz_locutor.sh).

1. Transcribe con Whisper (faster-whisper, modelo "small", en español) con tiempos por palabra.
2. Corrige en los subtítulos las palabras que Whisper suele confundir (UVT, Axios, gravable...).
3. Ubica el inicio de cada escena buscando su `inicio_texto` (escenas.json) en la transcripción.
4. Calcula la apertura de boca por cuadro (30 fps) a partir del volumen de la voz.

Uso: python audio_a_tiempos.py voz_recortada.wav voz_final.wav salida_dir
(la transcripción sale de la voz natural recortada; la boca y la duración, de la voz final; ambas tienen los mismos tiempos)
Escribe salida_dir/tiempos.json y salida_dir/transcripcion.txt.
"""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

FPS = 30
AQUI = Path(__file__).resolve().parent

natural, voz, salida = sys.argv[1], sys.argv[2], Path(sys.argv[3])
salida.mkdir(parents=True, exist_ok=True)

def cargar(f, sr):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', f, '-f', 's16le', '-ac', '1', '-ar', str(sr), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768

def norm(t):
    t = unicodedata.normalize('NFD', t.lower())
    return ''.join(c for c in t if c.isalnum())

modelo = WhisperModel('small', device='cpu', compute_type='int8')
segmentos, _ = modelo.transcribe(cargar(natural, 16000), language='es', word_timestamps=True, vad_filter=True)
palabras = [{'w': w.word.strip(), 'ini': round(w.start, 3), 'fin': round(w.end, 3)} for s in segmentos for w in s.words]

# Correcciones para los subtítulos: secuencia que oye Whisper -> texto correcto
CORRECCIONES = [
    (['red', 'de', '60'], ['renta', 'exenta']), (['aporta', 'salud'], ['aporte', 'a', 'salud']),
    (['que', 'haria'], ['quedaría']), (['si', 'haga'], ['sí', 'haga']), (['explico'], ['explico']),
    (['vt'], ['UVT']), (['grabable'], ['gravable']), (['actios'], ['Axios']), (['axios'], ['Axios']),
    (['describanos'], ['escríbanos']), (['gobierno'], ['Gobierno']), (['mora'], ['mora']),
    (['1090'], ['1.090']), (['1000'], ['1.000']), (['palabra', 'reforma'], ['palabra', 'REFORMA']),
    (['si', 'ya', 'se', 'ha', 'salariado'], ['Si', 'es', 'asalariado']), (['recta', 'excenta'], ['renta', 'exenta']),
    (['renta', 'excenta'], ['renta', 'exenta']), (['camara'], ['Cámara']), (['cena'], ['Sena']),
    (['trabajos', 'de', 'hasta'], ['trabajadores', 'de', 'hasta']), (['la', '720'], ['las', '720']),
]
def corregir(ps):
    # Une decimales que Whisper separa ("13" + ".5%" -> "13.5%")
    unidas = []
    for p in ps:
        if unidas and ((re.match(r'^[.,]\d', p['w']) and re.match(r'^\d+$', unidas[-1]['w']))
                       or (re.match(r'^%[.,]?$', p['w']) and re.match(r'^\d+([.,]\d+)?$', unidas[-1]['w']))):
            unidas[-1] = {'w': unidas[-1]['w'] + p['w'], 'ini': unidas[-1]['ini'], 'fin': p['fin']}
        else:
            unidas.append(dict(p))
    ps = unidas
    out, i = [], 0
    while i < len(ps):
        for mal, bien in CORRECCIONES:
            n = len(mal)
            if [norm(p['w']) for p in ps[i:i + n]] == mal:
                fin_punt = re.sub(r'^[\w%.,]*?([.,:;?!]*)$', r'\1', ps[i + n - 1]['w'])
                a, b = ps[i]['ini'], ps[i + n - 1]['fin']
                for k, w in enumerate(bien):
                    out.append({'w': w + (fin_punt if k == len(bien) - 1 else ''),
                                'ini': round(a + (b - a) * k / len(bien), 3), 'fin': round(a + (b - a) * (k + 1) / len(bien), 3)})
                i += n
                break
        else:
            out.append(dict(ps[i])); i += 1
    for p in out:
        p['w'] = re.sub(r'^(\d+(?:[.,]\d+)?)%', lambda m: m.group(1).replace('.', ',') + ' %', p['w'])
    if out:
        out[0]['w'] = '¿' + out[0]['w'][:1].upper() + out[0]['w'][1:]
        for k, p in enumerate(out[:12]):
            if p['w'][-1:] in '.,' and '2027' in p['w']:
                p['w'] = p['w'][:-1] + '?'
                if k + 1 < len(out):
                    out[k + 1]['w'] = out[k + 1]['w'][:1].upper() + out[k + 1]['w'][1:]
                break
    return out

palabras = corregir(palabras)
(salida / 'transcripcion.txt').write_text(' '.join(p['w'] for p in palabras), encoding='utf-8')

x = cargar(voz, 48000)
duracion = len(x) / 48000
escenas = json.loads((AQUI / 'escenas.json').read_text(encoding='utf-8'))['escenas']
lista = [norm(p['w']) for p in palabras]
inicios, desde = [], 0
for e in escenas:
    objetivo = [norm(t) for t in e['inicio_texto'].split()]
    hallado = next((k for k in range(desde, len(lista) - len(objetivo) + 1) if lista[k:k + len(objetivo)] == objetivo), None)
    if hallado is None:
        print('No encontré el inicio de la escena', e['id'], '->', e['inicio_texto'])
        hallado = desde
    inicios.append(palabras[hallado]['ini'] if palabras else 0.0)
    desde = hallado + 1
inicios[0] = 0.0
tiempos_escenas = [{'inicio': round(a, 3), 'fin': round(b, 3)} for a, b in zip(inicios, inicios[1:] + [duracion])]

paso = 48000 // FPS
n = int(duracion * FPS)
rms = np.array([np.sqrt(np.mean(x[i * paso:(i + 1) * paso] ** 2) + 1e-9) for i in range(n)])
ref = np.percentile(rms[rms > np.percentile(rms, 30)], 90) if n else 1
boca = np.convolve(np.clip(rms / ref, 0, 1), [0.25, 0.5, 0.25], mode='same')

json.dump({'duracion': round(duracion + 1.0, 3), 'escenas': tiempos_escenas, 'palabras': palabras,
           'boca': [round(float(v), 3) for v in boca]}, open(salida / 'tiempos.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'duración {duracion:.1f} s · {len(palabras)} palabras · escenas en', [e['inicio'] for e in tiempos_escenas])
