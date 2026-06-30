"""Minimal SRT parse/format. A cue = {start_ms, end_ms, text}."""
import re

_TS = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _ms(h, m, s, ms):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse(path):
    cues = []
    blocks = re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip())
    for b in blocks:
        lines = [l for l in b.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        tl = next((l for l in lines if "-->" in l), None)
        if not tl:
            continue
        m = _TS.search(tl)
        if not m:
            continue
        g = m.groups()
        ti = lines.index(tl)
        text = " ".join(x.strip() for x in lines[ti + 1:] if x.strip())
        cues.append({"start_ms": _ms(*g[:4]), "end_ms": _ms(*g[4:]), "text": text})
    return cues


def fmt_ts(ms):
    ms = max(0, int(round(ms)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def dump(cues, path):
    out = []
    for i, c in enumerate(cues, 1):
        out += [str(i), f"{fmt_ts(c['start_ms'])} --> {fmt_ts(c['end_ms'])}", c["text"], ""]
    open(path, "w", encoding="utf-8").write("\n".join(out).rstrip() + "\n")
