"""SRT parse/format round-trips and timestamp edge cases."""

from voiceclonedub import srt


def test_fmt_ts_basic():
    assert srt.fmt_ts(0) == "00:00:00,000"
    assert srt.fmt_ts(1500) == "00:00:01,500"
    assert srt.fmt_ts(3661001) == "01:01:01,001"


def test_fmt_ts_clamps_negative():
    assert srt.fmt_ts(-5) == "00:00:00,000"


def test_parse_dump_roundtrip(tmp_path):
    cues = [
        {"start_ms": 0, "end_ms": 1500, "text": "Hello world"},
        {"start_ms": 2000, "end_ms": 3200, "text": "Second line"},
    ]
    p = tmp_path / "x.srt"
    srt.dump(cues, str(p))
    assert srt.parse(str(p)) == cues


def test_parse_accepts_dot_milliseconds(tmp_path):
    p = tmp_path / "y.srt"
    p.write_text("1\n00:00:01.000 --> 00:00:02.000\nHi\n", encoding="utf-8")
    assert srt.parse(str(p)) == [{"start_ms": 1000, "end_ms": 2000, "text": "Hi"}]


def test_parse_joins_multiline_text(tmp_path):
    p = tmp_path / "z.srt"
    p.write_text("1\n00:00:00,000 --> 00:00:01,000\nline one\nline two\n", encoding="utf-8")
    assert srt.parse(str(p))[0]["text"] == "line one line two"
