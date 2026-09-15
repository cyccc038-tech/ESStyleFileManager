#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: strip_nonfree.py <MaterialFiles source dir>")

root = Path(sys.argv[1]).resolve()
app = root / "app"

# Material Files marks Google/Firebase-only code with //#ifdef NONFREE ... //#endif.
# For this privacy-oriented derivative build we remove those marked blocks instead of
# reusing the upstream Firebase project/API configuration.
for path in [app / "build.gradle"] + list((app / "src/main/java").rglob("*.kt")) + list((app / "src/main/java").rglob("*.java")):
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    text2 = re.sub(r"^[ \t]*//#ifdef NONFREE\s*\n.*?^[ \t]*//#endif\s*\n?", "", text, flags=re.M | re.S)
    if text2 != text:
        path.write_text(text2, encoding="utf-8")

# The only upstream source package that directly imports Firebase is nonfree; remove it
# entirely after its callers have been stripped above.
nonfree = app / "src/main/java/me/zhanghai/android/files/nonfree"
if nonfree.exists():
    shutil.rmtree(nonfree)

print("Removed NONFREE/Firebase code from derivative build")
