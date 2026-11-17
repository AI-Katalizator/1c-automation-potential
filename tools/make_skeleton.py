#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Готовит «скелет» исходников v8unpack для обработки из публичного образца.

Образец: tests/ExternalDataProcessor803/ВнешняяОбработка803.epf из репозитория
https://github.com/saby-integration/v8unpack (реальный файл, сохранённый платформой 8.3.15,
формат version 216 / 80315). Берём из него:
  * ExternalDataProcessor.json — убираем табличную часть, реквизит, макет и лишние формы,
    оставляем одну форму (структура классов как в реальном EPF с одной формой);
  * управляемую форму «ПустаяФорма» — только реквизит «Объект», без элементов;
    добавляем привязку события ПриСозданииНаСервере в том же виде, в каком она лежит
    в реальной общей форме ФормаПоиска из tests/Configuration803/1Cv8.cf того же репозитория.
Результат кладётся в src/skeleton/ с плейсхолдерами @@...@@; build.py подставляет имена и UUID.

Запуск: python3 tools/make_skeleton.py <путь к распакованному образцу (v8unpack -E)> src/skeleton
"""
import copy
import json
import os
import shutil
import sys

CLS_TABULAR = "2bcef0d1-0981-11d6-b9b8-0050bae0a95d"
CLS_TEMPLATES = "3daea016-69b7-4ed4-9453-127911372fe6"
CLS_FORMS = "d5b0e5ed-256d-401c-9c36-f630cafd8a62"
CLS_ATTRS = "ec6bb5e5-b7a8-4d75-bec9-658107a699cf"
CLS_ROOT = "c3831ec8-d8d5-4f93-8a22-f9bfae07327f"
EVENT_ON_CREATE_AT_SERVER = "9f2e5ddb-3492-4f5d-8f0d-416b8d1d5c5b"  # ПриСозданииНаСервере


def main(sample_dir, out_dir):
    d = json.load(open(os.path.join(sample_dir, "ExternalDataProcessor.json"), encoding="utf-8"))
    h = d["header"][0]
    h[1][0] = "@@FILE_UUID@@"
    body = h[3][1]
    obj = body[1]
    obj[1] = "@@TYPE_UUID_1@@"
    obj[2] = "@@TYPE_UUID_2@@"
    obj[3][1][1][2] = "@@PROC_UUID@@"
    obj[3][1][2] = '"@@NAME@@"'
    obj[3][1][3] = ["1", '"ru"', '"@@SYNONYM@@"']
    obj[4] = "@@FORM_UUID@@"  # основная форма
    body[2] = "4"
    del body[3:]
    body.extend([[CLS_TABULAR, "0"], [CLS_TEMPLATES, "0"], [CLS_FORMS, "1", "@@FORM_UUID@@"], [CLS_ATTRS, "0"]])
    d.update({
        "file_uuid": "@@FILE_UUID@@", "uuid": "@@PROC_UUID@@", "name": "@@NAME@@",
        "name2": {"ru": "@@SYNONYM@@"}, "comment": "",
        "copyinfo": [["4",
                      ["2",
                       ["@@PROC_UUID@@", "@@PROC_UUID@@", "1", [CLS_ROOT, '"@@NAME@@"']],
                       ["@@FORM_UUID@@", "@@FORM_UUID@@", "1", [CLS_FORMS, '"@@FORM_NAME@@"']]],
                      ["1", ["@@TYPE_UUID_1@@", "@@PROC_UUID@@", "0"]],
                      ["0"], ["0", "0"], ["0"]]],
    })
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.join(out_dir, "Form", "@@FORM_NAME@@"))
    json.dump(d, open(os.path.join(out_dir, "ExternalDataProcessor.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    src_form = os.path.join(sample_dir, "Form", "ПустаяФорма")
    f = json.load(open(os.path.join(src_form, "Form.json"), encoding="utf-8"))
    f["name"] = "@@FORM_NAME@@"
    f["name2"] = {"ru": "@@FORM_NAME@@"}
    hdr = f["header"][0][1][1][1]
    assert hdr[1][1] == ["1", "0", "в отдельном файле"]
    hdr[1][2] = '"@@FORM_NAME@@"'
    hdr[1][3] = ["1", '"ru"', '"@@FORM_NAME@@"']
    blob = f["form"][0][0][1]
    assert blob[0] == "49" and blob[19] == ["0", "1", "0"], "неожиданная структура формы образца"
    blob[19] = ["1", EVENT_ON_CREATE_AT_SERVER, '"ПриСозданииНаСервере"', "1", "0", EVENT_ON_CREATE_AT_SERVER, "0", "1"]
    json.dump(f, open(os.path.join(out_dir, "Form", "@@FORM_NAME@@", "Form.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    shutil.copy(os.path.join(src_form, "Form.elem.json"), os.path.join(out_dir, "Form", "@@FORM_NAME@@", "Form.elem.json"))
    json.dump({"uuid": "@@FORM_UUID@@"}, open(os.path.join(out_dir, "Form", "@@FORM_NAME@@", "Form.id.json"), "w", encoding="utf-8"), indent=2)
    print("skeleton ->", out_dir)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
