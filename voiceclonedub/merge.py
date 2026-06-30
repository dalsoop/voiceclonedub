"""Merge raw STT cues into sentence-level segments + drop Whisper repetition
hallucinations. Larger time windows = translations fit without over-compression;
de-duplication prevents the "same line spoken twice / two overlapping voices" artifact.
"""
import re
import difflib

SENT_END = re.compile(r"[.!?。！？…]['\"”’)]?\s*$")


def _ends_sentence(t):
    return bool(SENT_END.search((t or "").strip()))


def _norm(t):
    return re.sub(r"[\s.,!?。！？…'\"”’)(]+", "", (t or "")).lower()


def _collapse_rep(t):
    """Collapse immediate intra-cue repetition: 'A. A. A.' -> 'A.'"""
    parts = re.split(r"(?<=[.!?。！？…])\s+", (t or "").strip())
    if len(parts) <= 1:
        return t
    res = []
    for p in parts:
        if res and _norm(p) and _norm(p) == _norm(res[-1]):
            continue
        res.append(p)
    return " ".join(res)


def clean_cues(cues):
    """Drop adjacent near-duplicate cues (hallucination) + collapse intra-cue repeats.
    Conservative: emphasis repeats (different wording / large gap) are kept (sim>=0.90)."""
    out = []
    for c in cues:
        n = _norm(c["text"])
        if not n:
            continue
        if out:
            pn = _norm(out[-1]["text"])
            sim = difflib.SequenceMatcher(None, pn, n).ratio()
            contained = len(n) >= 5 and (n in pn or pn in n)
            if sim >= 0.90 or contained:
                if c["end_ms"] > out[-1]["end_ms"]:
                    out[-1]["end_ms"] = c["end_ms"]
                continue
        d = dict(c)
        d["text"] = _collapse_rep(d["text"])
        out.append(d)
    return out


def merge(cues, break_gap=0.35, hard_gap=0.6, max_dur=4.5, max_chars=70, min_dur=1.2):
    """Group cleaned cues into sentence/utterance segments.
    Segment start = first cue start, end = last cue end (preserves original timing)."""
    cues = clean_cues(cues)
    if not cues:
        return []

    segs, cur = [], [cues[0]]
    for i in range(1, len(cues)):
        prev, c = cues[i - 1], cues[i]
        gap = (c["start_ms"] - prev["end_ms"]) / 1000.0
        seg_dur = (prev["end_ms"] - cur[0]["start_ms"]) / 1000.0
        seg_chars = sum(len(x["text"]) for x in cur)
        brk = (gap >= hard_gap
               or (_ends_sentence(prev["text"]) and gap >= break_gap)
               or seg_dur >= max_dur or seg_chars >= max_chars)
        if brk:
            segs.append(cur)
            cur = [c]
        else:
            cur.append(c)
    segs.append(cur)

    # Absorb sub-min_dur orphan segments into a neighbor (prepend to next / append to prev).
    def d(g):
        return (g[-1]["end_ms"] - g[0]["start_ms"]) / 1000.0
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for j in range(len(segs)):
            if d(segs[j]) >= min_dur:
                continue
            if j == len(segs) - 1:
                segs[j - 1].extend(segs.pop(j))
            elif j == 0:
                g = segs.pop(0)
                segs[0] = g + segs[0]
            else:
                if d(segs[j - 1]) <= d(segs[j + 1]):
                    segs[j - 1].extend(segs.pop(j))
                else:
                    g = segs.pop(j)
                    segs[j] = g + segs[j]
            changed = True
            break

    out = []
    for group in segs:
        text = " ".join(x["text"].strip() for x in group if x["text"].strip())
        out.append({"start_ms": group[0]["start_ms"], "end_ms": group[-1]["end_ms"], "text": text})
    return out
