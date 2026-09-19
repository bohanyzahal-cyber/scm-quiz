# -*- coding: utf-8 -*-
"""מחיל את בידוד ה-bidi של mkbank (iso) על קובצי בנק שנכתבו ידנית.
שימוש: python tools/isofix.py <file.js|file.jsl> ...
כל שורת שאלה ({t:...}) נקראת עם node, והכלי מוודא שכתיבה-מחדש בלי שינוי משחזרת
את השורה בדיוק — רק אז הוא כותב את הגרסה עם הבידוד (q, o, e בלבד; t/s/k לא נוגעים)."""
import sys, io, json, re, subprocess, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "mkbank.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("import re\n_SEG"):src.index("if os.environ.get(\"NOISO\")")], ns)
iso = ns["iso"]
js = lambda x: json.dumps(x, ensure_ascii=False)

def ser(o, f=lambda s: s):
    return "{t:%s,s:%s,q:%s,o:[%s],c:%d,e:%s%s}" % (
        js(o["t"]), js(o["s"]), js(f(o["q"])), ",".join(js(f(x)) for x in o["o"]), o["c"], js(f(o["e"])),
        (",k:" + js(o["k"])) if o.get("k") else "")

for path in sys.argv[1:]:
    lines = io.open(path, encoding="utf-8").read().split("\n")
    qi = [i for i, l in enumerate(lines) if l.startswith("{t:")]
    objs = json.loads(subprocess.run(["node", "-e",
        r"const L=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(L.map(l=>eval('('+l.replace(/,\s*$/,'')+')'))))"],
        input=json.dumps([lines[i] for i in qi]), capture_output=True, text=True, encoding="utf-8").stdout)
    changed = 0
    for i, o in zip(qi, objs):
        raw = lines[i]
        tail = raw[len(raw.rstrip(",")):]            # פסיק סוגר, אם יש
        body = raw.rstrip(",")
        if ser(o) != body or set(o) - {"t", "s", "q", "o", "c", "e", "k"}:
            print("  !! %s שורה %d — פורמט לא צפוי, לא שונתה" % (os.path.basename(path), i + 1))
            continue
        new = ser(o, iso) + tail
        if new != raw:
            lines[i] = new; changed += 1
    io.open(path, "w", encoding="utf-8").write("\n".join(lines))
    print("%s: %d שאלות, %d עודכנו" % (os.path.basename(path), len(qi), changed))
