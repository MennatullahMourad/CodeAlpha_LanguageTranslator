"""UI smoke test: renders the app and clicks Translate with the API mocked."""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_translates_and_swaps(monkeypatch):
    monkeypatch.delenv("MS_TRANSLATOR_KEY", raising=False)
    with patch("deep_translator.GoogleTranslator.translate", return_value="مرحبا بالعالم"):
        at = AppTest.from_file(APP, default_timeout=30).run()
        assert not at.exception
        at.text_area(key="input_text").set_value("Hello world")
        next(b for b in at.button if b.label == "Translate").click().run()
        assert not at.exception
        assert at.session_state.result == "مرحبا بالعالم"

        # swap moves the translation into the input box
        at.button(key="swap").click().run()
        assert at.session_state.src == "ar" and at.session_state.tgt == "en"
        assert at.session_state.input_text == "مرحبا بالعالم"


def test_empty_input_shows_no_result():
    at = AppTest.from_file(APP, default_timeout=30).run()
    next(b for b in at.button if b.label == "Translate").click().run()
    assert not at.exception
    assert at.session_state.result == ""
