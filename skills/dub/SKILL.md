---
description: Dub a video into another language in the user's own voice with subtitle-accurate timing, looping until every deterministic quality gate passes. Use when the user asks to dub, translate, or re-voice a video (e.g. "dub this lecture into English", "make a Japanese version of this clip in my voice", "re-voice video.mp4 to en,zh").
---

# VoiceCloneDub — dub a video, loop until the quality gates pass

Drive the bundled `voiceclonedub` engine as an agent loop: **generate a dub → read its
deterministic quality scorecard → fix only what failed → repeat** until the run record reports
`ok: true`, or until the sensible fixes are exhausted (then report honestly which gate is stuck).

The engine is the single source of truth at `${CLAUDE_PLUGIN_ROOT}/src/voiceclonedub`. This skill
orchestrates it — it does not reimplement transcription, translation, sync, or gating.

## 0. Preflight — always first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

`ffmpeg`, `ffprobe`, and Python ≥ 3.10 are **required** — if any is missing, tell the user the
one-line fix the doctor prints and stop. Backend rows (translate / judge / stt / tts) only block
the stages you use: local STT needs `pip install faster-whisper`; TTS needs `[tts] endpoint` set
to a self-hosted VoxCPM / OpenAI-compatible server (see `voiceclonedub.example.toml`).

## 1. Gather inputs

- **video** (required) — path to the source file.
- **`--to`** — target language(s), comma-separated (`en`, or `en,ja,zh`).
- **`--from`** — source language (optional; auto-detected if omitted).
- **`--voice`** — 5–15 s of clean reference audio of the target speaker (the cleaner, the closer
  the clone). Optional but strongly recommended.

## 2. Run the engine

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/src" python3 -m voiceclonedub.cli \
  "<video>" --to <langs> [--from <src>] [--voice <ref.wav>] --rounds 3 --out out
```

The engine already loops internally (`--rounds`): it re-translates fidelity/negation failures and
re-tightens too-fast / overlapping lines, re-synthesizing **only changed segments** (cached), so
re-runs are cheap.

## 3. Observe — read the gate record

For each target language, read the JSON written next to the output video:
`out/<video-stem>/<lang>-<stamp>.json`. The decisive field is **`ok`**. The `gates` object holds:

- **hard gates** (all must pass): `empty`, `overlap`, `too_fast`, `word_trimmed`,
  `drift_max` (≤ 0.5), `coverage` (≥ 0.85), `loudness.ok`, `artifact.ok`
- **informational**: `fidelity_errors`, `neg_warn_info`, `big_gap_info`, `coverage_miss`

## 4. Act — fix only what failed, then loop back to step 2

If `ok: true` → **done** (go to step 5). If `ok: false`, diagnose by the failed gate and take the
matching action, then re-run:

| Failed gate | Likely cause | Action |
|---|---|---|
| `too_fast` / `overlap` / `word_trimmed` (persist after rounds) | target line too long for its time slot | raise `--rounds`; if still stuck, lower `[merge] max_chars` (shorter segments) or raise `[align] max_compress`; as a last resort shorten the offending line's wording and say so |
| `coverage` < 0.85 | a synthesized line wasn't transcribed back | inspect `coverage_miss` indices — usually a TTS/voice issue; check `--voice` quality and the `[tts]` endpoint |
| `fidelity_errors` / `neg_warn_info` persist | translation dropped or flipped meaning (negation, number, entity, clause) | the engine already retries these; if a specific line stays wrong, surface that line to the user for a human call — do not paper over a meaning error |
| `loudness.ok` false | clipping or near-silence in the mix | run the doctor; check the TTS output level |
| `artifact.ok` false | mux / ffmpeg failure | run the doctor; check ffmpeg and free disk |
| `empty` non-empty | a line failed to translate at all | re-run; if it persists, the translate endpoint is failing (doctor) |

**Stop looping** when every hard gate is green, **or** when you have applied the sensible
adjustments and a gate still fails — then report exactly which segment(s) and gate are stuck and
why. Never keep looping blindly.

## 5. Report

State the output path(s), the `ok` status, and a one-line gate summary
(`coverage / drift / too_fast / fidelity_errors`). **Never report success unless the record's
`ok` is `true`.** If you changed any flag or config value to get there, say what you changed.

## Notes

- 100% local — nothing is uploaded. Output is versioned (`<lang>-<timestamp>.mp4`); nothing is
  overwritten, and every render drops its gate record beside it.
- For multiple languages, run them in one invocation (`--to en,ja,zh`) and check each record.
