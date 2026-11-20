"""Unit tests for translator.py. The network call is mocked, so these run offline."""

from unittest.mock import patch

import pytest

import translator
from translator import AUTO, TranslationError, translate_text, validate


def test_validate_strips_text():
    assert validate("  hello  ", "en", "ar") == "hello"


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_text_rejected(text):
    with pytest.raises(TranslationError, match="enter some text"):
        validate(text, "en", "ar")


def test_too_long_rejected():
    with pytest.raises(TranslationError, match="too long"):
        validate("a" * (translator.MAX_CHARS + 1), "en", "ar")


def test_same_language_rejected():
    with pytest.raises(TranslationError, match="same"):
        validate("hello", "en", "en")


def test_auto_target_rejected():
    with pytest.raises(TranslationError):
        validate("hello", "en", AUTO)


def test_translate_calls_google_by_default(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)
    with patch("translator.GoogleTranslator") as mock_cls:
        mock_cls.return_value.translate.return_value = "مرحبا"
        assert translate_text("hello", AUTO, "ar") == "مرحبا"
        mock_cls.assert_called_once_with(source=AUTO, target="ar")


def test_translate_uses_microsoft_when_key_set(monkeypatch):
    monkeypatch.setenv("MS_TRANSLATOR_KEY", "dummy")
    monkeypatch.setenv("MS_TRANSLATOR_REGION", "westeurope")
    with patch("translator.MicrosoftTranslator") as mock_cls:
        mock_cls.return_value.translate.return_value = "Hola"
        assert translate_text("hello", "en", "es") == "Hola"
        assert translator.active_provider() == "Microsoft Translator"


def test_network_error_becomes_friendly_message(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)
    with patch("translator.GoogleTranslator") as mock_cls, \
         patch("translator.requests.get", side_effect=translator.requests.ConnectionError()):
        mock_cls.return_value.translate.side_effect = translator.RequestError()
        with pytest.raises(TranslationError, match="internet"):
            translate_text("hello", "en", "fr")


def test_empty_result_raises(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)
    with patch("translator.GoogleTranslator") as mock_cls:
        mock_cls.return_value.translate.return_value = ""
        with pytest.raises(TranslationError):
            translate_text("hello", "en", "fr")


def test_language_list_contains_common_languages():
    for code in ["en", "ar", "fr", "de", "es", "zh-CN"]:
        assert code in translator.CODE_TO_NAME


def test_tts_support_detection():
    assert translator.tts_supported("en")
    assert translator.tts_supported("ar")


class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_uses_google_gtx_when_library_endpoint_refuses(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)

    def fake_get(url, params, timeout):
        assert url == translator.GTX_URL and params["sl"] == "en" and params["tl"] == "ar"
        return _FakeResponse(200, [[["طبيعي", "natural", None, None, 10]], None, "en"])

    with patch("translator.GoogleTranslator") as google, patch("translator.requests.get", fake_get):
        google.return_value.translate.side_effect = translator.TooManyRequests()
        assert translator.translate_with_provider("natural", "en", "ar") == ("طبيعي", "Google Translate")


def test_falls_back_to_mymemory_when_google_refuses(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)
    calls = []

    def fake_get(url, params, timeout):
        if url == translator.GTX_URL:
            return _FakeResponse(429)
        calls.append(params)
        return _FakeResponse(200, {"responseStatus": 200, "responseData": {"translatedText": "طبيعي"}})

    with patch("translator.GoogleTranslator") as google, patch("translator.requests.get", fake_get):
        google.return_value.translate.side_effect = translator.TooManyRequests()
        result, provider = translator.translate_with_provider("natural", "en", "ar")
    assert (result, provider) == ("طبيعي", "MyMemory")
    assert calls[0]["langpair"] == "en|ar"


def test_mymemory_skips_untranslated_top_hit():
    # real response shape: the top hit just repeats the English word
    data = {
        "responseData": {"translatedText": "natural", "match": 0.99},
        "matches": [
            {"translation": "natural", "quality": "74", "match": 0.99},
            {"translation": "\u0637\u0628\u064a\u0639\u064a", "quality": 0, "match": 0.99},
            {"translation": "\u200e\u0637\u064e\u0628\u064a\u0639\u0650\u064a\u0651\u200e", "quality": "0", "match": 0.99},
        ],
    }
    assert translator._best_mymemory(data, "natural") == "طبيعي"


def test_clean_removes_direction_marks_and_entities():
    assert translator._clean("\u200eمرحبا&#39;\u200f") == "مرحبا'"


def test_mymemory_autodetect_and_quota_error(monkeypatch):
    def fake_get(url, params, timeout):
        assert params["langpair"].startswith("Autodetect|")
        return _FakeResponse(200, {"responseStatus": 429, "responseDetails": "MYMEMORY WARNING: quota used"})

    with patch("translator.requests.get", fake_get):
        with pytest.raises(translator.RequestError):
            translator.translate_mymemory("hello", AUTO, "fr")


def test_both_services_fail_gives_friendly_error(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)
    with patch("translator.GoogleTranslator") as google, \
         patch("translator.requests.get", return_value=_FakeResponse(429)):
        google.return_value.translate.side_effect = translator.TooManyRequests()
        with pytest.raises(TranslationError, match="refusing"):
            translate_text("hello", "en", "ar")


def test_long_text_is_split_for_mymemory():
    pieces = translator._chunks("Hello there. " * 100, translator.MYMEMORY_CHUNK)
    assert len(pieces) > 1 and all(len(p) <= translator.MYMEMORY_CHUNK for p in pieces)
