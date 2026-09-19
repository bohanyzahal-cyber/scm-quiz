# -*- coding: utf-8 -*-
"""בונה קובץ בנק (bankN.js) מקובץ נתונים בפייתון.

שימוש:  python mkbank.py <data.py> <out.js>

קובץ הנתונים מגדיר:
  T     — שם הנושא (שדה t)
  S     — מקור ברירת מחדל (שדה s)
  KEEP  — (אופציונלי) נתיב לקובץ שורות JS קיימות שנשמרות בראש הבנק
  Q     — רשימת מילונים: q (שאלה), a (התשובה הנכונה), d (שלושה מסיחים),
          e (הסבר), ואופציונלי s (מקור) ו-k ("calc")

הכלי מציב את התשובה הנכונה במיקום מאוזן (0–3) ומדפיס בדיקת אורך:
L = הנכונה ארוכה מכל המסיחים ביותר מ-2 תווים, S = קצרה מכולם ביותר מ-2.
"""
import sys, io, json, random, importlib.util, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

data_path, out_path = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("bankdata", data_path)
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)

T, S, Q = D.T, D.S, D.Q
keep = []
if getattr(D, "KEEP", None) and os.path.exists(D.KEEP):
    keep = [l.rstrip().rstrip(",") for l in io.open(D.KEEP, encoding="utf-8") if l.startswith("{t:")]

def js(x):
    return json.dumps(x, ensure_ascii=False)

# ---- בדיקות קלט ----
errs = []
for i, it in enumerate(Q):
    for f in ("q", "a", "d", "e"):
        if f not in it: errs.append("#%d חסר שדה %s" % (i, f))
    if len(it.get("d", [])) != 3: errs.append("#%d — צריך בדיוק 3 מסיחים" % i)
    allo = [it.get("a")] + list(it.get("d", []))
    if len(set(allo)) != 4: errs.append("#%d — אפשרות כפולה" % i)
    for fld in [it.get("q",""), it.get("e",""), it.get("a","")] + list(it.get("d", [])):
        if '"' in fld: errs.append("#%d — מרכאות ASCII בתוך טקסט: %s" % (i, fld[:40]))
if errs:
    print("\n".join(errs)); sys.exit(1)

# ---- מיקום מאוזן של התשובה הנכונה ----
kept_c = []
for l in keep:
    import re
    m = re.search(r",c:(\d),e:", l)
    if m: kept_c.append(int(m.group(1)))
rng = random.Random(T)
need = len(Q)
counts = [kept_c.count(k) for k in range(4)]
pos = []
for _ in range(need):
    lo = min(counts)
    cand = [k for k in range(4) if counts[k] == lo]
    k = rng.choice(cand); pos.append(k); counts[k] += 1
rng.shuffle(pos)

lines, flags = [], []
for i, it in enumerate(Q):
    ds = list(it["d"]); rng.shuffle(ds)
    c = pos[i]
    opts = ds[:c] + [it["a"]] + ds[c:]
    s = it.get("s", S)
    line = "{t:%s,s:%s,q:%s,o:[%s],c:%d,e:%s%s}" % (
        js(T), js(s), js(it["q"]), ",".join(js(o) for o in opts), c, js(it["e"]),
        (",k:" + js(it["k"])) if it.get("k") else "")
    lines.append(line)
    la, ld = len(it["a"]), [len(x) for x in it["d"]]
    tag = "L" if la > max(ld) + 2 else ("S" if la < min(ld) - 2 else "")
    flags.append(tag)
    if tag:
        print("  %s #%d  נכונה=%d  מסיחים=%s  %s" % (tag, i, la, ld, it["q"][:60]))

body = keep + lines
out = "BANK.push.apply(BANK,[\n" + ",\n".join(body) + "\n]);\n"
io.open(out_path, "w", encoding="utf-8").write(out)

nL, nS = flags.count("L"), flags.count("S")
n = len(Q)
cc = [0]*4
for l in body:
    import re
    cc[int(re.search(r",c:(\d),e:", l).group(1))] += 1
print("נכתב %s: %d שאלות (%d נשמרו + %d חדשות) · c=%s · חדשות: נכונה-ארוכה-בבירור %d%% · נכונה-קצרה-בבירור %d%%"
      % (os.path.basename(out_path), len(body), len(keep), n, cc, round(100*nL/max(n,1)), round(100*nS/max(n,1))))
