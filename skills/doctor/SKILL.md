---
description: Check that VoiceCloneDub's dependencies and backends are ready before dubbing — ffmpeg/ffprobe, Python version, and the translate / judge / STT / TTS endpoints. Use before a first dub, or when a dub run fails at setup ("voiceclonedub doctor", "is my dubbing setup ready", "why does dubbing fail to start").
---

# VoiceCloneDub — environment doctor

Run the bundled checker and relay its checklist to the user:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

- **Hard requirements** (block everything): `ffmpeg`, `ffprobe`, Python ≥ 3.10.
- **Per-stage backends** (block only the stage that uses them):
  - `translate` / `judge` — an OpenAI-compatible chat endpoint (default: local Ollama with
    `translategemma:12b` and a small judge model).
  - `stt` — local `faster-whisper` (`pip install faster-whisper`) or an OpenAI-compatible
    `/audio/transcriptions` endpoint.
  - `tts` — a self-hosted VoxCPM / OpenAI-compatible `/audio/speech` endpoint (`[tts] endpoint`).

For every ✗ / ⚠, give the user the one-line fix the script prints. The doctor exits non-zero only
when a hard dependency is missing.
