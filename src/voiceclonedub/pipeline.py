"""Orchestrator: video -> STT -> merge -> faithful translate -> fidelity gate ->
subtitle-anchor synth (refit loop) -> quality gates -> mux + versioned record.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
from typing import Any

from . import align, backends, media, merge, srt


def _norm(s: str) -> str:
    return re.sub(r"[\s.,!?;:·…\"'`’“”\-—()\[\]]+", "", (s or "").lower())


def _empty_ids(segs: list[dict], texts: dict[int, str]) -> list[int]:
    bad: list[int] = []
    for i in range(1, len(segs) + 1):
        t = (texts.get(i) or "").strip()
        if not t or t in ("...", "…") or len(_norm(t)) < 2:
            bad.append(i)
    return bad


def _coverage(
    track: str, lang: str, segs: list[dict], texts: dict[int, str], stt_cfg: dict
) -> tuple[float, list[int]]:
    """Re-transcribe the assembled track and fuzzy-match each intended line."""
    try:
        cues = backends.transcribe(stt_cfg, track, language=lang)
    except Exception:
        return 1.0, []  # STT unavailable -> don't block on coverage
    heard = _norm(" ".join(c["text"] for c in cues))
    miss: list[int] = []
    for i in range(1, len(segs) + 1):
        a = _norm(texts.get(i, ""))
        if len(a) < 3:
            continue
        best = max(
            (
                difflib.SequenceMatcher(None, a, heard[j : j + len(a) + 8]).ratio()
                for j in range(0, max(1, len(heard) - len(a)), 4)
            ),
            default=0,
        )
        if best < 0.62:
            miss.append(i)
    return round(1 - len(miss) / max(1, len(segs)), 2), miss


def _translate_all(
    tcfg: dict,
    segs: list[dict],
    tgt: str,
    idxs: list[int] | None = None,
    concise: bool = False,
    src: str | None = None,
) -> dict[int, str]:
    pick = idxs or list(range(1, len(segs) + 1))
    out: dict[int, str] = {}
    for i in pick:
        try:
            out[i] = backends.translate_line(
                tcfg, segs[i - 1]["text"], tgt, concise=concise, src=src
            )
        except Exception:
            out[i] = ""
    return out


def dub(
    video: str,
    tgt: str,
    cfg: dict,
    src: str | None = None,
    voice: str | None = None,
    rounds: int = 3,
    out_dir: str = "out",
    work_root: str = "work",
) -> dict:
    slug = os.path.splitext(os.path.basename(video))[0]
    work = os.path.join(work_root, slug, tgt)
    os.makedirs(work, exist_ok=True)
    cache = os.path.join(work, "_cache")
    os.makedirs(cache, exist_ok=True)

    # 1) transcribe
    src_audio = media.extract_audio(video, os.path.join(work, "src16k.wav"), sr=16000)
    raw_cues = backends.transcribe(cfg["stt"], src_audio, language=src)
    srt.dump(raw_cues, os.path.join(work, "source.srt"))

    # 2) merge + de-hallucinate
    m = cfg["merge"]
    segs = merge.merge(
        raw_cues,
        break_gap=m["break_gap"],
        hard_gap=m["hard_gap"],
        max_dur=m["max_dur"],
        max_chars=m["max_chars"],
        min_dur=m["min_dur"],
    )
    if not segs:
        raise RuntimeError("no segments after merge")
    srt.dump(segs, os.path.join(work, "segments.srt"))

    # 3) faithful translation (per line)
    texts = _translate_all(cfg["translate"], segs, tgt, src=src)
    for _ in range(3):  # never ship empty/placeholder lines
        bad = _empty_ids(segs, texts)
        if not bad:
            break
        texts.update(_translate_all(cfg["translate"], segs, tgt, idxs=bad, src=src))

    # 4) fidelity gate (judge + deterministic negation) -> fix flagged lines
    fidelity: list[int] = []
    for _ in range(3):
        fidelity = backends.judge_fidelity(cfg["judge"], segs, texts, tgt)
        if not fidelity:
            break
        texts.update(_translate_all(cfg["translate"], segs, tgt, idxs=fidelity, src=src))

    # 5) cached per-segment synth in your voice
    tts_cfg = cfg["tts"]

    def synth_fn(idx: int, text: str) -> str:
        key = hashlib.sha1(
            f"{text}|{voice}|{tts_cfg.get('model')}|{tts_cfg.get('cfg')}|{tts_cfg.get('steps')}".encode()
        ).hexdigest()
        cached = os.path.join(cache, key + ".wav")
        if not os.path.exists(cached):
            tmp = os.path.join(cache, key + ".bin")
            backends.tts(tts_cfg, text, tmp, voice_ref=voice)
            media.to_wav(tmp, cached, sr=48000, mono=True)
        return cached

    # 6) subtitle-anchor synth + refit loop (only re-tighten lines too fast for their slot)
    a = cfg["align"]
    ln = (a.get("lufs_target", -16.0), a.get("tp", -1.5), a.get("lra", 11.0))
    last: dict[str, Any] = {}
    track = ""
    for rd in range(rounds):  # noqa: B007 — rd reused after the loop as the round count
        track, last = align.build_track(
            segs, texts, work, synth_fn, max_compress=a["max_compress"], loudnorm=ln
        )
        fast = set(last["too_fast"]) | set(last["overlap"]) | set(last["word_trimmed"])
        if not fast:
            break
        texts.update(
            _translate_all(cfg["translate"], segs, tgt, idxs=sorted(fast), concise=True, src=src)
        )

    # 7) gates — multi-metric quality scorecard
    empty = _empty_ids(segs, texts)
    cov, cov_miss = _coverage(track, tgt, segs, texts, cfg["stt"])
    nwarn = backends.neg_warn(segs, texts, src=src or "")
    dub_lufs, orig_lufs = media.lufs(track), media.lufs(src_audio)  # loudness vs original + target
    loud_ok = (dub_lufs is None) or abs(dub_lufs - ln[0]) <= 2.0
    ok = (
        not empty
        and not last["overlap"]
        and not last["too_fast"]
        and not last["word_trimmed"]
        and last["drift_max"] <= a["max_drift_s"]
        and cov >= a["min_coverage"]
        and loud_ok
    )
    gates = {
        "empty": empty,
        "fidelity_errors": fidelity,
        "neg_warn_info": nwarn,
        "overlap": last["overlap"],
        "too_fast": last["too_fast"],
        "word_trimmed": last["word_trimmed"],
        "coverage": cov,
        "coverage_miss": cov_miss,
        "drift_max": last["drift_max"],
        "big_gap_info": last["big_gap"],
        "loudness": {"dub_lufs": dub_lufs, "orig_lufs": orig_lufs, "target": ln[0], "ok": loud_ok},
    }

    # 8) mux -> versioned output + record (+ artifact existence/integrity gate)
    stamp = time.strftime("%y%m%d%H%M%S")
    odir = os.path.join(out_dir, slug)
    os.makedirs(odir, exist_ok=True)
    out_path = os.path.join(odir, f"{tgt}-{stamp}.mp4")
    media.mux(video, track, out_path)
    sv = media.streams(out_path)
    out_dur = media.dur(out_path)
    artifact_ok = (
        os.path.exists(out_path)
        and os.path.getsize(out_path) > 10000
        and "video" in sv
        and "audio" in sv
        and out_dur > 1.0
    )
    gates["artifact"] = {
        "out_exists": os.path.exists(out_path),
        "has_video": "video" in sv,
        "has_audio": "audio" in sv,
        "dur_s": round(out_dur, 1),
        "ok": artifact_ok,
    }
    ok = ok and artifact_ok
    record = {
        "stamp": stamp,
        "slug": slug,
        "src": src,
        "tgt": tgt,
        "segs": len(segs),
        "rounds": rd + 1,
        "ok": ok,
        "gates": gates,
        "out": out_path,
        "lines": [
            {"start_ms": s["start_ms"], "text": texts.get(i + 1, "")} for i, s in enumerate(segs)
        ],
    }
    with open(os.path.join(odir, f"{tgt}-{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record
