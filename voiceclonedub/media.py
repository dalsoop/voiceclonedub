"""ffmpeg/ffprobe helpers. ffmpeg must be on PATH."""
import re
import subprocess


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def dur(path):
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", path])
    try:
        return float((r.stdout or "0").strip() or 0)
    except ValueError:
        return 0.0


def lufs(path):
    """Integrated loudness (EBU R128) in LUFS, or None. Speech-gated."""
    r = _run(["ffmpeg", "-nostdin", "-i", path, "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    mm = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", (r.stderr or ""))
    try:
        return float(mm[-1]) if mm else None
    except ValueError:
        return None


def streams(path):
    """Newline-joined codec_type list, e.g. contains 'video' and 'audio'."""
    return _run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                 "-of", "default=nw=1:nk=1", path]).stdout or ""


def extract_audio(video, out_wav, sr=16000, mono=True):
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-i", video, "-vn"]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr), "-c:a", "pcm_s16le", out_wav]
    subprocess.run(cmd, check=True)
    return out_wav


def to_wav(src, out_wav, sr=48000, mono=True, af=None):
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sr)]
    if af:
        cmd += ["-af", af]
    cmd += [out_wav]
    subprocess.run(cmd, check=True)
    return out_wav


def mux(video, audio, out, vcopy=True):
    """Replace the video's audio track with `audio`."""
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-i", video, "-i", audio,
           "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy" if vcopy else "libx264",
           "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    subprocess.run(cmd, check=True)
    return out
