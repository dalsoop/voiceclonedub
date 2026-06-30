"""Pure backend helpers: language names, output cleaning, script + negation guards."""

from voiceclonedub import backends


def test_lang_name_known_and_passthrough():
    assert backends.lang_name("en") == "English"
    assert backends.lang_name("xx") == "xx"


def test_clean_strips_model_preamble_and_quotes():
    assert backends._clean('Sure, here is the translation:\n"Hello"') == "Hello"
    assert backends._clean("Hello") == "Hello"


def test_wrong_script_cjk_guards():
    assert backends._wrong_script("こんにちは", "ja") is False
    assert backends._wrong_script("안녕하세요", "ja") is True  # Hangul leaked into Japanese
    assert backends._wrong_script("你好", "zh") is False
    assert backends._wrong_script("", "ja") is True


def test_neg_warn_flags_dropped_negation():
    segs = [{"text": "맡기지 맙시다"}, {"text": "좋아요"}]
    texts = {1: "Let's just leave it to the AI", 2: "It's good"}  # line 1 dropped the negation
    assert backends.neg_warn(segs, texts, src="ko") == [1]


def test_neg_warn_clean_when_negation_kept():
    segs = [{"text": "맡기지 맙시다"}]
    texts = {1: "Let's not leave it to the AI"}
    assert backends.neg_warn(segs, texts, src="ko") == []
