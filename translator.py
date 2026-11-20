"""Translation + text-to-speech logic, kept separate from the UI so it can be tested.

Provider selection:
  * Default: Google Translate through the `deep-translator` package (no API key needed).
    That endpoint sometimes refuses requests from a whole network (HTTP 429). When that
    happens the app tries Google's public "gtx" endpoint directly, and only if that also
    fails does it use the free MyMemory API (lower quality, used as a last resort).
  * Microsoft Translator: set the environment variables MS_TRANSLATOR_KEY and
    MS_TRANSLATOR_REGION (from your Azure Translator resource) and it is used instead.
"""

from __future__ import annotations

import html
import io
import os
import re

import requests

from deep_translator import GoogleTranslator, MicrosoftTranslator
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES
from deep_translator.exceptions import (
    LanguageNotSupportedException,
    NotValidLength,
    NotValidPayload,
    RequestError,
    TooManyRequests,
    TranslationNotFound,
)
from gtts import gTTS
from gtts.lang import tts_langs

MAX_CHARS = 5000
AUTO = "auto"

# {"English": "en", "Arabic": "ar", ...} sorted by display name
LANGUAGES: dict[str, str] = {
    name.title(): code for name, code in sorted(GOOGLE_LANGUAGES_TO_CODES.items())
}
CODE_TO_NAME: dict[str, str] = {code: name for name, code in LANGUAGES.items()}

_TTS_LANGS = tts_langs()


class TranslationError(Exception):
    """Raised with a message that is safe to show to the user."""


def active_provider() -> str:
    return "Microsoft Translator" if os.getenv("MS_TRANSLATOR_KEY") else "Google Translate"


def validate(text: str, source: str, target: str) -> str:
    """Return cleaned text or raise TranslationError."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise TranslationError("Please enter some text to translate.")
    if len(cleaned) > MAX_CHARS:
        raise TranslationError(f"Text is too long ({len(cleaned)} characters). The limit is {MAX_CHARS}.")
    if target == AUTO:
        raise TranslationError("Please choose a target language.")
    if source == target:
        raise TranslationError("Source and target languages are the same.")
    return cleaned


def _build_translator(source: str, target: str):
    key = os.getenv("MS_TRANSLATOR_KEY")
    if key:
        return MicrosoftTranslator(
            api_key=key,
            region=os.getenv("MS_TRANSLATOR_REGION"),
            source=source,
            target=target,
        )
    return GoogleTranslator(source=source, target=target)


GTX_URL = "https://translate.googleapis.com/translate_a/single"
GTX_CHUNK = 900       # keeps each GET request URL comfortably short
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MYMEMORY_CHUNK = 450  # the free API accepts up to 500 characters per request


def _chunks(text: str, size: int) -> list[str]:
    """Split text into pieces of at most `size` characters, breaking at sentence ends or spaces."""
    pieces, current = [], ""
    for part in re.split(r"(?<=[.!?\n])\s+", text):
        while len(part) > size:
            cut = part.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            pieces.append(part[:cut])
            part = part[cut:].lstrip()
        if len(current) + len(part) + 1 > size and current:
            pieces.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        pieces.append(current)
    return pieces


_BIDI_MARKS = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


def _clean(text: str) -> str:
    """Remove HTML entities and invisible direction marks some services add."""
    return _BIDI_MARKS.sub("", html.unescape(text or "")).strip()


def _check_status(response) -> None:
    if response.status_code == 429:
        raise TooManyRequests()
    if response.status_code != 200:
        raise RequestError()


def translate_gtx(text: str, source: str, target: str) -> str:
    """Translate with Google's public JSON endpoint (the one browser extensions use)."""
    out = []
    for piece in _chunks(text, GTX_CHUNK):
        response = requests.get(
            GTX_URL, params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": piece}, timeout=15
        )
        _check_status(response)
        data = response.json()
        # data[0] is a list of [translated_segment, original_segment, ...]
        out.append("".join(seg[0] for seg in (data[0] or []) if seg and seg[0]))
    return _clean(" ".join(out))


def _best_mymemory(data: dict, piece: str) -> str:
    """MyMemory's top hit is sometimes an untranslated copy of the input; prefer a real translation."""
    best = _clean(data["responseData"]["translatedText"])
    if best.lower() != piece.lower():
        return best
    candidates = [m for m in data.get("matches", [])
                  if _clean(m.get("translation", "")).lower() not in ("", piece.lower())]
    if not candidates:
        return best
    top = max(candidates, key=lambda m: (float(m.get("match") or 0), float(m.get("quality") or 0)))
    return _clean(top["translation"])


def translate_mymemory(text: str, source: str, target: str) -> str:
    """Translate with the free MyMemory API (accepts the same short codes as Google)."""
    src = "Autodetect" if source == AUTO else source
    out = []
    for piece in _chunks(text, MYMEMORY_CHUNK):
        response = requests.get(MYMEMORY_URL, params={"q": piece, "langpair": f"{src}|{target}"}, timeout=15)
        _check_status(response)
        data = response.json()
        if int(data.get("responseStatus", 200)) != 200:
            # e.g. the daily free limit is used up, or an unsupported language pair
            raise RequestError(str(data.get("responseDetails", "")))
        out.append(_best_mymemory(data, piece))
    return " ".join(out)


def translate_text(text: str, source: str, target: str) -> str:
    """Translate `text` from `source` to `target` language codes (source may be 'auto')."""
    return translate_with_provider(text, source, target)[0]


def translate_with_provider(text: str, source: str, target: str) -> tuple[str, str]:
    """Translate and also return the name of the service that produced the translation."""
    cleaned = validate(text, source, target)
    provider = active_provider()
    try:
        network_errors = (TooManyRequests, RequestError, ConnectionError, requests.RequestException, ValueError)
        try:
            result = _build_translator(source, target).translate(cleaned)
        except network_errors:
            if provider != "Google Translate":
                raise
            try:
                result = translate_gtx(cleaned, source, target)
            except network_errors:
                result, provider = translate_mymemory(cleaned, source, target), "MyMemory"
    except LanguageNotSupportedException as exc:
        raise TranslationError("This language pair is not supported by the provider.") from exc
    except TooManyRequests as exc:
        raise TranslationError("The translation services are refusing requests right now. Wait a few minutes and try again.") from exc
    except (RequestError, ConnectionError, requests.RequestException) as exc:
        raise TranslationError("Could not reach the translation service. Check your internet connection.") from exc
    except (TranslationNotFound, NotValidPayload, NotValidLength) as exc:
        raise TranslationError("No translation was returned for this text.") from exc
    except Exception as exc:  # network libraries raise many different types
        raise TranslationError(f"Translation failed: {exc}") from exc

    if not result:
        raise TranslationError("No translation was returned for this text.")
    return result, provider


def tts_supported(lang_code: str) -> bool:
    return lang_code in _TTS_LANGS or lang_code.split("-")[0] in _TTS_LANGS


def text_to_speech(text: str, lang_code: str) -> bytes:
    """Return MP3 bytes for `text` spoken in `lang_code`."""
    if not tts_supported(lang_code):
        raise TranslationError("Text-to-speech is not available for this language.")
    lang = lang_code if lang_code in _TTS_LANGS else lang_code.split("-")[0]
    buffer = io.BytesIO()
    try:
        gTTS(text=text, lang=lang).write_to_fp(buffer)
    except Exception as exc:
        raise TranslationError("Could not generate audio. Check your internet connection.") from exc
    return buffer.getvalue()
