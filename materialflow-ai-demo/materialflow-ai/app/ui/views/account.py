import streamlit as st

from app.services import auth
from app.ui import state


def _form(key: str, *, forced: bool) -> None:
    current = state.user()
    with st.form(key):
        old = st.text_input("Palavra-passe atual", type="password", autocomplete="current-password")
        new = st.text_input("Nova palavra-passe", type="password", autocomplete="new-password")
        repeat = st.text_input("Repita a nova palavra-passe", type="password", autocomplete="new-password")
        go = st.form_submit_button("Guardar nova palavra-passe", type="primary")
    if go:
        if new != repeat:
            st.error("As palavras-passe não coincidem.")
            return
        _, error = state.run(
            auth.change_password, current, old, new, keep_token=st.session_state.get(state.TOKEN_KEY)
        )
        if error is not None:
            state.show_error(error)
        else:
            if forced:
                st.rerun()  # o utilizador é relido da base de dados e segue para a aplicação
            st.success("Palavra-passe alterada.")


def render() -> None:
    st.header("A minha conta")
    current = state.user()
    st.text(f"Utilizador: {current.username}")
    st.subheader("Alterar palavra-passe")
    st.caption("Use pelo menos 12 caracteres. Uma frase longa é mais segura do que símbolos aleatórios.")
    _form("change_password", forced=False)


def render_forced_change(user) -> None:
    _, middle, _ = st.columns([1, 1.4, 1])
    with middle:
        st.title("Defina a sua palavra-passe")
        st.info("Por segurança, tem de escolher uma nova palavra-passe antes de continuar.")
        _form("forced_change", forced=True)
        if st.button("Terminar sessão"):
            state.end_session()
            st.rerun()
