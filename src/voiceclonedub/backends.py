"""Pluggable backends for each stage. Everything speaks OpenAI-compatible HTTP where it
can (so Ollama / vLLM / llama.cpp / your own server all work), with local fallbacks.

  translate : per-line, translation-specialist model (TranslateGemma by default)
  judge     : independent fidelity check (any small instruct LLM)
  stt       : faster-whisper (local) or OpenAI-compatible /audio/transcriptions
  tts       : OpenAI-compatible /audio/speech (self-hosted VoxCPM etc.) or local voxcpm
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any

LANG = {
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}


def lang_name(code: str) -> str:
    return LANG.get(code, code)


# ---------------------------------------------------------------- HTTP helpers
def _post_json(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
    retries: int = 3,
) -> dict:
    data = json.dumps(payload).encode()
    hdr = {"Content-Type": "application/json"}
    hdr.update(headers or {})
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdr)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"POST {url} failed: {last}")


def _chat(cfg: dict, messages: list[dict], temperature: float = 0.2, max_tokens: int = 2048) -> str:
    url = cfg["endpoint"].rstrip("/") + "/chat/completions"
    headers = {}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    r = _post_json(
        url,
        {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        headers,
    )
    return r["choices"][0]["message"]["content"]


# ---------------------------------------------------------------- translate
_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[぀-ヿ]")


def _clean(out: str) -> str:
    lines = [
        ln.strip().strip('"').strip("'").strip()
        for ln in (out or "").strip().splitlines()
        if ln.strip()
    ]
    lines = [
        ln for ln in lines if not re.match(r"(?i)^(okay|sure|here'?s|here is|translation)\b", ln)
    ]
    return (lines[-1] if lines else (out or "")).strip().strip('"').strip()


def _wrong_script(t: str, tgt: str) -> bool:
    """CJK target came back in the wrong script (some models echo Korean for colloquial
    KO->JA). Best-effort, CJK targets only."""
    if not t:
        return True
    if tgt == "ja":
        return bool(_HANGUL.search(t))  # Japanese has no Hangul — any = mixed/untranslated
    if tgt == "zh":
        return bool(_HANGUL.search(t) or _KANA.search(t))  # should be pure Han
    if tgt == "ko":
        return not _HANGUL.search(t)
    return False


def _tg(
    cfg: dict, text: str, src_name: str, tgt: str, concise: bool = False, force: bool = False
) -> str:
    instr = (
        f"Translate the following {src_name} sentence into natural {lang_name(tgt)}. "
        "Preserve the meaning exactly — keep every negation, number, name, and nuance; "
        "do NOT add words, fillers, or commentary not in the source. "
        + ("Be as concise as you can while keeping all meaning. " if concise else "")
        + (f"Your ENTIRE output MUST be in {lang_name(tgt)}, never {src_name}. " if force else "")
        + "Output ONLY the translation, nothing else."
    )
    return _clean(
        _chat(
            cfg,
            [{"role": "user", "content": f"{instr}\n{text}"}],
            temperature=0.4 if force else 0.0,
        )
    )


def translate_line(
    cfg: dict, text: str, tgt: str, concise: bool = False, src: str | None = None
) -> str:
    """Per line (most accurate). If a CJK target comes back in the wrong script, retry
    forced, then pivot through English (well-resourced) as a fallback."""
    src_name = lang_name(src) if src else "given"
    t = _tg(cfg, text, src_name, tgt, concise)
    if not _wrong_script(t, tgt):
        return t
    t = _tg(cfg, text, src_name, tgt, concise, force=True)
    if not _wrong_script(t, tgt) or tgt == "en":
        return t
    en = _tg(cfg, text, src_name, "en")  # pivot via English
    t2 = _tg(cfg, en, "English", tgt, concise)
    return t2 if not _wrong_script(t2, tgt) else t


# ---------------------------------------------------------------- fidelity judge
KO_NEG = re.compile(
    r"(맙시다|맙시|마세요|마라|말자|말아|지\s*마|안\s|안돼|안 ?됐|안 ?돼|못\s|못해|못했|없다|없어|없습|없고|없는|없을|없으|지\s*않|지않)"
)
TGT_NEG = re.compile(
    r"(\bnot\b|n[’']?t\b|\bno\b|\bnever\b|\bnone\b|\bnor\b|\bcannot\b|\bwithout\b|\bunable\b)", re.I
)


def neg_warn(segs: list[dict], texts: dict[int, str], src: str = "ko") -> list[int]:
    """Deterministic backstop: source has a negation marker but target has no negation word.
    May over-flag (implicit negation) — informational only."""
    if src != "ko":
        return []
    out: list[int] = []
    for i in range(1, len(segs) + 1):
        if KO_NEG.search(segs[i - 1]["text"]) and not TGT_NEG.search(texts.get(i, "")):
            out.append(i)
    return out


def judge_fidelity(cfg: dict, segs: list[dict], texts: dict[int, str], tgt: str) -> list[int]:
    """Independent CoT judge: per line, paraphrase source -> target -> SAME/ERROR.
    Returns list of 1-based indices the judge marked ERROR (meaning errors only)."""
    rows = "\n".join(
        f"{i}. SRC: {segs[i - 1]['text']}\n   {lang_name(tgt)}: {texts.get(i, '')}"
        for i in range(1, len(segs) + 1)
    )
    sysmsg = (
        f"You verify translation fidelity into {lang_name(tgt)} (you do NOT translate; you judge). "
        "For EACH numbered line reason briefly: SRC_meaning (watch negation, numbers, names), "
        "TGT_says, verdict SAME or ERROR. Mark ERROR only for a real meaning error: negation "
        "flipped/dropped, wrong/missing number, wrong/dropped entity, omitted clause, or "
        "mistranslation — NOT for style, brevity, or tone. End with exactly one line: "
        "FLAGS=[comma-separated line numbers that are ERROR] (FLAGS=[] if all SAME)."
    )
    try:
        out = _chat(
            cfg,
            [{"role": "system", "content": sysmsg}, {"role": "user", "content": rows}],
            temperature=0.0,
            max_tokens=4000,
        )
        m = re.search(r"FLAGS\s*=\s*\[([0-9,\s]*)\]", out)
        if not m:
            return []
        return [int(x) for x in re.findall(r"\d+", m.group(1)) if 1 <= int(x) <= len(segs)]
    except Exception:
        return []


# ---------------------------------------------------------------- STT
def transcribe(cfg: dict, audio_path: str, language: str | None = None) -> list[dict]:
    """Return cues [{start_ms,end_ms,text}]. faster-whisper local, or OpenAI-compatible."""
    backend = cfg.get("backend", "faster-whisper")
    if backend == "faster-whisper":
        from faster_whisper import WhisperModel  # lazy import

        device = cfg.get("device", "auto")
        model = WhisperModel(
            cfg.get("model", "large-v3"),
            device=("cpu" if device == "cpu" else "auto"),
            compute_type="int8" if device == "cpu" else "auto",
        )
        segments, _ = model.transcribe(audio_path, language=language, word_timestamps=False)
        return [
            {"start_ms": int(s.start * 1000), "end_ms": int(s.end * 1000), "text": s.text.strip()}
            for s in segments
            if s.text.strip()
        ]
    # OpenAI-compatible /audio/transcriptions (multipart) -> verbose_json segments
    raise NotImplementedError(
        "stt.backend='openai' endpoint transcription not wired in v0.1; "
        "use 'faster-whisper' or open an issue."
    )


# ---------------------------------------------------------------- TTS
def tts(cfg: dict, text: str, out_bytes_path: str, voice_ref: str | None = None) -> str:
    """Synthesize `text` in the target voice -> write audio bytes to out_bytes_path.
    Default path: OpenAI-compatible /audio/speech POST to a self-hosted endpoint."""
    endpoint = cfg.get("endpoint", "")
    if not endpoint:
        raise RuntimeError(
            "tts.endpoint is empty. Point it at a self-hosted VoxCPM / OpenAI-compatible "
            "TTS server (see voiceclonedub.example.toml). Local in-process VoxCPM is on the roadmap."
        )
    body: dict[str, Any] = {
        "input": text,
        "model": cfg.get("model", "voxcpm"),
        "cfg_value": cfg.get("cfg", 1.9),
        "inference_timesteps": cfg.get("steps", 40),
    }
    if voice_ref:
        body["voice_ref"] = voice_ref
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/audio/speech", data=data, headers=headers
    )
    audio = urllib.request.urlopen(req, timeout=180).read()
    with open(out_bytes_path, "wb") as f:
        f.write(audio)
    return out_bytes_path
