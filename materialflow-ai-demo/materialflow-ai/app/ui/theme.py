"""Estilo da aplicação. O CSS é estático (nunca inclui texto introduzido por utilizadores)."""

import streamlit as st

_CSS = """
<style>
  .block-container { padding-top: 2rem; max-width: 1200px; }
  h1, h2, h3 { color: #0F3A47; letter-spacing: -0.01em; }
  .mf-badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
              font-size: 0.78rem; font-weight: 600; white-space: nowrap; }
  .mf-draft    { background: #E6EAED; color: #3B4A54; }
  .mf-pending  { background: #FFF1CC; color: #7A5600; }
  .mf-returned { background: #FBE0DC; color: #9A2A1A; }
  .mf-approved { background: #D8EEF2; color: #0F5C6E; }
  .mf-done     { background: #DAF0DF; color: #1E6B35; }
  .mf-code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: #52646F; }
  div[data-testid="stSidebar"] { border-right: 1px solid #DCE3E7; }
  @media (max-width: 640px) { .block-container { padding: 1rem 0.75rem; } }
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
