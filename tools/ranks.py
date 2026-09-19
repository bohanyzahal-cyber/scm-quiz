# -*- coding: utf-8 -*-
"""דירוג אורך הנכונה בכל שאלה בקובץ נתונים: 0=הארוכה (כולל שוויון), 3=הקצרה.
שימוש: python tools/ranks.py tools/data/bankN.py"""
import sys, re, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("d", sys.argv[1]); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
rk = [0, 0, 0, 0]
for i, it in enumerate(D.Q):
    vl = lambda x: len(re.sub(r"<[^>]+>", "", x))
    la = vl(it["a"]); ld = sorted([vl(x) for x in it["d"]], reverse=True)
    r = sum(1 for x in ld if x >= la)
    rk[min(r, 3)] += 1
    print("#%-3d r%d %s נכונה %3d | מסיחים %s | %s" % (i, r, "C" if it.get("k") else " ", la, ld, it["a"][:50]))
n = len(D.Q)
print("פיזור (ארוכה/שנייה/שלישית/קצרה):", rk, " באחוזים:", [round(100 * x / n) for x in rk])
