"""Categorias de componentes e respetivos campos técnicos sugeridos."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CategoryField, ComponentCategory

# Campos sugeridos por categoria (do enunciado). Só os rótulos: nunca há valores pré-preenchidos.
DEFAULT_CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "RESISTENCIA": ("Resistência", ["Potência", "Tensão", "Material", "Comprimento", "Tipo de ligação"]),
    "ELETROVALVULA": (
        "Eletroválvula",
        ["Número de vias", "Tensão", "Frequência", "Tipo de ligação", "Pressão de trabalho"],
    ),
    "TUBO": (
        "Tubo",
        ["Material", "Diâmetro interior", "Diâmetro exterior", "Comprimento", "Temperatura de trabalho"],
    ),
    "MOTOR": ("Motor", ["Potência", "Tensão", "Frequência", "Velocidade", "Tipo de alimentação"]),
    "SENSOR": (
        "Sensor",
        ["Tipo", "Função", "Gama de medição", "Resistência nominal", "Tipo de conector"],
    ),
    "OUTRO": ("Outro componente", []),
}


def ensure_default_categories(session: Session) -> int:
    """Cria as categorias em falta (idempotente). Devolve quantas criou."""
    existing = {c.code: c for c in session.scalars(select(ComponentCategory).options(selectinload(ComponentCategory.fields)))}
    created = 0
    for code, (name, labels) in DEFAULT_CATEGORIES.items():
        category = existing.get(code)
        if category is None:
            category = ComponentCategory(code=code, name_pt=name)
            session.add(category)
            created += 1
            known: set[str] = set()
        else:
            known = {f.label for f in category.fields}
        for order, label in enumerate(labels):
            if label not in known:
                category.fields.append(CategoryField(label=label, sort_order=order))
    session.flush()
    return created


def list_categories(session: Session) -> list[ComponentCategory]:
    return list(
        session.scalars(
            select(ComponentCategory)
            .where(ComponentCategory.is_active.is_(True))
            .options(selectinload(ComponentCategory.fields))
            .order_by(ComponentCategory.name_pt)
        )
    )
