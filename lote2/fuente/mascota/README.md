# Mascota Axios: videos educativos con voz

Video vertical 1080x1920 con una mascota 3D en bloques que habla con voz sintética,
gesticula y muestra en el fondo el tema de cada frase. Todo es gratuito y de código abierto.

## Piezas

- `guion.json`: título y frases. Cada frase tiene `voz` (lo que se pronuncia), `sub` (el subtítulo),
  `gesto` (`point`, `skeptic`, `shock`, `shrug`, `list`, `thumbs`) y `panel` (lo que muestra la pantalla de fondo).
- `voz.py`: genera la voz con [Piper](https://github.com/rhasspy/piper) y la apertura de boca por cuadro.
- `mascota.html`: la escena (three.js 0.160.0 desde jsDelivr) y los paneles.
- `render.js`: dibuja cada cuadro con Playwright y lo une con la voz usando ffmpeg.

## Voces (uso comercial permitido)

- `es_MX-claude-high`: licencia Apache 2.0 (la usada en `mascota_renta_v1.mp4`).
- `es_MX-ald-medium`: dominio público (Unlicense); muestra en `muestra_voz_alternativa.m4a`.

Se descargan de `https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/...` (archivo `.onnx` y `.onnx.json`).

## Pasos

```bash
python3 -m venv venv && ./venv/bin/pip install piper-tts
./venv/bin/python voz.py guion.json es_MX-claude-high.onnx salida_voz
node render.js guion.json salida_voz ../../mascota_renta_v1.mp4
```

Para revisar cuadros sueltos antes del video completo: `node render.js guion.json salida_voz vista 1.5 8 14`.

## Antes de publicar

- Escuchar el audio completo: la voz sintética puede pronunciar mal siglas o cifras. Se corrige
  escribiendo en `voz` cómo se dice (por ejemplo "u ve te", "wasap").
- Marcar el contenido como hecho con IA en TikTok ("Contenido generado por IA") e Instagram, porque la voz es sintética.
