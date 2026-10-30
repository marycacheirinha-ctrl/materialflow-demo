import streamlit as st

from app.db.session import session_scope
from app.domain.permissions import Permission, has_permission
from app.services import categories, requests
from app.ui import state


def render() -> None:
    st.header("Nova peça")
    current = state.user()
    if not has_permission(current, Permission.REQUEST_CREATE):
        st.info("Só os utilizadores de Técnicos / Logística podem criar novas solicitações.")
        return

    with session_scope() as session:
        cats = categories.list_categories(session)
    options = {c.name_pt: c.id for c in cats}

    st.write(
        "Descreva a peça com o que sabe. A solicitação fica em rascunho e só segue para Compras "
        "quando a submeter."
    )
    with st.form("new_request"):
        original = st.text_area(
            "Descrição original *",
            height=100,
            max_chars=2000,
            help="Como a peça é conhecida hoje, tal como está na etiqueta, no catálogo ou na avaria.",
        )
        category_name = st.selectbox("Categoria do componente", ["(por identificar)", *options])
        col1, col2, col3 = st.columns(3)
        brand = col1.text_input("Marca", max_chars=100, help="Preencha só quando for relevante.")
        model = col2.text_input("Modelo", max_chars=100)
        reference = col3.text_input("Referência do fabricante", max_chars=100)
        submitted = st.form_submit_button("Criar rascunho", type="primary")

    if submitted:
        data = {
            "original_description": original,
            "category_id": options.get(category_name),
            "brand": brand,
            "model": model,
            "manufacturer_reference": reference,
        }
        req, error = state.run(requests.create_request, current, data)
        if error is not None:
            state.show_error(error)
        else:
            st.session_state[state.SELECTED_KEY] = req.id
            st.success(
                f"Rascunho {req.internal_code} criado. Abra «Materiais e solicitações» para "
                "acrescentar fotografias, características e descritivos."
            )
