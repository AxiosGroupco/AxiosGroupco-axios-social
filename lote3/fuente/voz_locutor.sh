#!/usr/bin/env bash
# Voz de locutor a partir de la grabación, en dos pasos:
#   1) recorte: solo acorta pausas largas (la voz sigue natural, para transcribir los subtítulos)
#   2) locutor: quita ruido (RNNoise), cambia tono y timbre (Rubber Band) y aplica cadena de radio
#      (EQ, de-esser, compresión, -14 LUFS) SIN mover los tiempos del paso 1.
# Uso: voz_locutor.sh entrada carpeta_salida [SEMITONOS]   (0 por defecto = su voz natural limpia; -2.5 = más grave)
# Escribe carpeta/voz_recortada.wav y carpeta/voz_final.wav
set -euo pipefail
ENT="$1"; DIR="$2"; ST="${3:-0}"
mkdir -p "$DIR"
MODELO="$(cd "$(dirname "$0")" && pwd)/modelos/sh.rnnn"
# Modelo RNNoise de voz (repositorio GregorR/rnnoise-models); se descarga, no se versiona
[ -f "$MODELO" ] || curl -sSL --create-dirs -o "$MODELO" https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn
RATIO=$(python3 -c "print(round(2 ** (${ST} / 12), 4))")
ffmpeg -y -loglevel error -i "$ENT" -af "highpass=f=75,\
silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.2:stop_periods=-1:stop_duration=0.6:stop_threshold=-38dB:stop_silence=0.45" \
  -ar 48000 -ac 1 "$DIR/voz_recortada.wav"
ffmpeg -y -loglevel error -i "$DIR/voz_recortada.wav" -af "arnndn=m=${MODELO}:mix=0.95,afftdn=nr=10:nf=-40:tn=1,\
agate=threshold=0.012:ratio=4:attack=8:release=250:range=0.08,\
rubberband=pitch=${RATIO}:formant=shifted:pitchq=quality:window=standard,\
equalizer=f=110:t=q:w=0.9:g=3,equalizer=f=380:t=q:w=1.2:g=-2.5,equalizer=f=3300:t=q:w=1.3:g=2.5,highshelf=f=9000:g=-1.5,\
deesser=i=0.35,acompressor=threshold=-22dB:ratio=3.5:attack=6:release=140:makeup=2,\
loudnorm=I=-14:TP=-1.5:LRA=7,alimiter=limit=0.89" -ar 48000 -ac 1 "$DIR/voz_final.wav"
