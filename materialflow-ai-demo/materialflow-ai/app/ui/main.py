"""Ponto de entrada da aplicação Streamlit: streamlit run app/ui/main.py"""

import logging
import sys
from pathlib import Path

# Permite `streamlit run app/ui/main.py` sem instalar o pacote.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app import demo  # noqa: E402
from app.config import ConfigError, get_settings  # noqa: E402
from app.domain.labels import DEPARTMENT_LABELS  # noqa: E402
from app.domain.permissions import Permission, has_permission  # noqa: E402
from app.logging_setup import configure_logging  # noqa: E402
from app.ui import state, theme  # noqa: E402
from app.ui.views import account, admin, login, new_request, placeholders, requests_view  # noqa: E402

log = logging.getLogger("materialflow.ui")


def _pages(user) -> list:
    pages = []
    if has_permission(user, Permission.REQUEST_CREATE):
        pages.append(st.Page(new_request.render, title="Nova peça", icon=":material/add_box:", url_path="nova-peca", default=True))
        pages.append(st.Page(placeholders.batch_import, title="Importação em lote", icon=":material/upload_file:", url_path="importacao"))
    if user.department is not None:
        pages.append(
            st.Page(
                requests_view.render,
                title="Materiais e solicitações",
                icon=":material/inventory_2:",
                url_path="solicitacoes",
                default=not pages,
            )
        )
        pages.append(st.Page(placeholders.dictionary, title="Dicionário técnico", icon=":material/menu_book:", url_path="dicionario"))
    if has_permission(user, Permission.MANAGE_USERS):
        pages.append(st.Page(admin.render, title="Administração", icon=":material/admin_panel_settings:", url_path="administracao", default=not pages))
    pages.append(st.Page(account.render, title="A minha conta", icon=":material/lock:", url_path="conta"))
    return pages


@st.cache_resource(show_spinner="A preparar a demonstração...")
def _prepare_demo() -> bool:
    demo.ensure_ready()
    return True


def main() -> None:
    st.set_page_config(page_title="MaterialFlow AI", page_icon=":material/inventory_2:", layout="wide")
    theme.inject()
    try:
        settings = get_settings()
        configure_logging(settings.log_level)
        if settings.demo_mode:
            _prepare_demo()
        user = state.resolve_current_user()
    except ConfigError as exc:
        st.error(f"Configuração em falta: {exc}")
        st.stop()
    except Exception:
        log.exception("Falha ao validar a sessão")
        st.error(
            "Não foi possível ligar à base de dados. Tente novamente dentro de instantes "
            "ou contacte o administrador."
        )
        st.stop()

    if user is None:
        login.render()
        return
    if user.must_change_password:
        account.render_forced_change(user)
        return

    navigation = st.navigation(_pages(user))
    with st.sidebar:
        st.markdown(f"**{user.full_name}**")
        if user.department:
            st.caption(DEPARTMENT_LABELS[user.department])
        elif user.is_admin:
            st.caption("Administrador técnico")
        if settings.demo_mode:
            st.warning("Demonstração com dados fictícios. Os dados apagam-se quando a aplicação reinicia.")
        if st.button("Terminar sessão", use_container_width=True):
            state.end_session()
            st.rerun()
    navigation.run()


main()
