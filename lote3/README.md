# Lote 3: video sobre el proyecto de Ley de Rescate Económico

- `guion-ley-rescate.md`: guion por escenas, instrucciones para grabar y texto de la publicación.
- `sprites/`: la mascota del narrador (dos poses × boca cerrada, media y abierta, más parpadeo) y las de los otros socios, con fondo transparente, generadas con `lote2/fuente/blender/mascotas.py`.
- `fuente/escenas.json`: título, tarjeta, pose y reacción de cada escena; `inicio_texto` son las primeras palabras de cada escena en el audio.
- `fuente/video.html` + `fuente/render.js`: arman el video vertical (1080x1920, 30 fps) cuadro a cuadro y lo unen con el audio.
- `fuente/voz_locutor.sh`: convierte la grabación en voz de locutor: acorta pausas, quita ruido (RNNoise), baja el tono y cambia el timbre (Rubber Band), y aplica ecualización, de-esser, compresión y -14 LUFS. Por defecto deja la voz natural (sin cambio de tono), que es la elegida por los socios.
- `fuente/audio_a_tiempos.py`: transcribe la voz natural con Whisper, corrige los subtítulos y calcula los tiempos de escenas, subtítulos y boca.
- `ley-rescate.mp4`: video final (1080x1920, 2:36).

La grabación original se queda en `audio/` y no se sube al repositorio (es público).

## Con el audio grabado

```bash
fuente/voz_locutor.sh voz.m4a audio              # voz natural limpia (elegida); -2.5 = más grave; -4 = más profunda
/opt/venv-axios/bin/python fuente/audio_a_tiempos.py audio/voz_recortada.wav audio/voz_final.wav audio
node fuente/render.js audio/tiempos.json audio/voz_final.wav ley-rescate.mp4
```
