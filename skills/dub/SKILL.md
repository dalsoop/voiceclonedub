---
description: Dub a video into another language in the user's own voice with subtitle-accurate timing, then report the deterministic quality scorecard. Use when the user asks to dub, translate, or re-voice a video (e.g. "dub this lecture into English", "make a Japanese version of this clip in my voice", "re-voice video.mp4 to en,zh").
---

# VoiceCloneDub — dub a video and report the quality scorecard

Run the bundled `voiceclonedub` engine **once** and report exactly what it produced. The engine is
the single source of truth at `${CLAUDE_PLUGIN_ROOT}/src/voiceclonedub`; this skill orchestrates it
and reads its quality record — it does not reimplement transcription, translation, sync, or gating,
and it does **not** loop on its own.

## 0. Preflight — always first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"
```

`ffmpeg`, `ffprobe`, and Python ≥ 3.10 are **required** — if any is missing, give the user the
one-line fix the doctor prints and stop. Backend rows (translate / judge / stt / tts) only block
the stages you use: local STT needs `pip install faster-whisper`; TTS needs `[tts] endpoint` set
to a self-hosted VoxCPM / OpenAI-compatible server (see `voiceclonedub.example.toml`).

## 1. Gather inputs

- **video** (required) — path to the source file.
- **`--to`** — target language(s), comma-separated (`en`, or `en,ja,zh`).
- **`--from`** — source language (optional; auto-detected if omitted — but passing it improves STT).
- **`--voice`** — 5–15 s of clean reference audio of the target speaker (optional, recommended).

## 2. Run the engine (single pass)

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/src" python3 -m voiceclonedub.cli \
  "<video>" --to <langs> [--from <src>] [--voice <ref.wav>] --out out
```

The **translation** stage still self-corrects internally — it re-translates empty lines and any line
the fidelity judge flags for dropped/flipped meaning (negation, number, entity, clause). There is no
synth refit loop: over-long lines are compressed/trimmed deterministically in this one pass.

## 3. Read the gate record

For each target language, read the JSON next to the output video:
`out/<video-stem>/<lang>-<stamp>.json`. The decisive field is **`ok`**. The `gates` object holds:

- **hard gates**: `empty`, `overlap`, `too_fast`, `word_trimmed`, `drift_max` (≤ 0.5),
  `coverage` (≥ 0.85), `loudness.ok`, `artifact.ok`
- **informational**: `fidelity_errors`, `neg_warn_info`, `big_gap_info`, `coverage_miss`

## 4. Report — no auto-loop

- `ok: true` → report the output path and a one-line gate summary
  (`coverage / drift / too_fast / fidelity_errors`).
- `ok: false` → report **exactly which gate(s) failed and what they mean**, and offer the relevant
  manual adjustment the user can make before re-running (do not silently re-run):

| Failed gate | What it means → what to adjust |
|---|---|
| `too_fast` / `overlap` / `word_trimmed` | the target line is longer than its time slot — lower `[merge] max_chars` (shorter segments) or raise `[align] max_compress` in `voiceclonedub.toml`, or shorten the source line |
| `coverage` < 0.85 | some synthesized lines weren't transcribed back (see `coverage_miss`) — usually a voice/TTS quality issue; check `--voice` and the `[tts]` endpoint |
| `fidelity_errors` / `neg_warn_info` | a meaning error the engine couldn't auto-fix — surface the specific line for a human call |
| `loudness.ok` / `artifact.ok` false | run the doctor (TTS level / ffmpeg / disk) |

**Never report success unless the record's `ok` is `true`.**

## Notes

- 100% local — nothing is uploaded. Output is versioned (`<lang>-<timestamp>.mp4`); nothing is
  overwritten, and every render drops its gate record beside it.
- For multiple languages, run them in one invocation (`--to en,ja,zh`) and check each record.
