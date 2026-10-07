# -*- coding: utf-8 -*-
"""בונה קובץ בנק (bankN.js) מקובץ נתונים בפייתון.

שימוש:  python mkbank.py <data.py> <out.js>

קובץ הנתונים מגדיר:
  T     — שם הנושא (שדה t)
  S     — מקור ברירת מחדל (שדה s)
  KEEP  — (אופציונלי) נתיב לקובץ שורות JS קיימות שנשמרות בראש הבנק
  SEED  — (אופציונלי) זרע לסידור התשובות; ברירת המחדל היא שם הנושא T
  Q     — רשימת מילונים: q (שאלה), a (התשובה הנכונה), d (שלושה או ארבעה מסיחים —
          ארבעה בשאלות בפורמט של ניצן, חמש תשובות א׳–ה׳), e (הסבר), ואופציונלי
          s (מקור), t (נושא), k ("calc") ו-m (שאלת מרצה: 1 = כלשונה מהדף של שלמה,
          2 = שוחזרה מהקלטה, 3 = שוחזרה מתמלול שיעור הסיכום, 4 = מהבחינה לדוגמה
          של ניצן, 5 = משאלות התרגול שניצן צירף לבחינה לדוגמה).
          שאלת מרצה שבה תשובה מפנה לתשובות אחרות (״א׳ ו-ב׳ נכונות״) נכתבת
          עם o (האפשרויות בסדר המקורי) ו-c (אינדקס הנכונה) במקום a/d,
          ומקבלת fx:1 — האפליקציה לא מערבבת אותה.

הכלי מציב את התשובה הנכונה במיקום מאוזן ומדפיס בדיקת אורך:
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
    if "o" in it:                               # סדר מקורי קבוע: o + c במקום a + d
        if len(it["o"]) not in (4, 5) or it.get("c") not in range(len(it["o"])):
            errs.append("#%d — סדר קבוע: צריך 4 או 5 אפשרויות ב-o ו-c בתחום" % i)
            continue
        it["a"] = it["o"][it["c"]]
        it["d"] = [x for k, x in enumerate(it["o"]) if k != it["c"]]
    for f in ("q", "a", "d", "e"):
        if f not in it: errs.append("#%d חסר שדה %s" % (i, f))
    if len(it.get("d", [])) not in (3, 4): errs.append("#%d — צריך 3 או 4 מסיחים" % i)
    allo = [it.get("a")] + list(it.get("d", []))
    if len(set(allo)) != len(allo): errs.append("#%d — אפשרות כפולה" % i)
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
rng = random.Random(getattr(D, "SEED", T))   # SEED — כששם הנושא משתנה ורוצים לשמור על אותו סידור תשובות
if all(len(it["d"]) == 3 for it in Q):
    # בנק של ארבע אפשרויות בלבד — האלגוריתם המקורי, כדי שבנייה חוזרת תיתן אותו פלט בדיוק
    need = len(Q)
    counts = [kept_c.count(k) + sum(1 for it in Q if "o" in it and it["c"] == k) for k in range(4)]
    pos = []
    for _ in range(need):
        lo = min(counts)
        cand = [k for k in range(4) if counts[k] == lo]
        k = rng.choice(cand); pos.append(k); counts[k] += 1
    rng.shuffle(pos)
else:
    # יש גם שאלות של חמש אפשרויות: איזון נפרד לכל גודל, והתשובה הנכונה מתפזרת באופן אחיד בין המיקומים
    counts = {4: [kept_c.count(k) for k in range(4)], 5: [0] * 5}
    for it in Q:
        if "o" in it:
            counts[len(it["o"])][it["c"]] += 1
    pos = [0] * len(Q)
    for g in (4, 5):
        idxs = [i for i, it in enumerate(Q) if "o" not in it and len(it["d"]) + 1 == g]
        vals = []
        for _ in idxs:
            lo = min(counts[g])
            cand = [k for k in range(g) if counts[g][k] == lo]
            k = rng.choice(cand); vals.append(k); counts[g][k] += 1
        rng.shuffle(vals)                      # שהמיקום לא ייגזר מסדר הכתיבה
        for i, v in zip(idxs, vals):
            pos[i] = v

# ---- בידוד רצפים לטיניים/יווניים (bidi) ----
# בטקסט עברי, מספר שבא אחרי אות לטינית/יוונית ״נבלע״ ברצף משמאל לימין:
# ״ו-μ; 12.50 — בלי ln״ מוצג כ״ו-12.50 ;μ״, ו״1/Ф״ בתחילת אפשרות מוצג כ״Ф/1״.
# לכן כל רצף שמתחיל באות לטינית/יוונית (כולל קידומת כמו ״1/״) נעטף ב-<bdi dir='ltr'>.
# תוכן שכבר בתוך <bdi> ותגיות HTML אינם נוגעים.
import re
_SEG = re.compile(r"(<bdi[^>]*>.*?</bdi>|<[^>]+>)", re.S)
_LET = "A-Za-zͰ-ϿЀ-ӿ"
_RUN = re.compile(r"(?:\d+(?:[.,]\d+)?(?:\s*[/·*]\s*)?)?[" + _LET + "√Σ∑Π]"   # כולל ״2.6M״ ו״1/Ф״
                  r"[" + _LET + r"0-9 =+−\-·/*^()\[\].,%²³⁴⁰¹⌈⌉⌊⌋√≈<>≤≥_∑Σ→➔]*")
# החץ → בתוך הרצף: ״LCL → FCL״ הוא רצף אחד משמאל לימין. כששני הצדדים בודדו בנפרד,
# הסדר החזותי בשורה עברית התהפך (FCL → LCL על המסך) — בדיוק ההפך מהכתוב.

def _trim(r):
    while True:
        r0 = r
        r = r.rstrip(" .,;:−-([=+·/^<>≈≤≥→➔")     # לא לסיים ברצף באופרטור או בחץ (אבל * של Q* נשאר)
        if r.endswith(")") and r.count(")") > r.count("("):
            r = r[:-1]
        if r.endswith("]") and r.count("]") > r.count("["):
            r = r[:-1]
        if r == r0:
            return r

def iso(text):
    parts = _SEG.split(text)
    for k in range(0, len(parts), 2):          # רק קטעי טקסט רגיל (לא תגיות ולא bdi קיים)
        seg, out, pos = parts[k], [], 0
        for m in _RUN.finditer(seg):
            r = _trim(m.group(0))
            if not r:
                continue
            out.append(seg[pos:m.start()])
            out.append("<bdi dir='ltr'>" + r + "</bdi>")
            pos = m.start() + len(r)
        out.append(seg[pos:])
        parts[k] = "".join(out)
    # סוגריים שעוטפים רצף מבודד — בתוך הבידוד, כדי שלא יישברו לשורה נפרדת: (<bdi>L=5</bdi>) ← <bdi>(L=5)</bdi>
    return re.sub(r"\(<bdi dir='ltr'>([^<]*)</bdi>\)", lambda m: "<bdi dir='ltr'>(" + m.group(1) + ")</bdi>", "".join(parts))

if os.environ.get("NOISO"):                  # להשוואה מול הפלט הישן
    iso = lambda s: s

def vlen(s):
    """אורך נראה — בלי תגיות HTML (כדי שבדיקת האורך לא תושפע מ-bdi)."""
    return len(re.sub(r"<[^>]+>", "", s))

lines, flags = [], []
for i, it in enumerate(Q):
    ds = list(it["d"]); rng.shuffle(ds)
    c = pos[i]
    opts = ds[:c] + [it["a"]] + ds[c:]
    if "o" in it:                               # סדר מקורי קבוע
        opts, c = list(it["o"]), it["c"]
    s = it.get("s", S)
    line = "{t:%s,s:%s,q:%s,o:[%s],c:%d,e:%s%s%s%s%s}" % (
        js(it.get("t", T)), js(s), js(iso(it["q"])), ",".join(js(iso(o)) for o in opts), c, js(iso(it["e"])),
        (",k:" + js(it["k"])) if it.get("k") else "",
        (",m:%d" % it["m"]) if it.get("m") else "",
        ",y:1" if it.get("y") else "",          # y — שאלה חדשה בסגנון הבחינה לדוגמה של ניצן
        ",fx:1" if "o" in it else "")
    lines.append(line)
    la, ld = vlen(it["a"]), [vlen(x) for x in it["d"]]
    tag = "L" if la > max(ld) + 2 else ("S" if la < min(ld) - 2 else "")
    flags.append(tag)
    if tag:
        print("  %s #%d  נכונה=%d  מסיחים=%s  %s" % (tag, i, la, ld, it["q"][:60]))

body = keep + lines
out = "BANK.push.apply(BANK,[\n" + ",\n".join(body) + "\n]);\n"
io.open(out_path, "w", encoding="utf-8").write(out)

nL, nS = flags.count("L"), flags.count("S")
n = len(Q)
cc = [0]*5
for l in body:
    import re
    cc[int(re.search(r",c:(\d),e:", l).group(1))] += 1
print("נכתב %s: %d שאלות (%d נשמרו + %d חדשות) · c=%s · חדשות: נכונה-ארוכה-בבירור %d%% · נכונה-קצרה-בבירור %d%%"
      % (os.path.basename(out_path), len(body), len(keep), n, cc, round(100*nL/max(n,1)), round(100*nS/max(n,1))))
