#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка PotencialAvtomatizaciiUslug_vNNN.epf без платформы 1С.

Шаги:
 1. Скелет src/skeleton (см. make_skeleton.py) -> build/src с подставленными именами и UUID.
 2. Модуль формы: src/bsl/ФормаМодуль.bsl + функция ШаблонДашборда(), сгенерированная
    из src/html/dashboard_v10.html. Модуль объекта: src/bsl/МодульОбъекта.bsl.
 3. v8unpack -B  -> .epf.
 4. Исправление размера TOC-блока (0x200, как пишет платформа) — tools/patch_toc.py.
 5. Проверки: структура контейнера, round-trip (v8unpack -E и сравнение), модуль внутри файла
    совпадает с исходником, нет запрещённых слов.
"""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import patch_toc  # noqa: E402
import v8container  # noqa: E402

VERSION = "002"
CFG = {
    "NAME": "ПотенциалАвтоматизацииУслуг",
    "SYNONYM": "Потенциал автоматизации учёта поступления услуг",
    "FORM_NAME": "Форма",
    # Фиксированные UUID: повторная сборка даёт тот же объект (1С узнаёт обработку как ту же самую).
    "FILE_UUID": "6b0f8a52-3c1e-4c55-9f0e-2a7d1b9c4e01",
    "PROC_UUID": "b3a1c6d0-5e2f-4a8b-9c3d-7e4f5a6b8c02",
    "TYPE_UUID_1": "c4d2e7f1-6a3b-4c9d-8e1f-0a2b3c4d5e03",
    "TYPE_UUID_2": "d5e3f8a2-7b4c-4dae-9f20-1b3c4d5e6f04",
    "FORM_UUID": "e6f4a9b3-8c5d-4ebf-a031-2c4d5e6f7a05",
}
# Слова собираются из частей, чтобы их не было даже в исходниках сборки.
_A, _B, _C, _D = "лид", "магнит", "lead", "magnet"
FORBIDDEN = [_A + "-" + _B, _A + _B, _A + " " + _B, _C + " " + _D, _C + "-" + _D, _C + _D]
OUT_NAME = f"PotencialAvtomatizaciiUslug_v{VERSION}.epf"


def subst(obj):
    if isinstance(obj, str):
        for k, v in CFG.items():
            obj = obj.replace("@@" + k + "@@", v)
        return obj
    if isinstance(obj, list):
        return [subst(x) for x in obj]
    if isinstance(obj, dict):
        return {subst(k): subst(v) for k, v in obj.items()}
    return obj


def bsl_string(line):
    return '"' + line.replace('"', '""') + '"'


def template_function(html_path):
    lines = open(html_path, encoding="utf-8").read().rstrip("\n").split("\n")
    out = ["&НаСервереБезКонтекста", "Функция ШаблонДашборда()", "", "\tСтроки = Новый Массив;"]
    for ln in lines:
        out.append("\tСтроки.Добавить(" + bsl_string(ln) + ");")
    out += ["\tВозврат СтрСоединить(Строки, Символы.ПС);", "", "КонецФункции"]
    return "\n".join(out)


def form_module():
    src = open(os.path.join(ROOT, "src", "bsl", "ФормаМодуль.bsl"), encoding="utf-8").read()
    marker = "// @@ШАБЛОН_ДАШБОРДА@@"
    assert src.count(marker) == 1
    return src.replace(marker, template_function(os.path.join(ROOT, "src", "html", "dashboard_v10.html")))


def main():
    build = os.path.join(ROOT, "build")
    src_dir = os.path.join(build, "src")
    dist = os.path.join(ROOT, "dist")
    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    os.makedirs(dist, exist_ok=True)

    skel = os.path.join(ROOT, "src", "skeleton")
    for dirpath, _, files in os.walk(skel):
        rel = subst(os.path.relpath(dirpath, skel))
        os.makedirs(os.path.join(src_dir, rel), exist_ok=True)
        for fn in files:
            data = json.load(open(os.path.join(dirpath, fn), encoding="utf-8"))
            json.dump(subst(data), open(os.path.join(src_dir, rel, fn), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    module = form_module()
    form_dir = os.path.join(src_dir, "Form", CFG["FORM_NAME"])
    with open(os.path.join(form_dir, "Form.obj.bsl"), "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(module)
    shutil.copy(os.path.join(ROOT, "src", "bsl", "МодульОбъекта.bsl"), os.path.join(src_dir, "ExternalDataProcessor.obj.bsl"))
    open(os.path.join(build, "Form.obj.generated.bsl"), "w", encoding="utf-8").write(module)

    out = os.path.join(dist, OUT_NAME)
    if os.path.exists(out):
        os.remove(out)
    r = subprocess.run(["v8unpack", "-B", src_dir, out], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("v8unpack -B: ошибка сборки")
    info = patch_toc.patch(out)
    patch_toc.normalize_times(out)
    print("TOC:", info)

    # --- проверки ---
    report = []
    blob = open(out, "rb").read()
    files = v8container.read_files(blob)
    report.append(("сигнатура контейнера ff ff ff 7f", blob[:4] == b"\xff\xff\xff\x7f"))
    report.append(("TOC block_size = 0x200 (как у файлов платформы)", v8container.toc_header(blob)[1] == 0x200))
    names = sorted(files)
    # Как в реальном образце 8.3: <обработка>, <обработка>.0/{info,text} (модуль объекта),
    # <форма> (метаданные формы), <форма>.0 (описание формы + текст модуля формы), copyinfo, root, version, versions.
    expected = sorted([CFG["FILE_UUID"], CFG["PROC_UUID"] + ".0/info", CFG["PROC_UUID"] + ".0/text", CFG["FORM_UUID"],
                       CFG["FORM_UUID"] + ".0", "copyinfo", "root", "version", "versions"])
    report.append(("состав файлов контейнера " + ", ".join(names), names == expected))
    form_def = files.get(CFG["FORM_UUID"] + ".0", b"").decode("utf-8-sig", errors="replace")
    quoted = '"' + module.replace('"', '""') + '"'
    report.append(("модуль формы внутри описания формы == исходник (без учёта CR)",
                   quoted.replace("\r\n", "\n") in form_def.replace("\r\n", "\n")))
    obj_text = files.get(CFG["PROC_UUID"] + ".0/text", b"").decode("utf-8-sig")
    obj_src = open(os.path.join(ROOT, "src", "bsl", "МодульОбъекта.bsl"), encoding="utf-8").read()
    report.append(("модуль объекта в файле == исходник", obj_text.replace("\r\n", "\n").strip() == obj_src.strip()))
    report.append(("привязка ПриСозданииНаСервере в описании формы",
                   "9f2e5ddb-3492-4f5d-8f0d-416b8d1d5c5b" in form_def and '"ПриСозданииНаСервере"' in form_def))
    root = files["root"].decode("utf-8-sig")
    report.append(("root указывает на " + CFG["FILE_UUID"], CFG["FILE_UUID"] in root))
    meta = files[CFG["FILE_UUID"]].decode("utf-8-sig")
    report.append(("в метаданных имя и синоним обработки", CFG["NAME"] in meta and CFG["SYNONYM"] in meta))
    version = files["version"].decode("utf-8-sig")
    report.append(("version = 216 / 80315 (как у образца 8.3.15)", "216" in version and "80315" in version))
    alltext = (module + meta + form_def).lower()
    report.append(("нет запрещённых слов", not any(w in alltext for w in FORBIDDEN)))

    rt = os.path.join(build, "roundtrip")
    if os.path.exists(rt):
        shutil.rmtree(rt)
    r = subprocess.run(["v8unpack", "-E", out, rt], capture_output=True, text=True)
    rt_bsl = open(os.path.join(rt, "Form", CFG["FORM_NAME"], "Form.obj.bsl"), encoding="utf-8-sig").read()
    report.append(("round-trip: v8unpack -E читает файл, модуль формы совпадает", r.returncode == 0 and rt_bsl == module))
    same_json = True
    for rel in ["ExternalDataProcessor.json", f"Form/{CFG['FORM_NAME']}/Form.json", f"Form/{CFG['FORM_NAME']}/Form.elem.json"]:
        a = json.load(open(os.path.join(src_dir, rel), encoding="utf-8"))
        b = json.load(open(os.path.join(rt, rel), encoding="utf-8"))
        for k in ("v8unpack",):
            a.pop(k, None); b.pop(k, None)
        if a != b:
            same_json = False
            print("  расхождение round-trip:", rel)
    report.append(("round-trip: метаданные и форма совпадают с исходниками", same_json))

    # повторная сборка из распакованного даёт тот же модуль и состав
    rb = os.path.join(build, "rebuilt.epf")
    subprocess.run(["v8unpack", "-B", rt, rb], capture_output=True, text=True)
    patch_toc.patch(rb)
    patch_toc.normalize_times(rb)
    f2 = v8container.read_files(open(rb, "rb").read())
    report.append(("пересборка из round-trip: те же файлы и содержимое",
                   sorted(f2) == names and all(f2[k] == files[k] for k in names if k != "versions")))

    ok = all(x[1] for x in report)
    lines = [f"# Протокол сборки {OUT_NAME}", "", f"Размер: {len(blob)} байт", ""]
    lines += [f"- [{'x' if v else ' '}] {k}" for k, v in report]
    lines += ["", "Итог: " + ("все автоматические проверки пройдены" if ok else "ЕСТЬ ОШИБКИ")]
    open(os.path.join(build, "BUILD_REPORT.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
