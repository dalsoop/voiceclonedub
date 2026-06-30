"""Subtitle-anchor placement: each translated line is voiced, then placed at the exact
moment it was originally spoken. Short lines leave a natural gap (no stretch = no
sluggishness); over-long lines are gently compressed so they never overlap the next line.
Drift is 0 by construction. Returns the assembled track + a defect report for the gates.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable

from . import media


def _atempo(src: str, dst: str, factor: float) -> str:
    """Speed up (factor>1) without pitch change. ffmpeg atempo supports 0.5..2.0 per stage."""
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src,
            "-af",
            f"atempo={factor:.4f}",
            dst,
        ],
        check=True,
    )
    return dst


def _trim(src: str, dst: str, cut_s: float) -> str:
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src,
            "-af",
            f"atrim=0:{cut_s:.3f},afade=t=out:st={max(0, cut_s - 0.04):.3f}:d=0.04",
            dst,
        ],
        check=True,
    )
    return dst


def build_track(
    segs: list[dict],
    texts: dict[int, str],
    work_dir: str,
    synth_fn: Callable[[int, str], str],
    max_compress: float = 1.45,
    too_fast: float = 1.30,
    peak_db: float = -1.5,
    max_gain_db: float = 6.0,
) -> tuple[str, dict]:
    """segs: [{start_ms,end_ms,text}] (1-based texts dict). synth_fn(idx, text)->wav path.
    Output is peak-normalized to `peak_db` dBFS (boost capped at `max_gain_db`) — transparent,
    no dynamic loudnorm / pumping. Returns (track, report)."""
    os.makedirs(work_dir, exist_ok=True)
    n = len(segs)
    total = max((s["end_ms"] for s in segs), default=0) / 1000.0 + 0.4

    pieces: list[tuple[float, str]] = []
    rep: list[dict] = []
    for i in range(n):
        st = segs[i]["start_ms"] / 1000.0
        nxt = segs[i + 1]["start_ms"] / 1000.0 if i + 1 < n else total
        avail = max(0.0, nxt - st)
        wav = synth_fn(i, texts.get(i + 1, ""))
        d = media.dur(wav)
        out_piece, speed, trim_s = wav, 1.0, 0.0
        if avail > 0 and d > avail:  # over-long -> compress to fit window
            speed = min(max_compress, d / avail)
            if speed > 1.01:
                fit = os.path.join(work_dir, f"f{i}.wav")
                out_piece = _atempo(wav, fit, speed)
        fd = media.dur(out_piece)
        if avail > 0 and fd > avail + 0.005:  # still over -> trim tail (last resort)
            cut = max(0.2, avail - 0.02)
            cw = os.path.join(work_dir, f"t{i}.wav")
            out_piece = _trim(out_piece, cw, cut)
            trim_s = round(fd - media.dur(out_piece), 2)
            fd = media.dur(out_piece)
        pieces.append((st, out_piece))
        rep.append(
            {
                "i": i + 1,
                "start": round(st, 2),
                "avail": round(avail, 2),
                "tts": round(d, 2),
                "final": round(fd, 2),
                "speed": round(speed, 3),
                "trim_s": trim_s,
            }
        )

    # placement: anchor at original start; clamp to >= prev end so audio never overlaps.
    positions: list[float] = []
    placed_gap: list[float] = []
    placed_over: list[float] = []
    drifts: list[float] = []
    prev_end = 0.0
    for k, (st, p) in enumerate(pieces):
        pos = max(prev_end, st) if k else st
        g = pos - prev_end
        placed_gap.append(g if g > 0 else 0.0)
        placed_over.append(0.0)  # clamped: structurally no overlap
        drifts.append(abs(pos - st))
        positions.append(pos)
        prev_end = pos + media.dur(p)

    # assemble: delay each piece to its position, mix down
    inp: list[str] = []
    for _, p in pieces:
        inp += ["-i", p]
    fc = [
        f"[{i}:a]adelay={int(positions[i] * 1000)}|{int(positions[i] * 1000)}[d{i}]"
        for i in range(n)
    ]
    fc.append(
        "".join(f"[d{i}]" for i in range(n))
        + f"amix=inputs={n}:duration=longest:normalize=0,apad,atrim=0:{total:.3f}[o]"
    )
    raw = os.path.join(work_dir, "track_raw.wav")
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *inp,
            "-filter_complex",
            ";".join(fc),
            "-map",
            "[o]",
            "-c:a",
            "pcm_s16le",
            raw,
        ],
        check=True,
    )
    # transparent peak normalization (no dynamic loudnorm -> no pumping / texture exposure)
    track = media.peak_normalize(
        raw, os.path.join(work_dir, "track.wav"), target_db=peak_db, max_gain_db=max_gain_db
    )

    report = {
        "overlap": [i + 1 for i in range(n) if placed_over[i] > 0.02],
        "too_fast": [r["i"] for r in rep if r["speed"] >= too_fast],
        "word_trimmed": [r["i"] for r in rep if r["trim_s"] > 0.05],
        "big_gap": [i + 1 for i in range(n) if placed_gap[i] > 0.9],
        "drift_max": round(max(drifts) if drifts else 0.0, 2),
        "out_peak_db": media.peak(track),
        "cues": rep,
    }
    return track, report
