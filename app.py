"""Language Translation Tool — CodeAlpha AI Internship, Task 1.

Run:  streamlit run app.py
"""

import html
import json

import streamlit as st

from styles import inject_css, page_foot, page_head
from translator import (
    AUTO,
    CODE_TO_NAME,
    LANGUAGES,
    MAX_CHARS,
    TranslationError,
    active_provider,
    text_to_speech,
    translate_with_provider,
    tts_supported,
)

st.set_page_config(page_title="Translator", page_icon=":material/translate:", layout="wide")
inject_css()
st.markdown(
    """<style>
    .output {
      background: var(--page); border: 1px solid var(--line); border-radius: .75rem;
      min-height: 220px; padding: .75rem 1rem; font-size: 1rem; line-height: 1.6; margin-bottom: .75rem;
      white-space: pre-wrap; overflow-wrap: anywhere;
    }
    .output.empty { color: var(--steel); }
    .stTextArea textarea { font-size: 1rem; line-height: 1.6; }
    </style>""",
    unsafe_allow_html=True,
)

SOURCE_OPTIONS = [AUTO] + list(LANGUAGES.values())
TARGET_OPTIONS = list(LANGUAGES.values())


def label(code: str) -> str:
    return "Detect language" if code == AUTO else CODE_TO_NAME.get(code, code)


# ---------- session state ----------
defaults = {"src": "en", "tgt": "ar", "input_text": "", "result": "", "result_lang": None, "audio": None,
            "provider": active_provider()}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)


def swap_languages() -> None:
    """Swap languages and move the last translation into the input box."""
    if st.session_state.src == AUTO:
        return
    st.session_state.src, st.session_state.tgt = st.session_state.tgt, st.session_state.src
    if st.session_state.result:
        st.session_state.input_text = st.session_state.result
    st.session_state.result = ""
    st.session_state.audio = None


def clear_all() -> None:
    st.session_state.input_text = ""
    st.session_state.result = ""
    st.session_state.audio = None


_COPY_ICON = (
    '<svg viewBox="0 -960 960 960" width="18" height="18" fill="currentColor" aria-hidden="true">'
    '<path d="M360-240q-33 0-56.5-23.5T280-320v-480q0-33 23.5-56.5T360-880h360q33 0 56.5 23.5'
    'T800-800v480q0 33-23.5 56.5T720-240H360Zm0-80h360v-480H360v480ZM200-80q-33 0-56.5-23.5'
    'T120-160v-560h80v560h440v80H200Z"/></svg>'
)


def copy_button(text: str) -> None:
    """HTML button that copies `text` to the clipboard (Streamlit has no clipboard API)."""
    # escape '<' so translated text can never close the <script> tag
    payload = json.dumps(text).replace("<", "\\u003c")
    st.iframe(
        f"""
        <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@500&display=swap" rel="stylesheet">
        <style>
          body {{ margin: 0; }}
          button {{
            font: 400 14px Figtree, 'Source Sans Pro', sans-serif; width: 100%; height: 40px; margin: 0;
            display: flex; gap: 8px; align-items: center; justify-content: center;
            border-radius: 999px; cursor: pointer; border: 1px solid #C9DDEA;
            background: #F6FAFC; color: #001D39;
          }}
          button:hover {{ border-color: #0A4174; color: #0A4174; }}
          button:focus-visible {{ outline: 2px solid #7BBDE8; outline-offset: 2px; }}
        </style>
        <button id="copy">{_COPY_ICON}<span>Copy</span></button>
        <script>
          const btn = document.getElementById("copy");
          const label = btn.querySelector("span");
          btn.onclick = () => {{
            const text = {payload};
            const done = () => {{ label.innerText = "Copied"; setTimeout(() => label.innerText = "Copy", 1500); }};
            const fallback = () => {{
              const area = document.createElement("textarea");
              area.value = text; document.body.appendChild(area); area.select();
              document.execCommand("copy"); area.remove(); done();
            }};
            if (navigator.clipboard) {{ navigator.clipboard.writeText(text).then(done, fallback); }}
            else {{ fallback(); }}
          }};
        </script>
        """,
        height=42,
    )


page_head("Translator", "Type or paste text, choose two languages, and get the translation. "
                        "You can copy it or listen to it.")

with st.container(key="surface-translate"):
    c_src, c_swap, c_tgt = st.columns([10, 1, 10], vertical_alignment="bottom")
    c_src.selectbox("From", SOURCE_OPTIONS, format_func=label, key="src")
    c_swap.button("", icon=":material/swap_horiz:", on_click=swap_languages, width="stretch",
                  help="Swap languages", disabled=st.session_state.src == AUTO, key="swap")
    c_tgt.selectbox("To", TARGET_OPTIONS, format_func=label, key="tgt")

    c_in, _, c_out = st.columns([10, 1, 10])
    c_in.text_area("Text to translate", key="input_text", height=220, max_chars=MAX_CHARS,
                   placeholder="Type or paste text", label_visibility="collapsed")

    with c_in:
        with st.container(horizontal=True, gap="small"):
            translate_clicked = st.button("Translate", type="primary", icon=":material/translate:")
            st.button("Clear", on_click=clear_all, type="tertiary")

    if translate_clicked:
        try:
            with st.spinner("Translating"):
                st.session_state.result, st.session_state.provider = translate_with_provider(
                    st.session_state.input_text, st.session_state.src, st.session_state.tgt
                )
            st.session_state.result_lang = st.session_state.tgt
            st.session_state.audio = None
        except TranslationError as err:
            st.session_state.result = ""
            st.toast(str(err), icon=":material/error:")

    with c_out:
        result = st.session_state.result
        if result:
            st.markdown(f'<div class="output" dir="auto">{html.escape(result)}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="output empty">The translation appears here.</div>', unsafe_allow_html=True)

        if result:
            a1, a2 = st.columns(2, vertical_alignment="center")
            with a1:
                copy_button(result)
            with a2:
                can_speak = tts_supported(st.session_state.result_lang)
                if st.button("Listen", icon=":material/volume_up:", width="stretch", disabled=not can_speak,
                             help=None if can_speak else "Listening isn't available for this language"):
                    try:
                        with st.spinner("Creating audio"):
                            st.session_state.audio = text_to_speech(result, st.session_state.result_lang)
                    except TranslationError as err:
                        st.toast(str(err), icon=":material/error:")
            if st.session_state.audio:
                st.audio(st.session_state.audio, format="audio/mp3", autoplay=True)

page_foot(f"Translated by {st.session_state.provider}")
