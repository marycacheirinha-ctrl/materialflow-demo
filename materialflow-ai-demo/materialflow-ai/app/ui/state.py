"""Estado de sessão da interface e execução de serviços em transações."""

from collections.abc import Callable
from typing import Any

import streamlit as st

from app.db.session import session_scope
from app.domain.errors import DomainError, ValidationError
from app.services import auth
from app.services.dto import CurrentUser

TOKEN_KEY = "mf_token"
USER_KEY = "mf_user"
SELECTED_KEY = "mf_selected_request"


def resolve_current_user() -> CurrentUser | None:
    """Valida a sessão no servidor em cada interação (expiração, revogação, conta ativa)."""
    token = st.session_state.get(TOKEN_KEY)
    if not token:
        st.session_state.pop(USER_KEY, None)
        return None
    with session_scope() as session:
        user = auth.resolve_session(session, token)
    if user is None:
        st.session_state.pop(TOKEN_KEY, None)
        st.session_state.pop(USER_KEY, None)
        st.session_state["mf_notice"] = "A sua sessão terminou. Inicie sessão novamente."
        return None
    st.session_state[USER_KEY] = user
    return user


def user() -> CurrentUser:
    return st.session_state[USER_KEY]


def start_session(token: str, user_: CurrentUser) -> None:
    st.session_state[TOKEN_KEY] = token
    st.session_state[USER_KEY] = user_


def end_session() -> None:
    token = st.session_state.get(TOKEN_KEY)
    current = st.session_state.get(USER_KEY)
    if token:
        with session_scope() as session:
            auth.logout(session, token, current)
    for key in list(st.session_state.keys()):
        if key.startswith("mf_"):
            del st.session_state[key]


def run(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, DomainError | None]:
    """Executa um serviço numa transação. Devolve (resultado, None) ou (None, erro de negócio).

    Em caso de erro faz-se rollback. Chamar `st.rerun()` só depois desta função devolver.
    """
    try:
        with session_scope() as session:
            return fn(session, *args, **kwargs), None
    except DomainError as exc:
        return None, exc


def show_error(error: DomainError) -> None:
    if isinstance(error, ValidationError):
        for message in error.errors:
            st.error(message)
    else:
        st.error(str(error))
