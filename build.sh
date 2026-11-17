#!/usr/bin/env bash
# Воспроизводимая сборка внешней обработки PotencialAvtomatizaciiUslug_v002.epf.
# Платформа 1С не нужна: файл собирается v8unpack из исходников src/.
#
#   ./build.sh            тест-зеркало расчёта + сборка + проверки
#   ./build.sh --bsl      дополнительно статический анализ BSL Language Server
#                         (нужны переменные JAVA=<java 21+> и BSL_LS_JAR=<bsl-language-server-exec.jar>)
#   ./build.sh --skeleton перегенерировать каркас src/skeleton из образца:
#                         SAMPLE_DIR=<образец ВнешняяОбработка803.epf из тестов v8unpack, распакованный v8unpack -E>
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
V8UNPACK_VERSION=1.2.15

if ! "$PY" -c "import v8unpack" 2>/dev/null; then
  echo "== устанавливаю v8unpack==$V8UNPACK_VERSION"
  "$PY" -m pip install --quiet "v8unpack==$V8UNPACK_VERSION"
fi
got=$("$PY" -m pip show v8unpack 2>/dev/null | awk '/^Version:/{print $2}')
if [ "$got" != "$V8UNPACK_VERSION" ]; then
  echo "!! установлен v8unpack $got, сборка проверялась на $V8UNPACK_VERSION" >&2
fi

for arg in "$@"; do
  if [ "$arg" = "--skeleton" ]; then
    echo "== перегенерация каркаса из образца"
    "$PY" tools/make_skeleton.py "${SAMPLE_DIR:?укажите SAMPLE_DIR=распакованный образец}" src/skeleton
  fi
done

echo "== тест-зеркало расчёта (контрольный пример)"
"$PY" tests/test_mirror.py

echo "== сборка и проверки контейнера"
"$PY" tools/build.py

for arg in "$@"; do
  if [ "$arg" = "--bsl" ]; then
    : "${JAVA:?укажите JAVA=путь к java 21+}"
    : "${BSL_LS_JAR:?укажите BSL_LS_JAR=путь к bsl-language-server-exec.jar}"
    echo "== статический анализ BSL Language Server"
    rm -rf build/bslcheck && mkdir -p build/bslcheck/src build/bslcheck/out
    cp build/Form.obj.generated.bsl build/bslcheck/src/Form.bsl
    cp src/bsl/МодульОбъекта.bsl build/bslcheck/src/Object.bsl
    "$JAVA" -jar "$BSL_LS_JAR" analyze -s build/bslcheck/src -w build/bslcheck -o build/bslcheck/out -r json -q >/dev/null 2>&1 || true
    "$PY" - <<'PYEOF'
import json, collections, sys
d = json.load(open("build/bslcheck/out/bsl-json.json", encoding="utf-8"))
parse = 0
for f in d["fileinfos"]:
    c = collections.Counter(x["code"] for x in f["diagnostics"])
    parse += c.get("ParseError", 0)
    print(f["path"].split("/")[-1], dict(sorted(c.items())))
print("Ошибок разбора (ParseError):", parse)
sys.exit(1 if parse else 0)
PYEOF
  fi
done

echo
echo "Готово: dist/PotencialAvtomatizaciiUslug_v002.epf (протокол: build/BUILD_REPORT.md)"
