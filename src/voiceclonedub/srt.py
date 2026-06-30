"""Minimal SRT parse/format. A cue = {start_ms, end_ms, text}."""

from __future__ import annotations

import re

_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse(path: str) -> list[dict]:
    cues: list[dict] = []
    with open(path, encoding="utf-8") as f:
        blocks = re.split(r"\n\s*\n", f.read().strip())
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        tl = next((ln for ln in lines if "-->" in ln), None)
        if not tl:
            continue
        m = _TS.search(tl)
        if not m:
            continue
        g = m.groups()
        ti = lines.index(tl)
        text = " ".join(x.strip() for x in lines[ti + 1 :] if x.strip())
        cues.append({"start_ms": _ms(*g[:4]), "end_ms": _ms(*g[4:]), "text": text})
    return cues


def fmt_ts(ms: float) -> str:
    ms = max(0, round(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def dump(cues: list[dict], path: str) -> None:
    out: list[str] = []
    for i, c in enumerate(cues, 1):
        out += [str(i), f"{fmt_ts(c['start_ms'])} --> {fmt_ts(c['end_ms'])}", c["text"], ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")
