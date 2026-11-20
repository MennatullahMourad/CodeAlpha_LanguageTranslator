"""Shared visual theme for the three apps.

Palette (from the project mood board):
    abyss  #001D39   harbor #0A4174   steel #49769F   lagoon #4E8EA2
    sky    #7BBDE8   ice    #BDD8E9   page   #EEF5F9
The navy band with a wave edge at the top of every page is drawn as an SVG
background on the main area, so it works with or without a sidebar.
Base colours and fonts live in .streamlit/config.toml.
"""

import html
from urllib.parse import quote

import streamlit as st

_WAVE_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320' preserveAspectRatio='none'>
  <rect width='1440' height='320' fill='#001D39'/>
  <path d='M1080 0 C1180 60 1330 40 1440 110 L1440 0 Z' fill='#0A4174' opacity='.55'/>
  <path d='M0 228 C260 282 520 176 800 212 C1040 244 1250 286 1440 232 L1440 320 L0 320 Z' fill='#0A4174'/>
  <path d='M0 256 C240 304 500 222 760 246 C1010 270 1230 314 1440 262 L1440 320 L0 320 Z' fill='#EEF5F9'/>
</svg>
"""
_WAVE_URI = "data:image/svg+xml," + quote(" ".join(_WAVE_SVG.split()))

_CSS = """
<style>
:root {
  --abyss: #001D39; --harbor: #0A4174; --steel: #49769F; --lagoon: #4E8EA2;
  --sky: #7BBDE8; --ice: #BDD8E9; --page: #EEF5F9; --line: #D3E3EE;
  --shadow: 0 12px 32px rgba(0, 29, 57, .09);
}

/* navy band behind the page header */
[data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"] {
  background: url("WAVE_URI") top center / 100% 330px no-repeat, var(--page);
}
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 3.2rem; max-width: 1120px; }

.page-head { color: #fff; min-height: 170px; max-width: 640px; }
.page-head .title {
  font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700;
  font-size: clamp(2rem, 4vw, 2.9rem); line-height: 1.05; letter-spacing: -.02em; margin: 0;
}
.page-head .lede { color: var(--ice); font-size: 1.05rem; line-height: 1.5; margin-top: .7rem; }

/* white working surfaces: keyed containers get the class .st-key-<key> */
.surface {
  background: #fff; border: 1px solid var(--line); border-radius: 20px;
  box-shadow: var(--shadow); padding: 1.4rem 1.5rem;
}
div[class*="st-key-surface"] {
  background: #fff; border: 1px solid var(--line) !important; border-radius: 20px;
  box-shadow: var(--shadow); padding: 1.4rem 1.5rem;
}

.muted { color: var(--steel); }
.page-foot { color: var(--steel); font-size: .85rem; text-align: center; margin: 2.5rem 0 1rem; }

/* sidebar headings in the light sidebar text colour */
section[data-testid="stSidebar"] h3 { color: #fff; }
</style>
""".replace("WAVE_URI", _WAVE_URI)


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_head(title: str, lede: str) -> None:
    """Title and one-line description, drawn on the navy band."""
    st.markdown(
        f'<div class="page-head"><div class="title">{html.escape(title)}</div>'
        f'<div class="lede">{html.escape(lede)}</div></div>',
        unsafe_allow_html=True,
    )


def page_foot(text: str) -> None:
    st.markdown(f'<div class="page-foot">{html.escape(text)}</div>', unsafe_allow_html=True)
