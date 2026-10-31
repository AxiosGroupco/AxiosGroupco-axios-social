# Mascotas de Axios en Blender

Tres personajes en bloques detallados (uno por socio), renderizados con Cycles.
Todo el modelado está en `mascotas.py`, así que cada cambio (pelo, ropa, pose, expresión)
se hace en código y se vuelve a generar. `mascotas.blend` es la misma escena para abrirla
y ajustarla a mano en Blender 4.2 o posterior.

## Generar las imágenes

```bash
blender -b -P mascotas.py -- --salida ../../mascotas/equipo.png --muestras 48 --blend mascotas.blend
blender -b -P mascotas.py -- --salida ../../mascotas/retrato_socio1.png --retrato 0 --muestras 40
```

- `--retrato 0|1|2`: primer plano de un socio (1080x1080). Sin este parámetro: el grupo (1080x1350).
- `--muestras`: calidad del render. Con 24 sale una vista previa en ~1,5 min; con 128, la versión final.

## Qué se puede cambiar en `mascotas.py`

- `SOCIOS`: tono de piel, pelo, ojos, atuendo (`camisa_vestir`, `buso`, `blazer` con `saco` y `camisa` de color propio), pantalón (`chino`, `jean`, `gris`, `negro`, `caqui`, con `cargo`),
  zapatos (`cuero_cafe`, `tenis`, `cuero_negro`), peinado (`copete`, `rizado`, `texturizado`), barba, gafas y cadena.
- `pelo()`: pelo esculpido con el volumen de la imagen guía: copete en mechones gruesos barridos hacia arriba y a la derecha, rizos en bolitas sobre una cúpula y pelo texturizado con flequillo. La barba de candado es de bloques.
- `ropa()`: detalles de cada atuendo (bolsillo con símbolo AX y lapicero dorado; blazer abierto sin corbata con pin AX).
- `POSES`: brazos (hombro y codo), cabeza, cejas, `guino`, `pulgar_arriba`, `calculadora`.
- `ax-simbolo.png`: el símbolo AX recortado del logo, usado en el buso, el bolsillo y el pin.
- Luces, fondo (pared azul, piso oscuro y tarima con aro de luz, como la imagen guía) y cámara al final del archivo.

## Privacidad

Los rasgos se tomaron de fotos de los socios que **no** se guardan en este repositorio (es público).
