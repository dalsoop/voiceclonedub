"""Config loading: built-in defaults <- voiceclonedub.toml / ~/.config/voiceclonedub.toml <- env."""

from __future__ import annotations

import os
import sys
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

DEFAULTS: dict[str, dict[str, Any]] = {
    "translate": {
        "backend": "ollama",
        "model": "translategemma:12b",
        "endpoint": "http://localhost:11434/v1",
        "api_key": "",
    },
    "judge": {
        "backend": "ollama",
        "model": "qwen3:8b",
        "endpoint": "http://localhost:11434/v1",
        "api_key": "",
    },
    "stt": {
        "backend": "faster-whisper",
        "model": "large-v3",
        "endpoint": "",
        "api_key": "",
        "device": "auto",
    },
    "tts": {
        "backend": "voxcpm",
        "endpoint": "",
        "api_key": "",
        "cfg": 1.9,
        "steps": 40,
        "takes": 2,
    },
    "align": {
        "gap_cap": 0.0,
        "fill": False,
        "max_compress": 1.45,
        "min_coverage": 0.85,
        "max_drift_s": 0.5,
        "peak_db": -1.5,
        "max_gain_db": 6.0,
    },
    "merge": {"break_gap": 0.35, "hard_gap": 0.6, "max_dur": 4.5, "max_chars": 70, "min_dur": 1.2},
}

_CANDIDATES = ["voiceclonedub.toml", os.path.expanduser("~/.config/voiceclonedub.toml")]


def _deep_merge(base: dict[str, Any], over: dict[str, Any] | None) -> dict[str, Any]:
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def load(path: str | None = None) -> dict[str, Any]:
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    p = path or next((c for c in _CANDIDATES if os.path.exists(c)), None)
    if p and os.path.exists(p):
        with open(p, "rb") as f:
            cfg = _deep_merge(cfg, tomllib.load(f))
    # env overrides: VCDUB_TRANSLATE_ENDPOINT, VCDUB_TTS_BACKEND, ...
    for section in cfg:
        for key in list(cfg[section]):
            env = f"VCDUB_{section.upper()}_{key.upper()}"
            if env in os.environ:
                cfg[section][key] = (
                    type(cfg[section][key])(os.environ[env])
                    if not isinstance(cfg[section][key], bool)
                    else os.environ[env] == "1"
                )
    return cfg
