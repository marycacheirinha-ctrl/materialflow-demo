"""Materiais e solicitações: lista, detalhe por separadores e ações de workflow."""

import pandas as pd
import streamlit as st

from app.db.session import session_scope
from app.domain import access
from app.domain.enums import AttachmentKind, RequestStatus
from app.domain.errors import NotFoundError
from app.domain.labels import ATTACHMENT_KIND_LABELS, SOURCE_LABELS, STATUS_LABELS
from app.domain.workflow import SAP_EDITABLE_STATUSES
from app.services import categories, requests
from app.ui import state
from app.ui.format import dash, fmt_date, fmt_dec, fmt_dt, status_badge

SOURCE_BY_LABEL = {label: source for source, label in SOURCE_LABELS.items()}
STATUS_FILTER = {"Todos os estados": None, **{label: status for status, label in STATUS_LABELS.items()}}


def render() -> None:
    st.header("Materiais e solicitações")
    current = state.user()

    col_a, col_b = st.columns([1, 2])
    status_label = col_a.selectbox("Estado", list(STATUS_FILTER))
    search = col_b.text_input("Pesquisar", placeholder="Código, descrição, referência ou código SAP")

    with session_scope() as session:
        items = requests.list_requests(session, current, status=STATUS_FILTER[status_label], search=search)

    if not items:
        st.info("Não há solicitações para mostrar com estes filtros.")
        return

    table = pd.DataFrame(
        [
            {
                "Código": r.internal_code,
                "Estado": STATUS_LABELS[r.status],
                "Descritivo PT-PT": r.description_pt or "",
                "Descrição original": (r.original_description or "")[:80],
                "Autor": r.created_by.full_name,
                "Atualizada": fmt_dt(r.updated_at),
            }
            for r in items
        ]
    )
    st.dataframe(table, hide_index=True, use_container_width=True)

    ids = [r.id for r in items]
    preselected = st.session_state.get(state.SELECTED_KEY)
    index = ids.index(preselected) if preselected in ids else 0
    labels = {r.id: f"{r.internal_code}  {r.description_pt or r.original_description[:50]}" for r in items}
    chosen = st.selectbox("Abrir solicitação", ids, index=index, format_func=labels.get, key="mf_open_select")
    st.session_state[state.SELECTED_KEY] = chosen
    st.divider()
    _detail(chosen)


# --------------------------------------------------------------------- detalhe

def _detail(request_id: int) -> None:
    current = state.user()
    try:
        with session_scope() as session:
            req = requests.get_request(session, current, request_id)
            category_list = categories.list_categories(session)
            transitions = requests.available_transitions(current, req)
    except NotFoundError as exc:
        st.error(str(exc))
        return

    can_tech = access.can_edit_technical(current, status=req.status, created_by_id=req.created_by_id)
    can_comm = access.can_edit_commercial(current, status=req.status)
    can_sap = access.can_edit_sap_fields(current, status=req.status)

    st.markdown(
        f'<span class="mf-code">{req.internal_code}</span> &nbsp; {status_badge(req.status)}',
        unsafe_allow_html=True,
    )
    st.subheader(req.description_pt or "Sem descritivo ainda")
    if req.description_en:
        st.caption(req.description_en)

    if req.status == RequestStatus.DEVOLVIDO_PARA_CORRECAO:
        returned = [h for h in req.history if h.to_status == RequestStatus.DEVOLVIDO_PARA_CORRECAO]
        if returned and returned[-1].note:
            st.warning("Devolvida para correção. Observações:")
            st.text(returned[-1].note)

    _actions(request_id, transitions)

    tabs = st.tabs(["Identificação", "Características", "Anexos", "Comercial", "Logística", "SAP", "Histórico"])
    with tabs[0]:
        _tab_identification(req, category_list, can_tech)
    with tabs[1]:
        _tab_characteristics(req, can_tech)
    with tabs[2]:
        _tab_attachments(req, can_tech)
    with tabs[3]:
        _tab_commercial(req, can_comm)
    with tabs[4]:
        _tab_logistics(req, can_tech)
    with tabs[5]:
        _tab_sap(req, can_sap)
    with tabs[6]:
        _tab_history(req)


def _actions(request_id: int, transitions) -> None:
    if not transitions:
        return
    needs_code = any(t.target == RequestStatus.CONCLUIDO_NO_SAP for t in transitions)
    chosen = None
    with st.form(f"actions_{request_id}"):
        note = st.text_area("Observações", height=80, key=f"note_{request_id}", max_chars=2000)
        code = None
        if needs_code:
            code = st.text_input(
                "Código do material criado no SAP",
                key=f"sapcode_{request_id}",
                max_chars=40,
                help="Introduza o código atribuído pelo SAP depois de criar o material. Nunca é gerado aqui.",
            )
        columns = st.columns(len(transitions))
        for column, step in zip(columns, transitions, strict=True):
            with column:
                if st.form_submit_button(step.label, use_container_width=True):
                    chosen = step
    if chosen is not None:
        _, error = state.run(
            requests.transition, state.user(), request_id, chosen.target, note=note, sap_code=code
        )
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()


def _readonly(label: str, value) -> None:
    st.caption(label)
    st.text(dash(value))


def _tab_identification(req, category_list, can_edit: bool) -> None:
    if not can_edit:
        _readonly("Descrição original", req.original_description)
        c1, c2, c3 = st.columns(3)
        with c1:
            _readonly("Categoria", req.category.name_pt if req.category else None)
            _readonly("Marca", req.brand)
        with c2:
            _readonly("Modelo", req.model)
            _readonly("Referência do fabricante", req.manufacturer_reference)
        with c3:
            _readonly(f"Descritivo PT-PT ({len(req.description_pt or '')}/40)", req.description_pt)
            _readonly(f"Descritivo EN ({len(req.description_en or '')}/40)", req.description_en)
        return

    names = {c.name_pt: c.id for c in category_list}
    options = ["(por identificar)", *names]
    current_name = req.category.name_pt if req.category and req.category.name_pt in names else "(por identificar)"
    with st.form(f"ident_{req.id}"):
        original = st.text_area("Descrição original *", value=req.original_description, height=90, max_chars=2000)
        category = st.selectbox("Categoria do componente", options, index=options.index(current_name))
        c1, c2, c3 = st.columns(3)
        brand = c1.text_input("Marca", value=req.brand or "", max_chars=100)
        model = c2.text_input("Modelo", value=req.model or "", max_chars=100)
        reference = c3.text_input("Referência do fabricante", value=req.manufacturer_reference or "", max_chars=100)
        st.markdown("**Descritivos normalizados**")
        st.caption(
            "Máximo de 40 caracteres, incluindo espaços. São guardados em maiúsculas e sem ponto final. "
            "Se passar do limite, escreva uma versão mais curta: o texto nunca é cortado automaticamente."
        )
        d1, d2 = st.columns(2)
        pt = d1.text_input("Descritivo PT-PT", value=req.description_pt or "", help="Exemplo: ELETROVÁLVULA 2 VIAS")
        en = d2.text_input("Descritivo EN", value=req.description_en or "", help="Exemplo: 2-WAY SOLENOID VALVE")
        saved = st.form_submit_button("Guardar", type="primary")
    st.caption(
        "A sugestão automática de descritivos por IA será ativada na fase seguinte. "
        "Por agora os descritivos são escritos manualmente."
    )
    if saved:
        data = {
            "original_description": original,
            "category_id": names.get(category),
            "brand": brand,
            "model": model,
            "manufacturer_reference": reference,
            "description_pt": pt,
            "description_en": en,
        }
        _, error = state.run(requests.update_technical, state.user(), req.id, data)
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()


def _tab_characteristics(req, can_edit: bool) -> None:
    rows = [
        {
            "Característica": c.label,
            "Valor": c.value or "",
            "Unidade": c.unit or "",
            "Origem": SOURCE_LABELS[c.source] if c.source else "",
        }
        for c in req.characteristics
    ]
    frame = pd.DataFrame(rows, columns=["Característica", "Valor", "Unidade", "Origem"])
    if not can_edit:
        if frame.empty:
            st.info("Ainda não há características registadas.")
        else:
            st.dataframe(frame.replace("", "não identificado"), hide_index=True, use_container_width=True)
        return

    st.caption(
        "Deixe o valor vazio quando não estiver confirmado: fica como «não identificado». "
        "Nunca preencha valores por dedução. Quando há valor, indique de onde vem."
    )
    if req.category and st.button("Acrescentar campos sugeridos da categoria", key=f"tpl_{req.id}"):
        added, error = state.run(requests.apply_category_template, state.user(), req.id)
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()
    edited = st.data_editor(
        frame,
        key=f"chars_{req.id}",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "Origem": st.column_config.SelectboxColumn("Origem", options=list(SOURCE_BY_LABEL), required=False),
        },
    )
    if st.button("Guardar características", type="primary", key=f"save_chars_{req.id}"):
        payload = []
        for record in edited.to_dict("records"):
            clean = {k: ("" if pd.isna(v) else v) for k, v in record.items()}
            payload.append(
                {
                    "label": clean["Característica"],
                    "value": clean["Valor"],
                    "unit": clean["Unidade"],
                    "source": SOURCE_BY_LABEL.get(clean["Origem"], clean["Origem"] or None),
                }
            )
        _, error = state.run(requests.set_characteristics, state.user(), req.id, payload)
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()


def _tab_attachments(req, can_edit: bool) -> None:
    if not req.attachments:
        st.info("Ainda não há fotografias nem fichas técnicas.")
    for attachment in req.attachments:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            left.markdown(
                f"**{ATTACHMENT_KIND_LABELS[attachment.kind]}**  \n"
                f"{attachment.original_filename}  ·  {attachment.size_bytes / 1024:.0f} KB"
            )
            try:
                with session_scope() as session:
                    _, data = requests.read_attachment(session, state.user(), req.id, attachment.id)
            except (NotFoundError, FileNotFoundError):
                st.error("O ficheiro não está disponível no armazenamento.")
                continue
            if attachment.kind == AttachmentKind.FOTOGRAFIA:
                st.image(data, width=260)
            else:
                st.download_button(
                    "Descarregar PDF", data, file_name=attachment.original_filename,
                    mime="application/pdf", key=f"dl_{attachment.id}",
                )
            if can_edit and right.button("Remover", key=f"rm_{attachment.id}"):
                _, error = state.run(requests.remove_attachment, state.user(), req.id, attachment.id)
                if error is not None:
                    state.show_error(error)
                else:
                    st.rerun()

    if not can_edit:
        return
    counter = st.session_state.get(f"mf_up_{req.id}", 0)
    with st.form(f"upload_{req.id}_{counter}"):
        photos = st.file_uploader("Fotografias (JPG, PNG ou WEBP)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        sheets = st.file_uploader("Fichas técnicas (PDF)", type=["pdf"], accept_multiple_files=True)
        go = st.form_submit_button("Carregar ficheiros", type="primary")
    if go:
        problems, done = [], 0
        for kind, files in ((AttachmentKind.FOTOGRAFIA, photos), (AttachmentKind.FICHA_TECNICA, sheets)):
            for uploaded in files or []:
                _, error = state.run(requests.add_attachment, state.user(), req.id, kind, uploaded.name, uploaded.getvalue())
                if error is not None:
                    problems.append(f"{uploaded.name}: {error}")
                else:
                    done += 1
        for message in problems:
            st.error(message)
        if done and not problems:
            st.session_state[f"mf_up_{req.id}"] = counter + 1
            st.rerun()
        elif done:
            st.success(f"{done} ficheiro(s) carregado(s). Corrija os restantes e tente novamente.")


def _tab_commercial(req, can_edit: bool) -> None:
    if not req.offers:
        st.info("Ainda não há fornecedores registados.")
    for offer in req.offers:
        title = f"{offer.supplier_name}  ·  {fmt_dec(offer.purchase_price)} {offer.currency or ''}".strip()
        with st.expander(title):
            if can_edit:
                _offer_form(req.id, offer)
            else:
                _readonly("Referência do fornecedor", offer.supplier_reference)
                _readonly("Preço de compra", f"{fmt_dec(offer.purchase_price)} {offer.currency or ''}".strip())
                _readonly("Unidade de compra", offer.purchase_unit)
                _readonly("Quantidade por embalagem", fmt_dec(offer.quantity_per_package))
                _readonly("Validade do preço", fmt_date(offer.price_valid_until))
                _readonly("Referência do preço", offer.price_reference)
                _readonly("Notas", offer.notes)
    if can_edit:
        st.markdown("**Novo fornecedor**")
        _offer_form(req.id, None)


def _offer_form(request_id: int, offer) -> None:
    key = f"offer_{request_id}_{offer.id if offer else 'new'}"
    with st.form(key):
        c1, c2 = st.columns(2)
        name = c1.text_input("Fornecedor *", value=offer.supplier_name if offer else "", max_chars=150)
        reference = c2.text_input("Referência do fornecedor", value=(offer.supplier_reference or "") if offer else "", max_chars=100)
        c3, c4, c5, c6 = st.columns(4)
        price = c3.text_input("Preço de compra", value=fmt_dec(offer.purchase_price) if offer else "")
        currency = c4.text_input("Moeda", value=(offer.currency or "EUR") if offer else "EUR", max_chars=3)
        unit = c5.text_input("Unidade de compra", value=(offer.purchase_unit or "") if offer else "", max_chars=10)
        package = c6.text_input("Qtd. por embalagem", value=fmt_dec(offer.quantity_per_package) if offer else "")
        c7, c8 = st.columns(2)
        valid = c7.date_input("Validade do preço", value=offer.price_valid_until if offer else None, format="DD/MM/YYYY")
        price_ref = c8.text_input("Referência do preço", value=(offer.price_reference or "") if offer else "", max_chars=100)
        notes = st.text_input("Notas", value=(offer.notes or "") if offer else "", max_chars=255)
        buttons = st.columns([1, 1, 3])
        save = buttons[0].form_submit_button("Guardar", type="primary")
        remove = buttons[1].form_submit_button("Remover") if offer else False
    data = {
        "supplier_name": name, "supplier_reference": reference, "purchase_price": price, "currency": currency,
        "purchase_unit": unit, "quantity_per_package": package, "price_valid_until": valid,
        "price_reference": price_ref, "notes": notes,
    }
    if save:
        if offer:
            _, error = state.run(requests.update_offer, state.user(), request_id, offer.id, data)
        else:
            _, error = state.run(requests.add_offer, state.user(), request_id, data)
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()
    if remove:
        _, error = state.run(requests.remove_offer, state.user(), request_id, offer.id)
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()


def _tab_logistics(req, can_edit: bool) -> None:
    st.caption("O peso indicado é o da peça, não o da embalagem.")
    if not can_edit:
        c1, c2, c3 = st.columns(3)
        with c1:
            _readonly("Peso líquido unitário", f"{fmt_dec(req.net_weight)} {req.weight_unit or ''}".strip() if req.net_weight is not None else None)
            _readonly("Peso bruto", fmt_dec(req.gross_weight) if req.gross_weight is not None else None)
        with c2:
            _readonly("Comprimento", fmt_dec(req.length) if req.length is not None else None)
            _readonly("Largura", fmt_dec(req.width) if req.width is not None else None)
            _readonly("Altura", fmt_dec(req.height) if req.height is not None else None)
        with c3:
            _readonly("Unidade de medida", req.dimension_unit)
            _readonly("Unidade base", req.base_unit)
        return
    with st.form(f"logistics_{req.id}"):
        c1, c2, c3 = st.columns(3)
        net = c1.text_input("Peso líquido unitário", value=fmt_dec(req.net_weight))
        gross = c2.text_input("Peso bruto (se disponível)", value=fmt_dec(req.gross_weight))
        weight_unit = c3.text_input("Unidade de peso", value=req.weight_unit or "", max_chars=10, help="Por exemplo KG ou G")
        c4, c5, c6, c7 = st.columns(4)
        length = c4.text_input("Comprimento", value=fmt_dec(req.length))
        width = c5.text_input("Largura", value=fmt_dec(req.width))
        height = c6.text_input("Altura", value=fmt_dec(req.height))
        dim_unit = c7.text_input("Unidade de medida", value=req.dimension_unit or "", max_chars=10, help="Por exemplo MM ou CM")
        base_unit = st.text_input("Unidade base", value=req.base_unit or "", max_chars=10, help="Por exemplo UN")
        saved = st.form_submit_button("Guardar", type="primary")
    if saved:
        data = {
            "net_weight": net, "gross_weight": gross, "weight_unit": weight_unit, "length": length,
            "width": width, "height": height, "dimension_unit": dim_unit, "base_unit": base_unit,
        }
        _, error = state.run(requests.update_technical, state.user(), req.id, data)
        if error is not None:
            state.show_error(error)
        else:
            st.rerun()


def _tab_sap(req, can_edit: bool) -> None:
    _readonly("ID interno da solicitação", req.internal_code)
    _readonly("Código de material SAP", req.sap_material_code)
    st.caption("O código SAP nunca é gerado aqui. Fica vazio até o material ser criado no SAP.")
    if can_edit:
        with st.form(f"sap_{req.id}"):
            c1, c2 = st.columns(2)
            mtype = c1.text_input("Tipo de material", value=req.sap_material_type or "", max_chars=10)
            group = c2.text_input("Grupo de mercadorias", value=req.sap_material_group or "", max_chars=20)
            c3, c4, c5 = st.columns(3)
            base = c3.text_input("Unidade base", value=req.base_unit or "", max_chars=10)
            plant = c4.text_input("Centro", value=req.sap_plant or "", max_chars=10)
            org = c5.text_input("Organização de compras", value=req.sap_purchasing_org or "", max_chars=10)
            saved = st.form_submit_button("Guardar campos SAP", type="primary")
        if saved:
            data = {"sap_material_type": mtype, "sap_material_group": group, "base_unit": base, "sap_plant": plant, "sap_purchasing_org": org}
            _, error = state.run(requests.update_sap_fields, state.user(), req.id, data)
            if error is not None:
                state.show_error(error)
            else:
                st.rerun()
        st.info(
            "A deteção automática de duplicados será ativada na fase seguinte. Até lá, confirme "
            "manualmente no SAP que o material ainda não existe antes de aprovar."
        )
    else:
        c1, c2 = st.columns(2)
        with c1:
            _readonly("Tipo de material", req.sap_material_type)
            _readonly("Unidade base", req.base_unit)
            _readonly("Organização de compras", req.sap_purchasing_org)
        with c2:
            _readonly("Grupo de mercadorias", req.sap_material_group)
            _readonly("Centro", req.sap_plant)
    if req.status in SAP_EDITABLE_STATUSES:
        problems = requests.validation_problems(req, RequestStatus.APROVADO_PARA_SAP)
        if problems:
            st.markdown("**Ainda falta para poder aprovar:**")
            for problem in problems:
                st.text(f"• {problem}")


def _tab_history(req) -> None:
    if not req.history:
        st.info("Sem histórico.")
    for entry in reversed(req.history):
        who = entry.user.full_name
        if entry.event_type.value == "TRANSICAO":
            origin = STATUS_LABELS[entry.from_status] if entry.from_status else "—"
            headline = f"{fmt_dt(entry.occurred_at)}  ·  {who}  ·  {origin} → {STATUS_LABELS[entry.to_status]}"
        elif entry.event_type.value == "CRIACAO":
            headline = f"{fmt_dt(entry.occurred_at)}  ·  {who}  ·  Solicitação criada"
        else:
            headline = f"{fmt_dt(entry.occurred_at)}  ·  {who}  ·  Alteração"
        with st.container(border=True):
            st.text(headline)
            if entry.note:
                st.text(f"Observações: {entry.note}")
            if entry.changes:
                with st.expander("Ver alterações"):
                    st.json(entry.changes, expanded=True)
