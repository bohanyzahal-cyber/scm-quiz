# -*- coding: utf-8 -*-
"""
בונה את פרקי הפודקאסט מקבצי התסריט שב-scripts/, ואת דף הנגן index.html.

  cd podcast && python nikud.py            # מנקד שורות חדשות (חובה לפני בנייה)
  python build.py                          # בונה את כל הפרקים שהשתנו
  python build.py 03                       # בונה רק פרק מסוים
  python build.py --force                  # מתעלם מהמטמון ובונה הכל מחדש

פורמט התסריט (scripts/NN-slug.txt):
    # title: שם הפרק
    א: שורה של המסביר (קול גברי, Avri)
    ש: שורה של המראיינת (קול נשי, Hila)
    ~4                     -> שקט של 4 שניות (זמן לחשוב על שאלה)
    שורה ריקה              -> הפסקה בין פסקאות
    # הערה                 -> לא נקרא

כל שורה מסונתזת בנפרד ונשמרת במטמון לפי גיבוב הטקסט+הקול, כך ששינוי שורה
אחת אינו מחייב סינתזה מחדש של הפרק כולו. הצינור הועתק מפודקאסט הקורס
ניהול מערכות תובלה ושינוע (דרך שיטות וכלי ניהול מתקדמים), שם נבדקו הקולות,
הניקוד וקצב ההפסקות.
"""
import asyncio
import hashlib
import html
import os
import re
import subprocess
import sys
import time
import urllib.parse

import edge_tts

# קונסולת Windows ברירת מחדל היא cp1252 ומתה על עברית
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
CACHE = os.path.join(HERE, ".cache")
OUT = os.path.join(HERE, "mp3")

COURSE = "ניהול שרשרת ההספקה"
VOICES = {"א": "he-IL-AvriNeural", "ש": "he-IL-HilaNeural"}
RATE = "+0%"
ALBUM = COURSE + " — פודקאסט תרגול"
GAP = 0.45                      # הפסקה בין דוברים
PARA_GAP = 0.9                  # הפסקה בין פסקאות
CONCURRENCY = 6                 # בקשות סינתזה במקביל

# הפרקים שתוכננו. פרק שעוד אין לו קובץ שמע מוצג בדף הנגן כ„בהכנה״.
PLANNED = [
    ("01", "חיזוי — אינטגרציה, שיטות וחיזוי עונתי"),
    ("02", "ניהול מלאי — עלויות, מודל המסור ואילוצים"),
    ("03", "מלאי ביטחון ונקודת הזמנה"),
    ("04", "פארטו ופילוחים — אי בי סי ופילוח רב ממדי"),
    ("05", "אחזקה ואמינות — גישות, עלויות, טור ומקביל"),
    ("06", "תדירות אחזקה מונעת ונקודת איזון"),
    ("07", "שלמה — מבנה השרשרת וניהול חומר"),
    ("08", "שלמה — רכש, ייצור ומיקור חוץ"),
    ("09", "שלמה — הזמנות לקוח ולוגיסטיקה"),
    ("10", "שלמה — אסטרטגיה, זמישות וארגז הכלים"),
    ("11", "חזרה למבחן — מלכודות החישוב וטעויות בשקפים"),
]

# ffmpeg מקודד הכל מחדש לפרמטר אחיד, כך שגם קטעי השקט מתחברים חלק
AUDIO_ARGS = ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1"]


def sh(args):
    r = subprocess.run(args, capture_output=True)
    if r.returncode:
        sys.exit("ffmpeg נכשל:\n" + r.stderr.decode("utf-8", "replace")[-2000:])
    return r


def parse(path):
    """מפרק קובץ תסריט לרשימת קטעים: ('say', voice, text) או ('gap', seconds)."""
    title = os.path.splitext(os.path.basename(path))[0]
    parts, pending_gap = [], 0.0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("# title:"):
                title = line.split(":", 1)[1].strip()
                continue
            if line.startswith("#"):
                continue
            if not line:
                pending_gap = max(pending_gap, PARA_GAP)
                continue
            m = re.match(r"^~([\d.]+)$", line)
            if m:
                pending_gap = max(pending_gap, float(m.group(1)))
                continue
            # התסריטים מנוקדים (ראו nikud.py), אז גם אות הדובר עשויה לשאת ניקוד
            m = re.match(r"^([אש])[֑-ׇ]*\s*:\s*(.+)$", line)
            if not m:
                sys.exit(f"שורה לא מזוהה ב-{os.path.basename(path)}:\n  {line}")
            if parts:
                parts.append(("gap", pending_gap or GAP))
            pending_gap = 0.0
            parts.append(("say", VOICES[m.group(1)], m.group(2)))
    return title, parts


def cache_path(kind, key):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE, f"{kind}_{h}.mp3")


async def synth_one(voice, text, dest, sem):
    async with sem:
        for attempt in range(4):
            try:
                comm = edge_tts.Communicate(text, voice, rate=RATE)
                await comm.save(dest + ".part")
                break
            except Exception as e:               # השירות מגביל קצב מדי פעם
                if attempt == 3:
                    raise RuntimeError(f"סינתזה נכשלה: {text[:60]}") from e
                await asyncio.sleep(1.5 * (attempt + 1))
    os.replace(dest + ".part", dest)


async def synth_missing(jobs):
    sem = asyncio.Semaphore(CONCURRENCY)
    await asyncio.gather(*(synth_one(v, t, d, sem) for v, t, d in jobs))


def silence(seconds):
    dest = cache_path("sil", f"{seconds:.3f}")
    if not os.path.exists(dest):
        sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
            "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.3f}",
            *AUDIO_ARGS, dest])
    return dest


def build(path, force=False):
    title, parts = parse(path)
    num = re.match(r"^(\d+)", os.path.basename(path))
    num = num.group(1) if num else "0"
    out = os.path.join(OUT, f"{num} - {title}.mp3")

    jobs, pieces = [], []
    for p in parts:
        if p[0] == "gap":
            pieces.append(silence(p[1]))
            continue
        _, voice, text = p
        dest = cache_path("say", voice + "|" + RATE + "|" + text)
        if force or not os.path.exists(dest):
            jobs.append((voice, text, dest))
        pieces.append(dest)

    if not jobs and os.path.exists(out) and not force:
        print(f"  ✓ {os.path.basename(out)} — ללא שינוי")
        return out

    if jobs:
        print(f"  מסנתז {len(jobs)} שורות…")
        asyncio.run(synth_missing(jobs))

    # כותרת שהשתנתה משאירה אחריה קובץ ישן עם אותו מספר — מוחקים אותו
    for old in os.listdir(OUT):
        if old.startswith(num + " - ") and old != os.path.basename(out):
            os.remove(os.path.join(OUT, old))

    listfile = os.path.join(CACHE, f"list_{num}.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for p in pieces:
            f.write("file '" + p.replace("\\", "/").replace("'", r"'\''") + "'\n")

    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", listfile, *AUDIO_ARGS,
        "-metadata", f"title={num} · {title}",
        "-metadata", f"album={ALBUM}",
        "-metadata", f"artist={COURSE}",
        "-metadata", f"track={int(num)}",
        "-metadata", "genre=Education",
        "-id3v2_version", "3",
        out])
    return out


def duration(path):
    # OneDrive מסנכרן את הקובץ בדיוק כשהוא נכתב, וההרצה הראשונה נכשלת לפעמים
    for _ in range(3):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", path],
                           capture_output=True)
        try:
            return float(r.stdout.decode().strip())
        except ValueError:
            time.sleep(0.5)
    return 0.0


def hebrew_duration(seconds):
    """„שעה ו-25 דקות״ ולא „1 שעות ו-25 דקות״. מעוגל לדקה הקרובה."""
    h, m = divmod(int(round(seconds / 60)), 60)
    words = {1: "שעה", 2: "שעתיים"}
    head = words.get(h) if h in words else (f"{h} שעות" if h else "")
    tail = "דקה אחת" if m == 1 else (f"{m} דקות" if m else "")
    return " ו-".join(p for p in (head, tail) if p) or "0 דקות"


# כיוון הכתיבה מוצהר ב-dir על שורש המסמך ולא רק ב-CSS: זה מה שקובע את כיוון
# הבסיס לאלגוריתם הדו-כיווני, והוא שורד גם אם הגיליון לא נטען. הצבעים ומפתח
# ערכת הנושא (scmq_theme) זהים לבוחן, כך שמצב כהה/בהיר עובר בין הדפים.
INDEX_HEAD = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>פודקאסט — __COURSE__</title>
<script>try{var t=localStorage.getItem('scmq_theme');if(t)document.documentElement.className=t;}catch(e){}</script>
<style>
:root{--bg:#f5f7f6;--surface:#fff;--surface2:#eef2f1;--text:#1c2321;--muted:#66706d;--border:#dfe5e3;--accent:#1f6f8b;--accentSoft:#e3f0f5;--onAccent:#fff;}
@media (prefers-color-scheme:dark){:root{--bg:#181c1b;--surface:#212625;--surface2:#2b3130;--text:#e9ecea;--muted:#9ea7a4;--border:#333b39;--accent:#6fb7d3;--accentSoft:#1c3441;--onAccent:#0b1f1c;}}
html.dark{--bg:#181c1b;--surface:#212625;--surface2:#2b3130;--text:#e9ecea;--muted:#9ea7a4;--border:#333b39;--accent:#6fb7d3;--accentSoft:#1c3441;--onAccent:#0b1f1c;}
html.light{--bg:#f5f7f6;--surface:#fff;--surface2:#eef2f1;--text:#1c2321;--muted:#66706d;--border:#dfe5e3;--accent:#1f6f8b;--accentSoft:#e3f0f5;--onAccent:#fff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:'Segoe UI',Arial,sans-serif;line-height:1.6;}
.wrap{max-width:760px;margin:0 auto;padding:22px 16px 60px;}
.top{display:flex;align-items:flex-start;gap:12px;}
.top div{flex:1;min-width:0;}
h1{font-size:23px;margin:0 0 4px;font-weight:650;}
.sub{color:var(--muted);font-size:14px;margin:0 0 4px;}
.tot{color:var(--muted);font-size:13px;margin:0 0 16px;}
.iconbtn{background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:7px 11px;font:inherit;font-size:14px;cursor:pointer;flex:none;}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;}
.nav a{flex:1 1 240px;display:inline-flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:9px 14px;color:var(--text);text-decoration:none;font-size:13.5px;}
.nav a:hover{border-color:var(--accent);}
.nav b{font-weight:650;}
.nav em{font-style:normal;color:var(--muted);}
.speed{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0 0 14px;color:var(--muted);font-size:13.5px;}
.speed button{background:var(--surface);border:1px solid var(--border);color:var(--text);border-radius:999px;padding:4px 12px;font:inherit;font-size:13px;cursor:pointer;}
.speed button.on{background:var(--accent);border-color:var(--accent);color:var(--onAccent);}
.ep{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;margin-bottom:12px;}
.hd{display:flex;align-items:baseline;gap:10px;margin-bottom:10px;}
.num{background:var(--accent);color:var(--onAccent);border-radius:6px;padding:1px 8px;font-size:13px;font-weight:700;flex:none;}
.ttl{font-weight:600;flex:1;min-width:0;}
.dur{color:var(--muted);font-size:13px;flex:none;font-variant-numeric:tabular-nums;}
audio{width:100%;height:40px;display:block;}
.row{display:flex;justify-content:flex-start;gap:12px;margin-top:8px;font-size:13px;color:var(--muted);}
.row a{color:var(--accent);text-decoration:none;}
.row a:hover{text-decoration:underline;}
.soon{background:transparent;border-style:dashed;padding:10px 16px;}
.soon .hd{margin:0;}
.soon .num{background:var(--surface2);color:var(--muted);}
.soon .ttl{font-weight:400;color:var(--muted);}
.note{color:var(--muted);font-size:13px;margin-top:24px;border-top:1px solid var(--border);padding-top:14px;}
</style>
</head>
<body>
<div class="wrap">
<div class="top"><div>
<h1>פודקאסט — __COURSE__</h1>
<p class="sub">פרק לכל נושא, בשני קולות — שישה פרקים לניצן, ארבעה לשלמה ופרק חזרה. בסוף כל פרק: שאלות לדרך, עם שקט קצר לחשוב לפני התשובה.</p>
</div><button class="iconbtn" id="theme" title="מצב כהה / בהיר">◐</button></div>
"""

INDEX_NAV = """<div class="nav">
<a href="../index.html">🎯 <span><b>בוחן התרגול</b> <em>· שאלות אמריקאיות וסימולציית מבחן</em></span></a>
<a href="../%D7%A0%D7%95%D7%A1%D7%97%D7%90%D7%95%D7%AA.html">📐 <span><b>דף נוסחאות ומושגים</b> <em>· כל נוסחה עם דוגמה פתורה</em></span></a>
</div>
<div class="speed">מהירות השמעה:
<button type="button" dir="ltr" data-r="1">×1</button><button type="button" dir="ltr" data-r="1.25">×1.25</button><button type="button" dir="ltr" data-r="1.5">×1.5</button>
</div>
"""

INDEX_TAIL = """<p class="note">אפשר להוריד את הפרקים ולהאזין בלי אינטרנט. הקבצים מתויגים כאלבום אחד לפי מספר פרק, כך שכל נגן ישמור על הסדר.
הקולות מסונתזים, והתסריטים נכתבו מאותו חומר של הבוחן ודף הנוסחאות, כדי שכולם יגידו אותו דבר.</p>
</div>
<script>
(function(){
  var audios=[].slice.call(document.querySelectorAll('audio'));
  var btns=[].slice.call(document.querySelectorAll('.speed button'));
  var rate=1;try{rate=parseFloat(localStorage.getItem('scmq_rate'))||1;}catch(e){}
  function setRate(r){rate=r;audios.forEach(function(a){a.playbackRate=r;});
    btns.forEach(function(b){b.classList.toggle('on',parseFloat(b.getAttribute('data-r'))===r);});
    try{localStorage.setItem('scmq_rate',String(r));}catch(e){}}
  btns.forEach(function(b){b.onclick=function(){setRate(parseFloat(b.getAttribute('data-r')));};});
  audios.forEach(function(a){
    a.addEventListener('play',function(){a.playbackRate=rate;
      audios.forEach(function(o){if(o!==a)o.pause();});});
  });
  setRate(rate);
  document.getElementById('theme').onclick=function(){
    var cur=document.documentElement.className;
    var dark=cur==='dark'||(cur!=='light'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches);
    var nx=dark?'light':'dark';document.documentElement.className=nx;
    try{localStorage.setItem('scmq_theme',nx);}catch(e){}
  };
})();
</script>
</body>
</html>
"""


def episodes():
    """כל קובצי הפרקים שבתיקיית mp3, לפי מספר — גם אם נבנו בהרצות קודמות."""
    rows = []
    for name in sorted(os.listdir(OUT)):
        m = re.match(r"^(\d+) - (.+)\.mp3$", name)
        if m:
            path = os.path.join(OUT, name)
            rows.append((m.group(1), m.group(2), name, duration(path), os.path.getsize(path) / 1e6))
    return rows


def write_index():
    rows = episodes()
    total = sum(r[3] for r in rows)
    built = {r[0] for r in rows}
    soon = [(n, t) for n, t in PLANNED if n not in built]
    parts = [INDEX_HEAD.replace("__COURSE__", COURSE)]
    count = f"{len(rows)} פרקים" if len(rows) != 1 else "פרק אחד"
    extra = f" · {len(soon)} נוספים בהכנה" if soon else ""
    parts.append(f'<p class="tot">{count} · {hebrew_duration(total)}{extra}</p>\n')
    parts.append(INDEX_NAV)
    for num, title, name, d, size in rows:
        href = "mp3/" + urllib.parse.quote(name)
        # bdi סוגר את רצפי הספרות בתוך פסקה ימין-לשמאל, כך שמספר הפרק ואורכו
        # לא נגררים למקום אחר לפי מה שמקיף אותם
        parts.append(
            f'<div class="ep" id="ep{num}"><div class="hd">'
            f'<bdi class="num">{num}</bdi>'
            f'<span class="ttl">{html.escape(title)}</span>'
            f'<bdi class="dur">{int(d // 60)}:{int(d % 60):02d}</bdi></div>'
            f'<audio controls preload="none" src="{href}"></audio>'
            f'<div class="row"><a href="{href}" download="{html.escape(name, quote=True)}">⬇ הורדה</a>'
            f'<bdi>{size:.1f} MB</bdi></div></div>\n')
    for num, title in soon:
        parts.append(f'<div class="ep soon"><div class="hd"><bdi class="num">{num}</bdi>'
                     f'<span class="ttl">{html.escape(title)}</span>'
                     f'<span class="dur">בהכנה</span></div></div>\n')
    parts.append(INDEX_TAIL)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write("".join(parts))
    return rows


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = [a for a in args if not a.startswith("--")]

    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    files = sorted(f for f in os.listdir(SCRIPTS) if f.endswith(".txt"))
    if only:
        files = [f for f in files if any(f.startswith(o) for o in only)]
    if not files:
        sys.exit("לא נמצאו תסריטים ב-scripts/")

    for f in files:
        print(f"\n▸ {f}")
        out = build(os.path.join(SCRIPTS, f), force)
        d = duration(out)
        print(f"  → {int(d // 60)}:{int(d % 60):02d}  ({os.path.getsize(out) / 1e6:.1f} MB)")

    rows = write_index()           # דף הנגן תמיד מכל הפרקים שבתיקייה
    print("\n" + "─" * 58)
    for num, title, name, d, size in rows:
        print(f"{int(d // 60):>3}:{int(d % 60):02d}  {size:>5.1f} MB  {name}")
    print("─" * 58)
    print(f"סה״כ {len(rows)} פרקים · {hebrew_duration(sum(r[3] for r in rows))} · "
          f"{sum(r[4] for r in rows):.0f} MB")


if __name__ == "__main__":
    main()
