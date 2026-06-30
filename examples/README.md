# Examples

Drop a short source video here and dub it — these double as the project's demo assets.

## Layout

```
examples/
  <name>/
    <name>.mp4          # source video (you add this — keep it short: seconds to a few minutes)
    voice.wav           # optional: a 5–15 s reference clip of the speaker's voice
    en-<stamp>.mp4      # result(s) after a run — the dubbed video
    en-<stamp>.json     # the quality-gate record for that render
```

`examples/**` is whitelisted in [`.gitignore`](../.gitignore), so media placed here is committed
even though `*.mp4` is ignored everywhere else. Keep inputs small so the repo stays light.

## Run one

```bash
# CLI
dub examples/lecture-ko/lecture-ko.mp4 --from ko --to en,ja \
    --voice examples/lecture-ko/voice.wav --out examples/lecture-ko

# …or from Claude Code with the plugin installed
#   "dub examples/lecture-ko/lecture-ko.mp4 into English and Japanese, in this voice"
```

The dubbed `<lang>-<timestamp>.mp4` and its `<lang>-<timestamp>.json` gate record land next to the
source. Commit a small input together with its result to turn an example into a reproducible demo.

> The best demo is a short, clean, **single-speaker** clip (a lecture or talking-head) plus the
> dubbed result — see [Getting good results](../README.md#getting-good-results) for why input
> quality matters most.
