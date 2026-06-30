"""Config layering: defaults <- file <- env, with type coercion."""

from voiceclonedub import config


def test_defaults_loaded_when_no_file():
    cfg = config.load("/nonexistent/voiceclonedub.toml")
    assert cfg["tts"]["cfg"] == 1.9
    assert cfg["align"]["max_drift_s"] == 0.5
    assert cfg["translate"]["backend"] == "ollama"


def test_deep_merge_is_recursive_and_non_mutating():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    over = {"a": {"y": 9}, "c": 4}
    out = config._deep_merge(base, over)
    assert out == {"a": {"x": 1, "y": 9}, "b": 3, "c": 4}
    assert base["a"]["y"] == 2  # original left untouched


def test_env_override_coerces_types(monkeypatch):
    monkeypatch.setenv("VCDUB_TTS_STEPS", "80")
    monkeypatch.setenv("VCDUB_ALIGN_FILL", "1")
    cfg = config.load("/nonexistent/voiceclonedub.toml")
    assert cfg["tts"]["steps"] == 80  # int preserved
    assert cfg["align"]["fill"] is True  # bool from "1"
