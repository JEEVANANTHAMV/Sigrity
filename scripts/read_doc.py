import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8", errors="replace")
# strip tags
text = re.sub(r"<script.*?</script>", " ", text, flags=re.DOTALL)
text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL)
text = re.sub(r"<[^>]+>", " ", text)
text = re.sub(r"[ \t]+", " ", text)
lines = [l.strip() for l in text.splitlines() if l.strip()]
print("\n".join(lines))
