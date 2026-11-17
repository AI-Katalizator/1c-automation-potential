# -*- coding: utf-8 -*-
"""Зеркало расчёта и заполнения дашборда из модуля формы (src/bsl/ФормаМодуль.bsl).

Повторяет на Python ту же логику, что и функции РассчитатьПоказатели(),
ЗначенияДляДашборда() и форматтеры 1С (Формат с ЧДЦ, Окр по арифметическому
правилу). Используется в test_mirror.py и для предпросмотра HTML без 1С.
"""
from __future__ import annotations
import datetime as dt
import math
from decimal import Decimal, ROUND_HALF_UP

NBSP = "\u00a0"


def okr(x: float, n: int = 0) -> float:
    """Окр(x, n) в 1С: арифметическое округление (Окр15как20)."""
    q = Decimal(1).scaleb(-n)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def _group(int_part: str) -> str:
    neg = int_part.startswith("-")
    s = int_part.lstrip("-")
    out = ""
    while len(s) > 3:
        out = NBSP + s[-3:] + out
        s = s[:-3]
    return ("-" if neg else "") + s + out


def fmt(x: float, dec: int | None = None, group: bool = True, point: str = ",") -> str:
    """Аналог Формат(): dec=None — без ЧДЦ (показать значащие знаки), иначе ЧДЦ=dec."""
    if dec is None:
        d = Decimal(repr(x)).normalize()
        s = format(d, "f")
    else:
        s = format(Decimal(repr(okr(x, dec))), f".{dec}f")
    if "." in s:
        i, f = s.split(".")
    else:
        i, f = s, ""
    if dec is None and f.strip("0") == "":
        f = ""
    i = _group(i) if group else i
    return i + (point + f if f else "")


def f_int(x):  # int(), rub() без знака ₽
    return fmt(okr(x, 0), 0)


def f_mins(x):  # mins(): до 2 знаков без хвостовых нулей
    return fmt(okr(x, 2))


def f_one(x):
    return fmt(okr(x, 1), 1)


def f_two(x):
    return fmt(okr(x, 2), 2)


def f_css(x):
    return fmt(okr(x, 2), None, group=False, point=".")


def plural(n, f1, f2, f5):
    n = abs(int(n)) % 100
    if 11 <= n <= 19:
        return f5
    n %= 10
    if n == 1:
        return f1
    if 2 <= n <= 4:
        return f2
    return f5


def gen_postavshik(n):  # «от N поставщика/поставщиков»
    n2 = abs(int(n)) % 100
    return "поставщика" if (n2 % 10 == 1 and n2 != 11) else "поставщиков"


def months_in_period(d1: dt.date, d2: dt.date) -> int:
    return max(1, (d2.year - d1.year) * 12 + d2.month - d1.month + 1)


def full_months(d1: dt.date, d2: dt.date) -> int:
    cnt = 0
    y, m = d1.year, d1.month
    while (y, m) <= (d2.year, d2.month):
        first = dt.date(y, m, 1)
        nxt = dt.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
        last = nxt - dt.timedelta(days=1)
        if d1 <= first and d2 >= last:
            cnt += 1
        y, m = nxt.year, nxt.month
    return cnt


DEFAULTS = dict(N=3, mode_months=False, M=9, man=5.0, sc=0.5, ck=0.5,
                salary=100000.0, k=1.302, hours=164.3)


def calculate(suppliers, d1, d2, **params):
    """suppliers: список (наименование, документов, месяцев с документами)."""
    p = dict(DEFAULTS, **params)
    mp = months_in_period(d1, d2)
    fm = full_months(d1, d2)
    m_eff = min(p["M"], fm) if fm > 0 else p["M"]
    total = sum(s[1] for s in suppliers)
    sup = len(suppliers)
    cand = cand_sup = 0
    for _, docs, months in suppliers:
        ok = (months >= m_eff) if p["mode_months"] else (docs >= p["N"])
        if ok:
            cand += docs
            cand_sup += 1
    rest = total - cand
    rest_sup = sup - cand_sup
    share = okr(cand / total * 100) if total else 0
    before = total * p["man"]
    after = cand * (p["sc"] + p["ck"]) + rest * p["man"]
    saved = before - after
    hours = saved / 60
    rate = p["salary"] * p["k"] / p["hours"] if p["hours"] else 0
    money = hours * rate
    return dict(total=total, suppliers=sup, cand=cand, cand_sup=cand_sup, rest=rest,
                rest_sup=rest_sup, share=share, before=before, after=after, saved=saved,
                hours=hours, rate=rate, money=money, months=mp, full_months=fm, m_eff=m_eff,
                money_month=money / mp, hours_month=hours / mp,
                pct_time=okr(saved / before * 100) if before else 0, params=p)


def is_full_year(d1, d2):
    return d1 == dt.date(d1.year, 1, 1) and d2 == dt.date(d1.year, 12, 31)


def period_texts(d1, d2):
    if is_full_year(d1, d2):
        title = f"за {d1.year} год"
    else:
        title = f"за {d1:%d.%m.%Y} – {d2:%d.%m.%Y}"
    short = (f"{d1:%d.%m} – {d2:%d.%m.%Y}" if d1.year == d2.year
             else f"{d1:%d.%m.%Y} – {d2:%d.%m.%Y}")
    return title, short


def org_text(org, anonymize):
    """Организация в шапке: пусто — все; при обезличивании название скрыто."""
    if not org:
        return "Все организации"
    if anonymize:
        return "Организация скрыта"
    return "Организация: " + org


def dashboard_values(r, d1, d2, mixed=None, sf=None, anonymize=False, org=""):
    p = r["params"]
    title, short = period_texts(d1, d2)
    unit = "в год" if r["months"] == 12 else "за период"
    if mixed is None or sf is None:
        excl = "Не включены: смешанные поступления «товары, услуги, комиссия» и полученные счета-фактуры."
    else:
        excl = ("Не включены: " + f"{mixed} " + plural(mixed, "смешанное поступление", "смешанных поступления", "смешанных поступлений")
                + " «товары, услуги, комиссия» и " + f"{sf} "
                + plural(sf, "полученный счёт-фактура", "полученных счёта-фактуры", "полученных счетов-фактур") + ".")
    tip_total = "Документы «Поступление (акт, накладная, УПД)» с видом операции «Услуги» за период. " + excl
    akta = lambda n: "акта" if plural(n, "1", "2", "5") in ("1", "2") else "актов"
    if p["mode_months"]:
        crit_tip = f"у каждого акты были не меньше чем в {r['m_eff']} месяцах из {r['full_months']}"
        crit = f"у поставщика акты или УПД были не меньше чем в {r['m_eff']} месяцах из {r['full_months']} полных месяцев периода."
        rest_tail = "с более редкими актами"
    else:
        n = int(p["N"])
        crit_tip = f"от каждого пришло {n} и более {akta(n)} за период"
        crit = f"от поставщика пришло {n} и более {akta(n)} или УПД за период."
        rest_tail = (f"с 1–{n - 1} актами" if n - 1 >= 2 else "с 1 актом")
    if r["rest"] > 0:
        rest_txt = (f" Остальные {r['rest']} " + plural(r["rest"], "акт", "акта", "актов") + " — от "
                    + f"{r['rest_sup']} {gen_postavshik(r['rest_sup'])} {rest_tail}, они остаются за бухгалтером.")
    else:
        rest_txt = " Остальных документов нет."
    tip_cand = f"Повторяющиеся операции: акты от {r['cand_sup']} {gen_postavshik(r['cand_sup'])}, {crit_tip}." + rest_txt
    tip_share = f"{r['cand']} повторяющихся из {r['total']} документов поступления услуг."
    tip_period = "Журнал операций базы " + title + ("; база обезличена." if anonymize else ".")
    c = 2 * math.pi * 24
    ln = r["cand"] / r["total"] * c if r["total"] else 0
    auto = p["sc"] + p["ck"]
    scale = 100 / max(p["man"], auto, 0.0001)
    part_sc = p["sc"] / auto * 100 if auto else 50
    return {
        "ЗАГОЛОВОК_ПЕРИОДА": title,
        "ОРГАНИЗАЦИЯ_ТЕКСТ": org_text(org, anonymize),
        "ПОДСКАЗКА_ВСЕГО": tip_total,
        "ВСЕГО": f_int(r["total"]),
        "ПОСТАВЩИКОВ_ТЕКСТ": f"{f_int(r['suppliers'])} {gen_postavshik(r['suppliers'])}",
        "ПОДСКАЗКА_КАНДИДАТЫ": tip_cand,
        "КАНДИДАТЫ": f_int(r["cand"]),
        "ПОСТАВЩИКОВ_КАНДИДАТОВ_ТЕКСТ": f"{f_int(r['cand_sup'])} {gen_postavshik(r['cand_sup'])}",
        "КОЛЬЦО_ДЛИНА": f_css(ln),
        "КОЛЬЦО_ОСТАТОК": f_css(c - ln),
        "ДОЛЯ": f_int(r["share"]),
        "ПОДСКАЗКА_ДОЛЯ": tip_share,
        "ПОДСКАЗКА_ПЕРИОД": tip_period,
        "ПЕРИОД_КОРОТКО": short,
        "МЕСЯЦЕВ_ТЕКСТ": f"{r['months']} " + plural(r["months"], "месяц", "месяца", "месяцев"),
        "ЕД_ПЕРИОДА": unit,
        "ЧАСОВ": f_one(r["hours"]),
        "ЧАСОВ_В_МЕСЯЦ": f_one(r["hours_month"]),
        "ПРОЦЕНТ_ВРЕМЕНИ": f_int(r["pct_time"]),
        "РУБЛЕЙ": f_int(r["money"]),
        "РУБЛЕЙ_В_МЕСЯЦ": f_int(r["money_month"]),
        "ОКЛАД_ВВОД": fmt(p["salary"], None, group=False),
        "МВР": f_mins(p["man"]),
        "МСЦ": f_mins(p["sc"]),
        "МПР": f_mins(p["ck"]),
        "МИН_ВРУЧНУЮ": f_int(r["before"]),
        "ОСТАЛЬНЫЕ": f_int(r["rest"]),
        "МИН_С_АВТО": f_mins(r["after"]),
        "МИН_ЭКОНОМИЯ": f_mins(r["saved"]),
        "ОКЛАД": f_int(p["salary"]),
        "КОЭФ_ВЗНОСОВ": fmt(p["k"]),
        "ЧАСОВ_В_МЕСЯЦЕ_НОРМА": fmt(p["hours"]),
        "СТАВКА": f_int(r["rate"]),
        "ЧАСОВ_2": f_two(r["hours"]),
        "СТАВКА_2": f_two(r["rate"]),
        "КРИТЕРИЙ": crit,
        "ШИРИНА_АВТО": f_css(auto * scale * 0.82),
        "ШИРИНА_ВРУЧНУЮ": f_css(p["man"] * scale * 0.82),
        "ДОЛЯ_СЦЕНАРИЙ": f_css(part_sc),
        "ДОЛЯ_ПРОВЕРКА": f_css(100 - part_sc),
        "МИН_АВТО_НА_ДОК": f_mins(auto),
    }


def escape_html(t: str) -> str:  # ЭкранироватьHTML()
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fill(template: str, values: dict) -> str:  # ЗаполнитьШаблон()
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", escape_html(v))
    return out
