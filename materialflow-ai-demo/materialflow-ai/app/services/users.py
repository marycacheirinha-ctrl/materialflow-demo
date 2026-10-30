"""Gestão de contas (apenas administrador técnico). Não atribui autoridade sobre materiais."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import User
from app.domain.enums import Department
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.domain.permissions import Permission, require_permission
from app.security import passwords
from app.security.password_policy import validate_password_strength
from app.services import audit, auth
from app.services.dto import CurrentUser
from app.utils import clock

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_user(
    session: Session,
    admin: CurrentUser,
    *,
    username: str,
    full_name: str,
    email: str,
    password: str,
    department: Department | None,
    is_admin: bool = False,
    must_change_password: bool = True,
) -> User:
    require_permission(admin, Permission.MANAGE_USERS)
    uname = auth.normalize_username(username)
    errors: list[str] = []
    if not _USERNAME.match(uname):
        errors.append("O nome de utilizador deve ter 3 a 64 caracteres (letras minúsculas, números, ponto, hífen ou _).")
    name = " ".join((full_name or "").split())
    if not name:
        errors.append("O nome completo é obrigatório.")
    mail = (email or "").strip().lower()
    if not _EMAIL.match(mail):
        errors.append("O email não é válido.")
    if department is None and not is_admin:
        errors.append("Atribua um departamento ou o perfil de administrador técnico.")
    errors += validate_password_strength(password, username=uname)
    if errors:
        raise ValidationError(errors)
    if session.scalar(select(User.id).where(User.username == uname)):
        raise ConflictError("Já existe um utilizador com esse nome.")
    if session.scalar(select(User.id).where(User.email == mail)):
        raise ConflictError("Já existe um utilizador com esse email.")

    now = clock.now()
    user = User(
        username=uname,
        full_name=name,
        email=mail,
        password_hash=passwords.hash_password(password),
        department=department,
        is_admin=is_admin,
        must_change_password=must_change_password,
        password_changed_at=now,
    )
    session.add(user)
    session.flush()
    audit.record(
        session,
        "UTILIZADOR_CRIADO",
        actor=admin,
        entity_type="user",
        entity_id=user.id,
        details={"username": uname, "department": department, "is_admin": is_admin},
    )
    return user


def list_users(session: Session, admin: CurrentUser) -> list[User]:
    require_permission(admin, Permission.MANAGE_USERS)
    return list(session.scalars(select(User).order_by(User.username)))


def _active_admin_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True), User.is_active.is_(True))) or 0


def update_user(
    session: Session,
    admin: CurrentUser,
    user_id: int,
    *,
    department: Department | None,
    is_admin: bool,
    is_active: bool,
) -> User:
    require_permission(admin, Permission.MANAGE_USERS)
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("Utilizador inexistente.")
    if department is None and not is_admin:
        raise ValidationError("Atribua um departamento ou o perfil de administrador técnico.")
    losing_admin = user.is_admin and user.is_active and (not is_admin or not is_active)
    if losing_admin and _active_admin_count(session) <= 1:
        raise ConflictError("Tem de existir pelo menos um administrador técnico ativo.")
    if user.id == admin.id and not is_active:
        raise ConflictError("Não pode desativar a sua própria conta.")

    before = {"department": user.department, "is_admin": user.is_admin, "is_active": user.is_active}
    user.department, user.is_admin, user.is_active = department, is_admin, is_active
    if not is_active or before["department"] != department or before["is_admin"] != is_admin:
        auth.revoke_all_sessions(session, user.id)
    audit.record(
        session,
        "UTILIZADOR_ALTERADO",
        actor=admin,
        entity_type="user",
        entity_id=user.id,
        details={"antes": before, "depois": {"department": department, "is_admin": is_admin, "is_active": is_active}},
    )
    return user
