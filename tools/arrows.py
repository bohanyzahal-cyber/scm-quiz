# -*- coding: utf-8 -*-
"""מחליף חצים ימניים (→ ➔) בחץ שמאלי (←) כשלפחות אחד השכנים הוא אות עברית
או ספרה — שם כיוון הקריאה הוא מימין לשמאל. בין שתי מילים לועזיות החץ נשאר."""
import re, sys, io
sys.stdout.reconfigure(encoding="utf-8")
HEB = re.compile(r"[\u0590-\u05FF0-9]")
def neighbor(s, i, step):
    j = i + step
    while 0 <= j < len(s):
        ch = s[j]
        if ch.isalnum() or "\u0590" <= ch <= "\u05FF":
            return ch
        j += step
    return ""
def fix(s):
    out = list(s); n = 0
    for i, ch in enumerate(s):
        if ch in "→➔":
            a, b = neighbor(s, i, -1), neighbor(s, i, +1)
            if HEB.match(a or "x") or HEB.match(b or "x"):
                out[i] = "←"; n += 1
    return "".join(out), n
tot = 0
for p in sys.argv[1:]:
    s = io.open(p, encoding="utf-8").read()
    t, n = fix(s)
    if n:
        io.open(p, "w", encoding="utf-8").write(t)
    kept = t.count("→") + t.count("➔")
    print("%-28s הוחלפו %3d · נשארו ימניים (בין מילים לועזיות) %d" % (p.replace("\\","/").split("/")[-1], n, kept))
    tot += n
print("סה״כ", tot)
