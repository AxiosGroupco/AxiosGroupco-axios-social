#!/usr/bin/env bash
# Compila MarcadorSonido.apk sin Gradle, con las herramientas del SDK de Android.
# Uso: ANDROID_HOME=... ./compilar.sh <número de versión>
set -euo pipefail
cd "$(dirname "$0")"
VERSION="${1:-1}"
BT="$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"
JAR="$(ls -d "$ANDROID_HOME"/platforms/android-* | sort -V | tail -1)/android.jar"
echo "build-tools: $BT"; echo "plataforma: $JAR"

rm -rf build && mkdir -p build/clases build/dex build/assets
cp ../recursos/musica/*.mp3 build/assets/

"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml -A build/assets \
    --min-sdk-version 26 --target-sdk-version 34 --version-code "$VERSION" --version-name "$VERSION" build/res.zip

javac -source 8 -target 8 -nowarn -Xlint:-options -classpath "$JAR" -d build/clases $(find src -name '*.java')
"$BT/d8" --lib "$JAR" --min-api 26 --output build/dex $(find build/clases -name '*.class')
(cd build/dex && zip -q ../base.apk classes.dex)

"$BT/zipalign" -f 4 build/base.apk build/alineado.apk
keytool -genkeypair -keystore build/llave.jks -storepass marcador -keypass marcador -alias marcador \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Marcador Axios" >/dev/null 2>&1
"$BT/apksigner" sign --ks build/llave.jks --ks-pass pass:marcador --key-pass pass:marcador \
    --out build/MarcadorSonido.apk build/alineado.apk
"$BT/apksigner" verify build/MarcadorSonido.apk
"$BT/aapt2" dump badging build/MarcadorSonido.apk | head -4
ls -la build/MarcadorSonido.apk
