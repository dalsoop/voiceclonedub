# Examples

Real renders you can play and compare — the **same short, re-voiced into each language**.

## Compare the dubs

Click a cell to play it on GitHub. **short-08** (clean diagram slides) is the best reference render.

<table>
<tr><th>Short</th><th>🇺🇸 English</th><th>🇯🇵 Japanese</th></tr>

<tr>
<td><b>short-08</b> ⭐<br/><sub>clean diagram slides</sub></td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-08/en.mp4

</td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-08/ja.mp4

</td>
</tr>

<tr>
<td><b>short-05</b></td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-05/en.mp4

</td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-05/ja.mp4

</td>
</tr>

<tr>
<td><b>short-01</b><br/><sub><a href="short-01/source-ko.mp4">🇰🇷 source</a></sub></td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-01/en.mp4

</td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-01/ja.mp4

</td>
</tr>

<tr>
<td><b>short-03</b></td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-03/en.mp4

</td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-03/ja.mp4

</td>
</tr>

<tr>
<td><b>short-04</b></td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-04/en.mp4

</td>
<td>

https://github.com/dalsoop/voiceclonedub/raw/main/examples/short-04/ja.mp4

</td>
</tr>
</table>

> **Notes.** The Korean source video is kept only for **short-01** (every dub already carries the
> original footage with re-voiced audio, so a separate source isn't needed to watch the result).
> Chinese (`zh`) text translations exist in the pipeline but weren't synthesized to video in this
> set. **short-05**'s English is the canonical reference render.

Each dub is the original video with the audio replaced — **same timing, your voice, another
language**. Listen to short-05 in English then Japanese: the words land where the speaker's mouth
moves, and it's recognizably the same voice.

## Reproduce / add your own

A ready-to-use voice reference ships here too: [`voice-reference.wav`](voice-reference.wav)
— a ~10s clean clip of the author's voice, exactly the kind of sample `--voice` wants. Every
English/Japanese render above was cloned from it. Swap in your own to hear the shorts in *your* voice.

```bash
# CLI (short-01 keeps its Korean source)
dub examples/short-01/source-ko.mp4 --from ko --to en,ja --voice examples/voice-reference.wav --out examples/short-01

# …or from Claude Code with the plugin installed
#   "dub this short into English and Japanese, in this voice"
```

The dubbed `<lang>-<timestamp>.mp4` and its `<lang>-<timestamp>.json` gate record land next to the
source. To add an example, drop a short clip under `examples/<name>/` and commit it with its result.

## Layout

```
examples/
  <name>/
    source-ko.mp4       # source video (kept where available)
    en.mp4 / ja.mp4     # dubbed renders
    <lang>-<stamp>.json # quality-gate record for a fresh run (optional)
```

`examples/**` is whitelisted in [`.gitignore`](../.gitignore), so media here is committed even
though `*.mp4` is ignored everywhere else. Keep inputs short to keep the repo light. The best demo
is a clean, **single-speaker** clip — see [Getting good results](../README.md#getting-good-results).
