"""Administração técnica: contas, códigos de recuperação e registo de auditoria."""

import pandas as pd
import streamlit as st

from app.db.session import session_scope
from app.domain.labels import DEPARTMENT_LABELS
from app.domain.permissions import Permission, has_permission
from app.services import audit, auth, users
from app.ui import state
from app.ui.format import fmt_dt

NO_DEPARTMENT = "(nenhum, só administrador técnico)"
DEPARTMENT_BY_LABEL = {NO_DEPARTMENT: None, **{label: dept for dept, label in DEPARTMENT_LABELS.items()}}


def render() -> None:
    st.header("Administração")
    current = state.user()
    if not has_permission(current, Permission.MANAGE_USERS):
        st.info("Esta área é só para o administrador técnico.")
        return
    st.caption(
        "O administrador técnico gere contas e consulta a auditoria. Não tem autoridade para "
        "aprovar materiais: essa competência pertence só a Dados Mestre."
    )
    tab_users, tab_reset, tab_audit = st.tabs(["Utilizadores", "Recuperação de palavra-passe", "Auditoria"])
    with tab_users:
        _users_tab()
    with tab_reset:
        _reset_tab()
    with tab_audit:
        _audit_tab()


def _users_tab() -> None:
    current = state.user()
    with session_scope() as session:
        rows = users.list_users(session, current)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Utilizador": u.username,
                    "Nome": u.full_name,
                    "Email": u.email,
                    "Departamento": DEPARTMENT_LABELS.get(u.department, "—") if u.department else "—",
                    "Administrador": "Sim" if u.is_admin else "Não",
                    "Ativo": "Sim" if u.is_active else "Não",
                    "Último acesso": fmt_dt(u.last_login_at),
                }
                for u in rows
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Nova conta")
    with st.form("create_user", clear_on_submit=False):
        c1, c2 = st.columns(2)
        username = c1.text_input("Nome de utilizador", help="Minúsculas, números, ponto, hífen ou _")
        full_name = c2.text_input("Nome completo")
        c3, c4 = st.columns(2)
        email = c3.text_input("Email")
        department = c4.selectbox("Departamento", list(DEPARTMENT_BY_LABEL), index=1)
        is_admin = st.checkbox("Administrador técnico")
        password = st.text_input("Palavra-passe inicial", type="password", autocomplete="new-password")
        st.caption("O utilizador terá de a alterar no primeiro acesso.")
        go = st.form_submit_button("Criar conta", type="primary")
    if go:
        _, error = state.run(
            users.create_user, current,
            username=username, full_name=full_name, email=email, password=password,
            department=DEPARTMENT_BY_LABEL[department], is_admin=is_admin,
        )
        if error is not None:
            state.show_error(error)
        else:
            st.success(f"Conta «{username.strip().lower()}» criada.")
            st.rerun()

    st.subheader("Alterar conta")
    if not rows:
        return
    by_name = {u.username: u for u in rows}
    pick = st.selectbox("Conta", list(by_name), key="admin_edit_pick")
    target = by_name[pick]
    labels = list(DEPARTMENT_BY_LABEL)
    current_label = DEPARTMENT_LABELS[target.department] if target.department else NO_DEPARTMENT
    with st.form(f"edit_user_{target.id}"):
        dept_label = st.selectbox("Departamento", labels, index=labels.index(current_label))
        admin_flag = st.checkbox("Administrador técnico", value=target.is_admin)
        active_flag = st.checkbox("Conta ativa", value=target.is_active)
        saved = st.form_submit_button("Guardar alterações")
    if saved:
        _, error = state.run(
            users.update_user, current, target.id,
            department=DEPARTMENT_BY_LABEL[dept_label], is_admin=admin_flag, is_active=active_flag,
        )
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()


def _reset_tab() -> None:
    current = state.user()
    st.write(
        "Gere um código de uso único para um utilizador que esqueceu a palavra-passe. "
        "Entregue-o por um canal seguro (por exemplo, pessoalmente ou por telefone). "
        "Não há envio automático por email."
    )
    with session_scope() as session:
        rows = users.list_users(session, current)
    by_name = {u.username: u for u in rows if u.is_active}
    if not by_name:
        st.info("Não há contas ativas.")
        return
    pick = st.selectbox("Utilizador", list(by_name), key="reset_pick")
    if st.button("Gerar código de recuperação"):
        token, error = state.run(auth.issue_reset_token, current, by_name[pick].id)
        if error is not None:
            state.show_error(error)
        else:
            st.success("Código gerado. Só é mostrado agora e expira em poucos minutos.")
            st.code(token, language=None)


def _audit_tab() -> None:
    current = state.user()
    if not has_permission(current, Permission.VIEW_AUDIT_LOG):
        st.info("Sem permissão para consultar a auditoria.")
        return
    action = st.text_input("Filtrar por ação", placeholder="Por exemplo ESTADO_ALTERADO", key="audit_action")
    with session_scope() as session:
        entries = audit.list_entries(session, current, limit=300, action=action.strip() or None)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Data": fmt_dt(e.occurred_at),
                    "Utilizador": e.username or "",
                    "Ação": e.action,
                    "Entidade": f"{e.entity_type or ''} {e.entity_id or ''}".strip(),
                    "Detalhes": str(e.details) if e.details else "",
                }
                for e in entries
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
