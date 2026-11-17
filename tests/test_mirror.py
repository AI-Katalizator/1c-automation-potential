# -*- coding: utf-8 -*-
"""Зеркальный тест формул на модельных данных (НЕ на базе 1С).

Модельный журнал собран так, чтобы совпасть с контрольным примером за 2025 год:
127 документов «Услуги» от 35 поставщиков; 11 поставщиков с ≥3 актами дают 97 документов;
6 из них присылают акты не реже 9 месяцев из 12 (73 документа).
Плюс «шум», который отбор должен отбросить: 3 смешанных поступления, 89 счетов-фактур,
непроведённые и помеченные на удаление документы, документы вне периода.
Запуск: python3 tests/test_mirror.py
"""
import datetime as dt
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import mirror as m  # noqa: E402

D1, D2 = dt.date(2025, 1, 1), dt.date(2025, 12, 31)


ORG_A = 'ООО "Альфа & Партнёры"'
ORG_A_HTML = "ООО &quot;Альфа &amp; Партнёры&quot;"
ORG_B = "АО Бета"


def make_journal():
    docs = []  # (вид документа, вид операции, проведён, пометка, дата, поставщик, организация)
    add = lambda sup, d, op="Услуги", kind="ПоступлениеТоваровУслуг", posted=True, deleted=False, org=ORG_A: docs.append((kind, op, posted, deleted, d, sup, org))
    # 6 «ежемесячных» поставщиков: 12 месяцев, у последнего 13 документов
    for i in range(6):
        for mth in range(1, 13):
            add(f"Ежемесячный {i+1}", dt.date(2025, mth, 10))
    add("Ежемесячный 6", dt.date(2025, 6, 25))
    # 5 повторяющихся, но не ежемесячных: 5,5,5,5,4 документа в разных месяцах
    for i, n in enumerate([5, 5, 5, 5, 4]):
        for k in range(n):
            add(f"Регулярный {i+1}", dt.date(2025, 1 + k * 2, 5))
    # 24 разовых: 6 по 2 документа, 18 по 1
    for i in range(6):
        add(f"Разовый2 {i+1}", dt.date(2025, 3, 3)); add(f"Разовый2 {i+1}", dt.date(2025, 9, 3))
    for i in range(18):
        add(f"Разовый1 {i+1}", dt.date(2025, 1 + i % 12, 15))
    # шум, который отбор обязан исключить
    for i in range(3):
        add("Ежемесячный 1", dt.date(2025, 4, 1), op="ПокупкаКомиссия")
    for i in range(89):
        add("Ежемесячный 2", dt.date(2025, 1 + i % 12, 2), op=None, kind="СчетФактураПолученный")
    add("Разовый1 1", dt.date(2025, 5, 5), posted=False)
    add("Разовый1 2", dt.date(2025, 5, 5), deleted=True, posted=False)
    add("Ежемесячный 3", dt.date(2024, 12, 31))
    add("Ежемесячный 3", dt.date(2026, 1, 1))
    add("Новый", dt.date(2025, 7, 7), op="Товары")
    # вторая организация: 4 акта одного поставщика, 1 смешанное, 2 счёта-фактуры
    for mth in (2, 4, 6, 8):
        add("Бета-поставщик", dt.date(2025, mth, 12), org=ORG_B)
    add("Бета-поставщик", dt.date(2025, 3, 1), op="ПокупкаКомиссия", org=ORG_B)
    for mth in (2, 4):
        add("Бета-поставщик", dt.date(2025, mth, 12), op=None, kind="СчетФактураПолученный", org=ORG_B)
    return docs


def query_mirror(docs, d1, d2, org=None):
    """Зеркало пакета запросов: отбор + СГРУППИРОВАТЬ ПО Контрагент, НАЧАЛОПЕРИОДА(Дата, МЕСЯЦ)."""
    by = defaultdict(int)
    mixed = sf = 0
    for kind, op, posted, deleted, d, sup, doc_org in docs:
        if not (posted and not deleted and d1 <= d <= d2):
            continue
        if org and doc_org != org:  # пусто — все организации
            continue
        if kind == "ПоступлениеТоваровУслуг" and op == "Услуги":
            by[(sup, (d.year, d.month))] += 1
        elif kind == "ПоступлениеТоваровУслуг" and op == "ПокупкаКомиссия":
            mixed += 1
        elif kind == "СчетФактураПолученный":
            sf += 1
    agg = defaultdict(lambda: [0, 0])
    for (sup, _), n in by.items():
        agg[sup][0] += n
        agg[sup][1] += 1  # месяцев с документами
    sup = sorted(((k, v[0], v[1]) for k, v in agg.items()), key=lambda x: (-x[1], x[0]))
    return sup, mixed, sf


def check(name, got, exp):
    status = "OK " if got == exp else "FAIL"
    print(f"[{status}] {name}: {got!r} (ожидалось {exp!r})")
    return got == exp


def main():
    journal = make_journal()
    sup, mixed, sf = query_mirror(journal, D1, D2, org=ORG_A)
    r = m.calculate(sup, D1, D2)
    v = m.dashboard_values(r, D1, D2, mixed, sf, org=ORG_A)
    ok = True
    ok &= check("всего документов", r["total"], 127)
    ok &= check("поставщиков", r["suppliers"], 35)
    ok &= check("кандидатов (N=3)", r["cand"], 97)
    ok &= check("поставщиков-кандидатов", r["cand_sup"], 11)
    ok &= check("доля, %", v["ДОЛЯ"], "76")
    ok &= check("вручную, мин", r["before"], 635)
    ok &= check("с автоматизацией, мин", r["after"], 247)
    ok &= check("экономия, ч (вывод)", v["ЧАСОВ"], "6,5")
    ok &= check("ставка, ₽/ч (вывод)", v["СТАВКА"], "792")
    ok &= check("экономия, ₽ в год", v["РУБЛЕЙ"], "5\u00a0125")
    ok &= check("экономия, ₽ в месяц", v["РУБЛЕЙ_В_МЕСЯЦ"], "427")
    ok &= check("смешанных исключено", mixed, 3)
    ok &= check("счетов-фактур исключено", sf, 89)
    ok &= check("рубли от точных часов, а не от 6,5 ч", round(6.5 * r["rate"]), 5151)
    r9 = m.calculate(sup, D1, D2, mode_months=True, M=9)
    v9 = m.dashboard_values(r9, D1, D2, mixed, sf, anonymize=True, org=ORG_A)
    ok &= check("кандидатов (9 мес из 12)", r9["cand"], 73)
    ok &= check("экономия, ₽ (9 мес из 12)", v9["РУБЛЕЙ"], "3\u00a0857")
    # обезличивание: стабильная нумерация по убыванию числа актов
    anon = [f"Поставщик {i+1}" for i in range(len(sup))]
    ok &= check("обезличенный №1 = больше всех актов", sup[0][0], "Ежемесячный 6")
    ok &= check("количество обезличенных имён", len(anon), 35)
    # отбор по организации: пусто — все организации, выбрана другая — только её документы
    sup_all, mixed_all, sf_all = query_mirror(journal, D1, D2)
    ok &= check("все организации: документов", sum(x[1] for x in sup_all), 131)
    ok &= check("все организации: поставщиков", len(sup_all), 36)
    ok &= check("все организации: смешанных / СФ", (mixed_all, sf_all), (4, 91))
    sup_b, mixed_b, sf_b = query_mirror(journal, D1, D2, org=ORG_B)
    ok &= check("вторая организация: документов / поставщиков", (sum(x[1] for x in sup_b), len(sup_b)), (4, 1))
    ok &= check("вторая организация: смешанных / СФ", (mixed_b, sf_b), (1, 2))
    # организация в шапке: название, «все», скрыта при обезличивании
    ok &= check("шапка: выбрана организация", v["ОРГАНИЗАЦИЯ_ТЕКСТ"], "Организация: " + ORG_A)
    ok &= check("шапка: обезличено", v9["ОРГАНИЗАЦИЯ_ТЕКСТ"], "Организация скрыта")
    v_all = m.dashboard_values(m.calculate(sup_all, D1, D2), D1, D2, mixed_all, sf_all)
    ok &= check("шапка: пусто", v_all["ОРГАНИЗАЦИЯ_ТЕКСТ"], "Все организации")
    # все плейсхолдеры шаблона заполнены
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "..", "src", "html", "dashboard_v10.html"), encoding="utf-8").read()
    html = m.fill(tpl, v)
    ok &= check("незаполненных плейсхолдеров", html.count("{{"), 0)
    ok &= check("название организации экранировано в HTML", ORG_A_HTML in html, True)
    html9 = m.fill(tpl, v9)
    ok &= check("при обезличивании названия организации нет в HTML", ("Альфа" in html9, "Организация скрыта" in html9), (False, True))
    for i, word in enumerate(("лид" + "-магнит", "лид" + "магнит", "lead" + " magnet", "Лид" + "-магнит"), 1):
        ok &= check(f"нет запрещённого слова №{i} в HTML", word.lower() in html.lower(), False)
    out = os.path.join(here, "..", "build", "preview")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "dashboard_test_2025.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(out, "dashboard_test_2025_m9.html"), "w", encoding="utf-8").write(m.fill(tpl, v9))
    print("ИТОГ:", "все проверки пройдены" if ok else "ЕСТЬ ОШИБКИ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
