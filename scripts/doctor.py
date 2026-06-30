#!/usr/bin/env python3
"""VoiceCloneDub environment doctor — checks deps + backend reachability. Standard library only.

Run directly (`python3 scripts/doctor.py`) or via the plugin skill. Exits non-zero only when a
HARD dependency (ffmpeg / ffprobe / Python 3.10+) is missing; per-stage backends are advisory."""

from __future__ import annotations

import os
import shutil
import socket
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

OK, WARN, BAD = "✓", "⚠", "✗"  # check / warn / cross


def _mark(state: bool | None) -> str:
    return OK if state is True else (WARN if state is None else BAD)


def _check(label: str, state: bool | None, hint: str = "") -> bool | None:
    print(f"  {_mark(state)} {label}")
    if state is not True and hint:
        print(f"      -> {hint}")
    return state


def _reachable(url: str, timeout: float = 2.0) -> bool:
    try:
        u = urlparse(url if "://" in url else "http://" + url)
        host = u.hostname or "localhost"
        port = u.port or (443 if u.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    print("VoiceCloneDub doctor\n")

    print("Core (required):")
    py_ok = sys.version_info >= (3, 10)
    ff_ok = shutil.which("ffmpeg") is not None
    fp_ok = shutil.which("ffprobe") is not None
    _check(
        f"python {sys.version_info.major}.{sys.version_info.minor} (>=3.10)",
        py_ok,
        "install Python 3.10+",
    )
    _check("ffmpeg on PATH", ff_ok, "brew install ffmpeg   |   apt-get install ffmpeg")
    _check("ffprobe on PATH", fp_ok, "ships with ffmpeg")
    hard_ok = py_ok and ff_ok and fp_ok

    try:
        from voiceclonedub import config as _cfg

        _check("voiceclonedub engine importable", True)
        cfg = _cfg.load()
    except Exception as e:
        _check("voiceclonedub engine importable", False, f"bundled package not found: {e}")
        return 1

    print("\nBackends (only the stages you actually use need to be green):")
    stt = cfg["stt"]
    if stt.get("backend") == "faster-whisper":
        try:
            import faster_whisper  # noqa: F401

            _check("stt: faster-whisper installed", True)
        except ImportError:
            _check(
                "stt: faster-whisper",
                None,
                "pip install faster-whisper   (or set [stt] to an OpenAI-compatible endpoint)",
            )
    else:
        ep = stt.get("endpoint", "")
        _check(
            f"stt endpoint: {ep or '(unset)'}",
            _reachable(ep) if ep else None,
            "set [stt] endpoint to a reachable /audio/transcriptions server",
        )

    for name in ("translate", "judge"):
        ep = cfg[name].get("endpoint", "")
        model = cfg[name].get("model", "?")
        _check(
            f"{name}: {model} @ {ep or '(unset)'}",
            _reachable(ep) if ep else None,
            f"start the server, e.g. `ollama serve` + `ollama pull {model}`",
        )

    tep = cfg["tts"].get("endpoint", "")
    _check(
        f"tts endpoint: {tep or '(unset)'}",
        _reachable(tep) if tep else None,
        "point [tts] endpoint at a self-hosted VoxCPM / OpenAI-compatible /audio/speech server",
    )

    print()
    if not hard_ok:
        print(f"{BAD} hard dependencies missing (ffmpeg / ffprobe / python). Fix those first.")
        return 1
    print(f"{OK} core ready. Items marked {WARN}/{BAD} only block the stages that use them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
