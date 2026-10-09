# -*- coding: utf-8 -*-
"""בונה חוברת מודפסת למבחן בחומר פתוח מתוך דף הנוסחאות: PDF עם מספרי עמודים, תוכן עניינים ומפתח מונחים.

  cd scm-quiz && python tools/booklet.py

מה נעשה:
  * הפרקים שאינם במבחן (מצגות 8–11) מושמטים.
  * כל פרק מקבל מספר (§5) וכל כרטיס מספר משנה (§5.3); כל פרק מתחיל בעמוד חדש.
  * נספח: שאלות המאגר של שלמה — שאלה והתשובה הנכונה בלבד.
  * שני מעברים: במעבר הראשון מודפס PDF ונמצא העמוד של כל §; בשני העמודים נכתבים לתוכן העניינים ולמפתח.
  * בסוף מוטבעים בראש כל עמוד מספר העמוד והפרקים שבו (לדפדוף מהיר).
הפלט: ״חוברת למבחן - ניהול שרשרת ההספקה.pdf״ בתיקיית הקורס.
"""
import io, os, re, sys, json, subprocess, tempfile
import fitz

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(os.path.dirname(ROOT), "חוברת למבחן - ניהול שרשרת ההספקה.pdf")
CHROME = [p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                      r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") if os.path.exists(p)][0]
DROP = ("rel", "pm", "be")            # לא במבחן


def strip(t):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", t)).strip()


src = io.open(os.path.join(ROOT, "נוסחאות.html"), encoding="utf-8").read()
body = src[src.index('<h2 id="exam">'):src.rindex("</body>")].rstrip()
assert body.endswith("</div>")
body = body[:-len("</div>")]                       # סגירת ה-wrap

body = body.replace('<div class="card"><h3>הבחינה לדוגמה — הפתרונות', '<div class="card wide"><h3>הבחינה לדוגמה — הפתרונות')
body = re.sub(r'<div class="sub" style="margin-top:26px">.*?</div>', '', body, flags=re.S)      # שורת הקישורים שבתחתית הדף
# ---- פיצול לפרקים
parts = re.split(r'(?=<h2 id=")', body)
secs = []
for p in parts:
    m = re.match(r'<h2 id="(\w+)">(.*?)</h2>', p, re.S)
    if not m or m.group(1) in DROP:
        continue
    secs.append([m.group(1), m.group(2), p[m.end():]])

# ---- נספח: המאגר של שלמה (שאלה + התשובה הנכונה)
js = ("const fs=require('fs');const B=[];(new Function('BANK',fs.readFileSync(process.argv[1],'utf8')"
      ".replace(/^\\s*(var|let|const)\\s+BANK\\s*=.*$/m,'')))(B);"
      "console.log(JSON.stringify(B.filter(q=>q.m).map(q=>({t:q.t,q:q.q,a:q.o[q.c]}))))")
bank = json.loads(subprocess.run(["node", "-e", js, os.path.join(ROOT, "src", "bank22.js")],
                                 capture_output=True, encoding="utf-8").stdout)
by = {}
for q in bank:
    by.setdefault(q["t"], []).append(q)
app = ['<div class="note">שלמה: שאלות המבחן נלקחות ממאגר של 76 שאלות כאלה, והסדר מעורבב. כאן 38 השאלות שהוצגו או הוקראו בשיעורים — '
       'השאלה והתשובה הנכונה בלבד. לשים לב למילים <b>אינו</b> / <b>הינו</b> בשאלה שבמבחן: הניסוח עשוי להתהפך.</div>']
for t, qs in by.items():
    rows = "".join("<tr><td>%s</td><td><b>%s</b></td></tr>" % (q["q"], q["a"]) for q in qs)
    app.append('<div class="card wide"><h3>%s</h3><table class="qa"><tr><th>השאלה</th><th>התשובה הנכונה</th></tr>%s</table></div>' % (t, rows))
secs.append(["shq", "שלמה — שאלות ממאגר המבחן <small>שאלה ותשובה נכונה</small>", "\n".join(app)])

# ---- מספור § לפרקים ולכרטיסים
cards = []            # (code, כותרת, טקסט הכרטיס)
toc = []              # (code, כותרת)
html_secs = []
for i, (sid, title, content) in enumerate(secs, 1):
    code = "§%d" % i
    toc.append((code, strip(re.sub("<small>.*?</small>", "", title, flags=re.S)), strip("".join(re.findall("<small>(.*?)</small>", title, re.S)))))
    k = [0]
    chunks = re.split(r"(?=<h3>)", content)
    out = []
    for ch in chunks:
        m = re.match(r"<h3>(.*?)</h3>", ch, re.S)
        if m:
            k[0] += 1
            c = "%s.%d" % (code, k[0])
            cards.append((c, strip(re.sub(r'<span class="tag">.*?</span>', "", m.group(1), flags=re.S)), strip(ch)))
            ch = '<h3><bdi dir="ltr" class="sec">%s</bdi> %s</h3>' % (c, m.group(1)) + ch[m.end():]
        out.append(ch)
    html_secs.append('<section><h2><bdi dir="ltr" class="sec">%s</bdi> %s</h2>%s</section>' % (code, title, "".join(out)))

# ---- מפתח מונחים: מונח ← מילת חיפוש; ההפניות נמצאות אוטומטית בכרטיסים שמכילים אותה
TERMS = [
    ("אחוז הפחתה (ממוצע נע משוקלל)", "אחוז הפחתה"), ("אחזקה חזויה", "חזויה"), ("אחזקה מונעת", "מונעת"), ("אחזקת שבר", "אחזקת שבר|שבר:|כיבוי"),
    ("אוקיינוס כחול", "אוקיינוס"), ("אינטגרציה — הפתרון", "VMI"), ("גישה נאיבית", "נאיבית"), ("דלפי", "דלפי"),
    ("החלקה מעריכית — לא במבחן", "החלקה מעריכית"), ("זמינות A", "זמינות"), ("זמישות", "זמישות"), ("מקדם עונתיות", "מקדם עונתיות|מקדם העונתיות"),
    ("כלל האצבע לעונתיות", "1\\.2"), ("טבלת K — רמת שירות", "1\\.65"), ("ימי מחסור", "מחסור"), ("לוגיסטיקה חוזרת", "חוזרת"),
    ("סבבי מלאי / מלאי בשבועות", "סבבי"), ("מחשבון — רגרסיה צעד-צעד", "STAT"), ("מלאי ביטחון B", "מלאי ביטחון|K·S"),
    ("מקדם אחזקת מלאי i", "מקדם אחזקת"), ("מקדם המתאם r", "מתאם"), ("ממוצע נע פשוט", "ממוצע נע פשוט"), ("ממוצע נע משוקלל", "משוקלל"),
    ("נקודת הזמנה O.L", "נקודת הזמנה"), ("עלות הזמנה K", "עלות הזמנה"), ("עלות אחזקה שנתית — שבר ומונע", "השבתה"),
    ("עלות מחזור חיים", "מחזור חיים"), ("ערך צריכה", "ערך צריכה"), ("פארטו — שלבי העבודה", "דירוג מהגבוה"), ("פג תוקף, נפח, קריטיות", "פג תוקף"),
    ("מודל הקרחון", "קרחון"), ("רגרסיה ליניארית", "רגרסיה"), ("שוט השור", "שוט השור"), ("מה לא במבחן", "לא יהיה"), ("מבנה המבחן", "13 "),
    ("פתרונות הבחינה לדוגמה", "הגרסה הסופית"), ("תהליכי האב", "תהליכי האב"), ("חמשת הבלוקים", "הבלוקים"), ("חמש מטרות השרשרת", "חמש מטרות"),
    ("תהליך הרכש — 9 שלבים", "9 שלבים"), ("תמחיר מול המחרה", "המחרה"), ("מטריצת גמישות", "מטריצת גמישות"), ("סוגי מלאי", "סוגי מלאי"),
    ("עלויות מלאי", "עלויות מלאי"), ("מדדי ניהול הזמנות", "מדדי ניהול הזמנות"), ("השנה הראשונה בתפקיד", "השנה הראשונה"), ("מיקור חוץ — רמות", "מיקור חוץ"),
    ("שבעת הבזבוזים", "הבזבוזים"), ("התאמה אסטרטגית", "התאמה אסטרטגית"), ("עיסוקי הליבה", "עיסוקי הליבה"), ("שרשרת פיתוח המוצר", "פיתוח המוצר"),
    ("מודל המסור", "המסור"), ("מדיניות מלאי A / B / C", "קשב ניהולי|מדיניות מלאי"), ("פילוח רב-ממדי (מרפאות)", "מבוטחים"),
] + [(t, t) for t in ("ABC", "Agile", "EOQ", "GloCal", "Imax", "JIT", "KPI", "LCC", "Lean", "MAD", "MSE", "MRD", "MRP", "MTBF", "MTTR",
                      "Make or Buy", "Muda", "OTD", "Pull", "5S", "TPS", "VMI", "Kaizen", "ODM", "3PL", "Benchmark", "SCOR", "ERP", "WMS", "TMS")]
index = []
for name, pat in TERMS:
    # קודם כרטיסים שהמונח בכותרת שלהם, אחר כך כרטיסים שהמונח בגוף; עד שלוש הפניות
    hits = [c for c, h, txt in cards if re.search(pat, h)] + [c for c, h, txt in cards if not re.search(pat, h) and re.search(pat, txt)]
    if hits:
        index.append((name, hits[:3]))
    else:
        print("  (אין במפתח — לא נמצא בדף: %s)" % name)
heb = sorted([x for x in index if not re.match("[A-Za-z0-9]", x[0])], key=lambda x: x[0])
lat = sorted([x for x in index if re.match("[A-Za-z0-9]", x[0])], key=lambda x: x[0].lower())

CSS = """
@page{size:A4;margin:16mm 12mm 12mm}
*{box-sizing:border-box}
body{margin:0;font-family:'Segoe UI',Arial,sans-serif;font-size:10.3pt;line-height:1.42;color:#000;direction:rtl}
h1{font-size:19pt;margin:0 0 2mm}
section{break-before:page}
h2{font-size:14.5pt;margin:0 0 3mm;padding:1.5mm 3mm;background:#111;color:#fff;border-radius:2mm;break-after:avoid}
h2 small{font-weight:400;font-size:9pt;color:#ddd;margin-right:3mm}
h2 .sec{background:#fff;color:#000;border-radius:1.5mm;padding:0 2mm;margin-left:2mm;font-weight:800}
h3{font-size:11pt;margin:0 0 1.5mm;break-after:avoid}
h3 .sec{display:inline-block;background:#000;color:#fff;border-radius:1mm;padding:0 1.6mm;font-size:9pt;margin-left:1.5mm;font-weight:700}
.card{border:0.3mm solid #777;border-radius:2mm;padding:2.5mm 3.5mm;margin-bottom:3mm;break-inside:avoid}
.grid{columns:2;column-gap:4mm}
.grid .card{display:inline-block;width:100%}
.card.wide{break-inside:auto}
.two{columns:2;column-gap:4mm}.two .card{display:inline-block;width:100%}
.f{font-family:'Cambria Math','Times New Roman',serif;font-size:11.5pt;direction:ltr;text-align:left;background:#eee;border-radius:1.5mm;padding:1.2mm 3mm;margin:1.2mm 0;display:block;unicode-bidi:isolate;font-weight:600}
.f.fr{direction:rtl;text-align:right;font-family:'Segoe UI',Arial,sans-serif;font-size:10.5pt}
.f sub{font-size:8pt}
bdi{display:inline-block;max-width:100%}
.ex{margin:1mm 0;padding-right:2.5mm;border-right:0.5mm solid #999}
.note{border-right:1mm solid #000;background:#f1f1f1;padding:1.5mm 3mm;margin:1.5mm 0;font-size:9pt}
.warn{border:0.3mm dashed #000;padding:1.5mm 3mm;margin:1.5mm 0;font-size:9pt}
table{border-collapse:collapse;width:100%;margin:1.5mm 0;font-size:9.4pt}
th,td{border:0.25mm solid #666;padding:0.8mm 2mm;text-align:right;vertical-align:top}
th{background:#ddd}
td.n,th.n{text-align:center;direction:ltr;font-weight:700}
tr{break-inside:avoid}
ul{margin:1mm 0;padding-right:5mm}li{margin:0.4mm 0}
.tag{display:inline-block;font-size:7.5pt;padding:0 2mm;border:0.2mm solid #888;border-radius:3mm;color:#333;margin-right:1mm;font-weight:400}
.k{font-weight:700}
.qa td:first-child{width:58%}
/* עמוד השער */
.front h1{margin-bottom:1mm}
.how{border:0.5mm solid #000;border-radius:2mm;padding:2mm 4mm;margin:2mm 0 3mm;font-size:10pt}
.toc td,.toc th{font-size:10.5pt;padding:1mm 2.5mm}
.toc td.c,.idx td.c{direction:ltr;text-align:center;font-weight:800;white-space:nowrap}
.toc td.p,.idx td.p{direction:ltr;text-align:center;font-weight:800;font-size:11.5pt;width:14mm}
.idxwrap{columns:2;column-gap:6mm}
.idx{break-inside:auto;margin:0}
.idx td{font-size:9pt;padding:0.3mm 1.5mm;border-width:0 0 0.15mm 0;border-color:#aaa}
.idx td.c{font-size:8.6pt}
.idxh{font-weight:800;font-size:11pt;margin:3mm 0 1mm;border-bottom:0.6mm solid #000}
"""


def render(pages):
    """pages: code -> page number (או None במעבר הראשון)."""
    def pg(c):
        return str(pages.get(c, "")) if pages else "00"

    rows = "".join('<tr><td class="c">%s</td><td>%s <span class="tag">%s</span></td><td class="p">%s</td></tr>' % (c, t, sm, pg(c)) if sm else
                   '<tr><td class="c">%s</td><td>%s</td><td class="p">%s</td></tr>' % (c, t, pg(c)) for c, t, sm in toc)

    def idx(items):
        r = []
        for name, hits in items:
            refs = " · ".join('%s <b>%s</b>' % (h, pg(h)) for h in hits)
            r.append('<tr><td>%s</td><td class="c" style="font-weight:400">%s</td></tr>' % (name, refs))
        return '<table class="idx">%s</table>' % "".join(r)

    front = ('<div class="front"><h1>חוברת למבחן — ניהול שרשרת ההספקה</h1>'
             '<div class="how"><b>איך מוצאים מהר:</b> (1) שאלה עם מספרים — קודם <b>§1</b>: סוגי החישוב של ניצן והפתרונות של הבחינה לדוגמה. '
             '(2) מונח או נוסחה — <b>מפתח המונחים</b> שבעמוד הבא: ליד כל מונח מספר הכרטיס (§) ו<b>מספר העמוד</b> בהדגשה. '
             '(3) שאלה של שלמה — הנספח האחרון: שאלות המאגר עם התשובה הנכונה. '
             'בראש כל עמוד מודפסים מספר העמוד והפרקים שבו. המבחן: 25 שאלות — 13 של ניצן (כ-6 חישוב) ו-12 של שלמה.</div>'
             '<table class="toc"><tr><th>§</th><th>הפרק</th><th>עמ׳</th></tr>%s</table></div>' % rows)
    index_html = ('<section><h2>מפתח מונחים <small>§ הכרטיס ומספר העמוד (מודגש)</small></h2>'
                  '<div class="idxh">עברית</div><div class="idxwrap">%s</div>'
                  '<div class="idxh">אנגלית וקיצורים</div><div class="idxwrap">%s</div></section>' % (idx(heb), idx(lat)))
    return ('<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="UTF-8"><style>%s</style></head><body>%s%s%s</body></html>'
            % (CSS, front, index_html, "\n".join(html_secs)))


def to_pdf(html, dest):
    tmp = os.path.join(tempfile.gettempdir(), "scm_booklet.html")
    io.open(tmp, "w", encoding="utf-8").write(html)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf=" + dest, "file:///" + tmp.replace("\\", "/")],
                   capture_output=True, timeout=180)
    return fitz.open(dest)


tmp_pdf = os.path.join(tempfile.gettempdir(), "scm_booklet_pass.pdf")
doc = to_pdf(render(None), tmp_pdf)
n1 = len(doc)
# בעמודי השער והמפתח מופיעים כל הקודים — מאתרים רק מהעמוד שבו מתחיל §1 (כותרת הפרק הראשון)
first = None
for n, page in enumerate(doc, 1):
    if "המבחן והבחינה לדוגמה של ניצן" in page.get_text() and n > 1 and first is None:
        blocks = page.get_text()
        if "איך מוצאים מהר" not in blocks and "מפתח מונחים" not in blocks:
            first = n
assert first, "לא נמצא העמוד הראשון של §1"
pages = {}
codes = [c for c, _, _ in toc] + [c for c, _, _ in cards]
on_page = {}
for n in range(first, len(doc) + 1):
    txt = doc[n - 1].get_text()
    for c in codes:
        num = re.escape(c[1:])
        if re.search(r"(?<![\d.])§\s*%s(?![\d.])" % num, txt) or re.search(r"(?<![\d.])%s\s*§(?![\d.])" % num, txt):
            pages.setdefault(c, n)
            if "." not in c:
                on_page.setdefault(n, []).append(c)
doc.close()
missing = [c for c in codes if c not in pages]
assert not missing, "לא אותרו: %s" % missing

doc = to_pdf(render(pages), tmp_pdf)
assert len(doc) == n1, "מספר העמודים השתנה בין המעברים (%d ← %d)" % (n1, len(doc))
# ---- הטבעה בראש כל עמוד: מספר העמוד והפרקים שבו
cur = ""
for n, page in enumerate(doc, 1):
    if n in on_page:
        cur = on_page[n][-1]
        label = " ".join(on_page[n])
    else:
        label = cur
    w = page.rect.width
    page.insert_text((w - 60, 30), "%d" % n, fontsize=20, fontname="hebo")
    if label and n >= first:
        page.insert_text((28, 30), label, fontsize=15, fontname="hebo")
    page.insert_text((w / 2 - 8, page.rect.height - 14), "%d / %d" % (n, len(doc)), fontsize=8, fontname="helv")
doc.save(OUT, garbage=3, deflate=True)
print("נכתב: %s — %d עמודים (§1 מתחיל בעמ׳ %d); %d מונחים במפתח, %d כרטיסים" % (OUT, len(doc), first, len(index), len(cards)))
for c, t, _ in toc:
    print("  %-4s עמ׳ %-3d %s" % (c, pages[c], t))
