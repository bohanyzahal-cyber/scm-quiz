# -*- coding: utf-8 -*-
# שאלות שבהן הנכונה היא השנייה באורכה — עם אורכי כל האפשרויות, לצורך פיזור
import sys, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("d", sys.argv[1]); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
rk = [0,0,0,0]
for i, it in enumerate(D.Q):
    la = len(it["a"]); ld = sorted([len(x) for x in it["d"]], reverse=True)
    r = sum(1 for x in ld if x >= la)          # 0 = הארוכה (כולל שוויון בראש), 1 = שנייה...
    rk[min(r,3)] += 1
    if r == 1:
        print("#%-3d נכונה %3d | מסיחים %s | %s" % (i, la, ld, it["a"][:60]))
print("פיזור דירוג הנכונה (ארוכה/שנייה/שלישית/קצרה):", rk)
