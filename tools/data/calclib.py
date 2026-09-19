# -*- coding: utf-8 -*-
"""עזרים משותפים לבנקים של ניצן (מצגות 3–11). כל המספרים בשאלות מחושבים בקוד,
והמסיחים נגזרים מטעויות נפוצות (שכחת שורש, יחידות זמן, עיגול לא נכון וכד').

ייבוא מתוך קובץ נתונים:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from calclib import *
"""
import math

exp, ln, sqrt = math.exp, math.log, math.sqrt


def L(s):
    """ביטוי משמאל לימין בתוך טקסט עברי."""
    return "<bdi dir='ltr'>" + s + "</bdi>"


def num(v, dec=2):
    """מספר בפורמט קבוע: dec ספרות אחרי הנקודה, עם מפריד אלפים."""
    r = round(v, dec) + 0.0
    if r == 0:
        r = 0.0
    return "{:,.{d}f}".format(r, d=dec)


def opts(correct, cands, dec=2, unit="", pre=""):
    """מחזיר (נכונה, [3 מסיחים]) — כולם באותו פורמט, שונים זה מזה אחרי העיגול."""
    c = pre + num(correct, dec) + unit
    out = []
    for v in cands:
        s = pre + num(v, dec) + unit
        if s != c and s not in out:
            out.append(s)
        if len(out) == 3:
            break
    assert len(out) == 3, (correct, cands)
    return c, out


def stdev_s(xs):
    """סטיית תקן מדגמית (n−1) — כמו בשקפים (24.22, 3.99, 24.29, 14.01)."""
    m = sum(xs) / len(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def stdev_p(xs):
    m = sum(xs) / len(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def table(head, rows):
    """טבלת HTML: head = כותרות, rows = רשימת שורות (התא הראשון בכל שורה — כותרת שורה)."""
    h = "<table><tr>" + "".join("<th>%s</th>" % x for x in head) + "</tr>"
    for r in rows:
        h += "<tr><th>%s</th>" % r[0] + "".join("<td>%s</td>" % x for x in r[1:]) + "</tr>"
    return h + "</table>"


# מקדם K לפי רמת שירות — הטבלה של ניצן (מצגת 5, שקף 12). ערכים דו-צדדיים:
# ההסתברות להימצא בין שני גבולות; ההסתברות לחוסר = (1 − רמת השירות) / 2.
KTAB = {0.85: 1.44, 0.88: 1.56, 0.90: 1.65, 0.92: 1.75, 0.95: 1.96}

Q = []


def add(q, a, d, e, calc=True, s=None):
    it = dict(q=q, a=a, d=list(d), e=e)
    if calc:
        it["k"] = "calc"
    if s:
        it["s"] = s
    Q.append(it)
