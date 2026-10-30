import streamlit as st

from app.config import get_settings
from app.db.session import session_scope
from app.domain.errors import DomainError, ValidationError
from app.services import auth
from app.ui import state


def render() -> None:
    _, middle, _ = st.columns([1, 1.4, 1])
    with middle:
        st.title("MaterialFlow AI")
        st.caption("Fichas de materiais normalizadas para o SAP")

        if get_settings().demo_mode:
            st.info(
                "Demonstração com dados fictícios. Utilizadores: demo.tecnico (Técnicos / Logística), "
                "demo.compras (Compras), demo.dadosmestre (Dados Mestre) e demo.admin (administração de contas). "
                "A palavra-passe é a que lhe foi indicada. Não introduza dados reais."
            )

        notice = st.session_state.pop("mf_notice", None)
        if notice:
            st.info(notice)
        done = st.session_state.pop("mf_reset_done", False)
        if done:
            st.success("Palavra-passe alterada. Já pode iniciar sessão.")

        with st.form("login"):
            username = st.text_input("Nome de utilizador", autocomplete="username")
            password = st.text_input("Palavra-passe", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Iniciar sessão", type="primary", use_container_width=True)

        if submitted:
            result, error = None, None
            try:
                with session_scope() as session:
                    result = auth.authenticate(session, username, password)
            except DomainError as exc:
                error = exc
            if error is not None:
                st.error(str(error))
            elif result is not None:
                current, token = result
                state.start_session(token, current)
                st.rerun()

        with st.expander("Esqueci-me da palavra-passe"):
            st.write(
                "Peça ao administrador técnico um código de recuperação. "
                "O código é de uso único e expira em poucos minutos."
            )
            with st.form("reset"):
                r_user = st.text_input("Nome de utilizador", key="reset_user")
                r_code = st.text_input("Código de recuperação", key="reset_code")
                r_new = st.text_input("Nova palavra-passe", type="password", key="reset_new")
                r_repeat = st.text_input("Repita a nova palavra-passe", type="password", key="reset_repeat")
                go = st.form_submit_button("Definir nova palavra-passe", use_container_width=True)
            if go:
                if r_new != r_repeat:
                    st.error("As palavras-passe não coincidem.")
                else:
                    error = None
                    try:
                        with session_scope() as session:
                            auth.reset_password_with_token(session, r_user, r_code.strip(), r_new)
                    except ValidationError as exc:
                        error = exc
                    except DomainError as exc:
                        error = exc
                    if error is not None:
                        state.show_error(error)
                    else:
                        st.session_state["mf_reset_done"] = True
                        st.rerun()
