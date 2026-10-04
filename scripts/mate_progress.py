#!/usr/bin/env python3
"""Apunta altas/cambios hechos en MyHeritage en data/mate_transfer/progress.json.

Uso:  python3 scripts/mate_progress.py new  @I500046@=5501615 @I500047@=5501616 ...
      python3 scripts/mate_progress.py couple 5501634+5501553
      python3 scripts/mate_progress.py upd  @I154@ "BIRT place + nota"
"""
import json, sys, datetime
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "data" / "mate_transfer" / "progress.json"
prog = json.loads(p.read_text())
now = datetime.datetime.now().isoformat(timespec="seconds")
kind, args = sys.argv[1], sys.argv[2:]
if kind == "new":
    for a in args:
        mid, mh = a.split("=")
        gid = "@I" + str(int(mh) - 5000000) + "@"
        prog["new"][mid] = {"godes_id": gid, "done": ["alta"], "at": now}
        prog["log"].append(f"{now} NEW {mid} → {gid}")
elif kind == "couple":
    prog.setdefault("couples", [])
    for a in args:
        x, y = sorted(int(v) for v in a.split("+"))
        if [x, y] not in prog["couples"]:
            prog["couples"].append([x, y])
            prog["log"].append(f"{now} COUPLE {x}+{y}")
elif kind == "upd":
    prog["updates"][args[0]] = {"done": args[1:], "at": now}
    prog["log"].append(f"{now} UPD {args[0]} {' '.join(args[1:])}")
p.write_text(json.dumps(prog, ensure_ascii=False, indent=1))
print(f"altas: {len(prog['new'])} · cambios: {len(prog['updates'])}")
