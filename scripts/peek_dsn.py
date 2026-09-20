import re

p = r"C:\Users\aicoe\Desktop\Sigrity\runs\schematic_gen_test\Fault-Detector\FAULT-DETECTOR.DSN"
data = open(p, "rb").read()
print("size:", len(data))
for pattern in [b"Schematic", b"PAGE", b"Page", b"Detector-Dsn", b"PAGE1", b"SCHEMATIC"]:
    idx = 0
    hits = []
    while True:
        i = data.find(pattern, idx)
        if i < 0:
            break
        hits.append(i)
        idx = i + 1
        if len(hits) >= 5:
            break
    print(pattern, "hits:", hits)
# Show first Schematic hit context, non-printables as dots
i = data.find(b"Schematic")
if i >= 0:
    ctx = data[max(0, i - 120) : i + 200]
    cleaned = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
    print("context:", cleaned)
# Also utf-16 decode attempt for a slice
u16 = data[:20000].decode("utf-16-le", errors="ignore")
for pat in ("Schematic", "PAGE"):
    j = u16.find(pat)
    if j >= 0:
        print("utf16", pat, repr(u16[max(0, j - 80) : j + 120]))
