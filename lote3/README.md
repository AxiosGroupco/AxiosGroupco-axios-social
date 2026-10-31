# Lote 3: video sobre el proyecto de Ley de Rescate Económico

- `guion-ley-rescate.md`: guion por escenas, instrucciones para grabar y texto de la publicación.
- `sprites/`: la mascota del narrador (dos poses × boca cerrada, media y abierta, más parpadeo) y las de los otros socios, con fondo transparente, generadas con `lote2/fuente/blender/mascotas.py`.
- `fuente/escenas.json`: título, tarjeta, pose y reacción de cada escena; `inicio_texto` son las primeras palabras de cada escena en el audio.
- `fuente/video.html` + `fuente/render.js`: arman el video vertical (1080x1920, 30 fps) cuadro a cuadro y lo unen con el audio.
- `fuente/audio_a_tiempos.py`: limpia la voz (ruido, compresión, -14 LUFS), la transcribe con Whisper y calcula los tiempos de escenas, subtítulos y boca.

## Con el audio grabado

```bash
/opt/venv-axios/bin/python fuente/audio_a_tiempos.py voz.m4a audio
node fuente/render.js audio/tiempos.json audio/voz_limpia.wav ley-rescate.mp4
```
