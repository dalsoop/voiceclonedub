"""ffmpeg/ffprobe helpers. ffmpeg must be on PATH."""

from __future__ import annotations

import re
import subprocess


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def dur(path: str) -> float:
    r = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            path,
        ]
    )
    try:
        return float((r.stdout or "0").strip() or 0)
    except ValueError:
        return 0.0


def lufs(path: str) -> float | None:
    """Integrated loudness (EBU R128) in LUFS, or None. Speech-gated."""
    r = _run(["ffmpeg", "-nostdin", "-i", path, "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    mm = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", (r.stderr or ""))
    try:
        return float(mm[-1]) if mm else None
    except ValueError:
        return None


def peak(path: str) -> float | None:
    """Maximum sample peak in dBFS (via volumedetect), or None. 0 dBFS == full scale."""
    r = _run(["ffmpeg", "-nostdin", "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    mm = re.findall(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", (r.stderr or ""))
    try:
        return float(mm[-1]) if mm else None
    except ValueError:
        return None


def peak_normalize(
    src: str, dst: str, target_db: float = -1.5, max_gain_db: float = 6.0, sr: int = 48000
) -> str:
    """Transparent peak normalization: measure the track's peak and apply a single linear
    gain so the peak sits at `target_db` dBFS, capping any *boost* at `max_gain_db`.

    Unlike dynamic EBU R128 `loudnorm` (one-pass), this never compresses the signal, so it
    introduces no pumping and does not amplify the noise floor / expose synth texture beyond
    the cap. Attenuation (when the track is already hotter than the target) is uncapped."""
    pk = peak(src)
    gain = 0.0 if pk is None else min(target_db - pk, max_gain_db)
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
            f"volume={gain:.2f}dB,aresample={sr}",
            dst,
        ],
        check=True,
    )
    return dst


def streams(path: str) -> str:
    """Newline-joined codec_type list, e.g. contains 'video' and 'audio'."""
    return (
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=nw=1:nk=1",
                path,
            ]
        ).stdout
        or ""
    )


def extract_audio(video: str, out_wav: str, sr: int = 16000, mono: bool = True) -> str:
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", video, "-vn"]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr), "-c:a", "pcm_s16le", out_wav]
    subprocess.run(cmd, check=True)
    return out_wav


def to_wav(
    src: str, out_wav: str, sr: int = 48000, mono: bool = True, af: str | None = None
) -> str:
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr)]
    if af:
        cmd += ["-af", af]
    cmd += [out_wav]
    subprocess.run(cmd, check=True)
    return out_wav


def mux(video: str, audio: str, out: str, vcopy: bool = True) -> str:
    """Replace the video's audio track with `audio`."""
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video,
        "-i",
        audio,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy" if vcopy else "libx264",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        out,
    ]
    subprocess.run(cmd, check=True)
    return out
