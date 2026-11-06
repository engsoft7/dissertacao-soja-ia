#!/usr/bin/env bash
# Roda dentro do emulador do teste-premium.yml (android-emulator-runner).
#
#   teste_premium_emulador.sh <pasta de saída> <apk de release> <percurso: 1|0>
#
# 1. Com percurso=1: instala o build de depuração e o PercursoNoAparelhoTest e
#    roda o teste com am instrument, para o app continuar instalado e as
#    capturas e achados de acessibilidade poderem ser copiados com run-as (o
#    connectedAndroidTest do Gradle desinstala tudo no fim).
# 2. teste_aparelho.py com o APK de release.
set -u
SAIDA="$1"; APK="$2"; PERCURSO="${3:-1}"
PKG=com.agrointeligencia.app
APP=software/aplicativo_mobile/app/build/outputs/apk
mkdir -p "$SAIDA"
adb wait-for-device
adb shell getprop ro.build.version.sdk

if [ "$PERCURSO" = "1" ]; then
  P="$SAIDA/percurso"; mkdir -p "$P"
  adb uninstall "$PKG.test" >/dev/null 2>&1
  adb uninstall "$PKG" >/dev/null 2>&1
  adb install -r -t "$APP/debug/app-debug.apk"
  adb install -r -t "$APP/androidTest/debug/app-debug-androidTest.apk"
  adb logcat -c
  timeout 1800 adb shell am instrument -w -e class "$PKG.PercursoNoAparelhoTest" \
    "$PKG.test/androidx.test.runner.AndroidJUnitRunner" > "$P/instrument.txt" 2>&1
  echo "am instrument terminou com $?"
  tail -20 "$P/instrument.txt"
  adb logcat -d -s PERCURSO:I > "$P/logcat.txt"
  for f in $(adb shell run-as "$PKG" ls files/percurso 2>/dev/null | tr -d '\r'); do
    adb exec-out run-as "$PKG" cat "files/percurso/$f" > "$P/$f"
  done
  ls -la "$P"
  adb uninstall "$PKG.test" >/dev/null 2>&1
  adb uninstall "$PKG" >/dev/null 2>&1
fi

python3 software/automacao_github/teste_aparelho.py "$APK" "$SAIDA/release"
echo "teste_aparelho.py terminou com $?"
exit 0
