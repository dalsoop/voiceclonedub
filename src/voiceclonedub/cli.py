"""`dub` CLI entrypoint."""

from __future__ import annotations

import argparse
import sys

from . import __version__, config, pipeline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dub",
        description="Dub a video into another language in your own voice (local, subtitle-accurate sync).",
    )
    ap.add_argument("input", help="input video (mp4/mov/...)")
    ap.add_argument(
        "--to", required=True, help="target language(s), comma-separated, e.g. en or en,ja"
    )
    ap.add_argument(
        "--from", dest="src", default=None, help="source language (default: auto-detect)"
    )
    ap.add_argument("--voice", default=None, help="reference audio (wav) for voice cloning")
    ap.add_argument("--config", default=None, help="config file (default: ./voiceclonedub.toml)")
    ap.add_argument("--out", default="out", help="output directory (default: ./out)")
    ap.add_argument("--version", action="version", version=f"voiceclonedub {__version__}")
    args = ap.parse_args(argv)

    cfg = config.load(args.config)
    targets = [t.strip() for t in args.to.split(",") if t.strip()]
    rc = 0
    for tgt in targets:
        print(f"▶ dubbing {args.input} -> {tgt} ...", file=sys.stderr)
        try:
            rec = pipeline.dub(
                args.input,
                tgt,
                cfg,
                src=args.src,
                voice=args.voice,
                out_dir=args.out,
            )
        except Exception as e:
            print(f"✗ {tgt}: {e}", file=sys.stderr)
            rc = 1
            continue
        g = rec["gates"]
        status = "✓ ok" if rec["ok"] else "⚠ check gates"
        print(f"{status}  {rec['out']}", file=sys.stderr)
        print(
            f"   coverage={g['coverage']} drift={g['drift_max']}s "
            f"overlap={g['overlap']} too_fast={g['too_fast']} "
            f"trimmed={g['word_trimmed']} fidelity_errors={g['fidelity_errors']}",
            file=sys.stderr,
        )
        if not rec["ok"]:
            rc = max(rc, 0)  # informational; still produced output
    return rc


if __name__ == "__main__":
    sys.exit(main())
