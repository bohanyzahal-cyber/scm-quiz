# -*- coding: utf-8 -*-
# מציג את השאלות שבהן התשובה הנכונה היא הארוכה ביותר (גם בתו אחד), לצורך איזון
import sys, io, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("d", sys.argv[1]); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
n = 0
for i, it in enumerate(D.Q):
    la = len(it["a"]); ld = [len(x) for x in it["d"]]
    if la >= max(ld):
        n += 1
        j = ld.index(max(ld))
        print("#%d  נכונה %d | הארוך מהמסיחים %d: %s" % (i, la, max(ld), it["d"][j]))
print("סה״כ נכונה-ארוכה: %d מתוך %d" % (n, len(D.Q)))
