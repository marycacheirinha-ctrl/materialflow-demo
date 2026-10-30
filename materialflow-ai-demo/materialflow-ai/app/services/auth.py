"""Autenticação, sessões, bloqueio por tentativas repetidas e recuperação de palavra-passe."""

import datetime as dt

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import LoginAttempt, PasswordResetToken, User, UserSession
from app.domain.errors import AccountLockedError, AuthenticationError, ValidationError
from app.security import passwords
from app.security.password_policy import validate_password_strength
from app.security.tokens import generate_token, hash_token
from app.services import audit
from app.services.dto import CurrentUser
from app.utils import clock

GENERIC_LOGIN_ERROR = "Nome de utilizador ou palavra-passe incorretos."


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def to_current_user(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        department=user.department,
        is_admin=user.is_admin,
        must_change_password=user.must_change_password,
    )


def _lock_state(session: Session, username: str) -> int | None:
    """Minutos restantes de bloqueio, ou None se a conta não estiver bloqueada.

    Contam-se as falhas desde o último login com sucesso, dentro da janela. O bloqueio dura
    `lockout_minutes` a partir da última falha. Funciona também para utilizadores inexistentes
    (as tentativas são por nome), para não permitir descobrir que contas existem.
    """
    s = get_settings()
    now = clock.now()
    window = dt.timedelta(minutes=max(s.failed_login_window_minutes, s.lockout_minutes))
    since = now - window
    last_success = session.scalar(
        select(func.max(LoginAttempt.attempted_at)).where(
            LoginAttempt.username == username, LoginAttempt.succeeded.is_(True)
        )
    )
    if last_success and last_success > since:
        since = last_success
    failures = list(
        session.scalars(
            select(LoginAttempt.attempted_at)
            .where(
                LoginAttempt.username == username,
                LoginAttempt.succeeded.is_(False),
                LoginAttempt.attempted_at > since,
            )
            .order_by(LoginAttempt.attempted_at)
        )
    )
    if len(failures) < s.max_failed_logins:
        return None
    unlock_at = failures[-1] + dt.timedelta(minutes=s.lockout_minutes)
    if now >= unlock_at:
        return None
    return max(1, int((unlock_at - now).total_seconds() // 60) + 1)


def authenticate(session: Session, username: str, password: str) -> tuple[CurrentUser, str]:
    """Valida as credenciais e cria uma sessão. Devolve o utilizador e o token de sessão."""
    uname = normalize_username(username)
    remaining = _lock_state(session, uname)
    if remaining is not None:
        audit.record(session, "LOGIN_BLOQUEADO", username=uname)
        session.commit()  # o registo tem de persistir apesar da exceção (o chamador faria rollback)
        raise AccountLockedError(remaining)

    user = session.scalar(select(User).where(User.username == uname))
    # Verifica sempre um hash (real ou fictício) para igualar o tempo de resposta.
    hash_to_check = user.password_hash if user else passwords.dummy_hash()
    password_ok = passwords.verify_password(hash_to_check, password or "")

    if user is None or not user.is_active or not password_ok:
        session.add(LoginAttempt(username=uname, succeeded=False, attempted_at=clock.now()))
        audit.record(session, "LOGIN_FALHADO", username=uname)
        session.commit()  # sem isto, o rollback do chamador apagaria a tentativa e o bloqueio nunca dispararia
        raise AuthenticationError(GENERIC_LOGIN_ERROR)

    now = clock.now()
    session.add(LoginAttempt(username=uname, succeeded=True, attempted_at=now))
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    user.last_login_at = now

    token = generate_token()
    s = get_settings()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + dt.timedelta(hours=s.session_absolute_hours),
        )
    )
    current = to_current_user(user)
    audit.record(session, "LOGIN", actor=current)
    session.flush()
    return current, token


def resolve_session(session: Session, token: str | None) -> CurrentUser | None:
    """Devolve o utilizador da sessão, ou None se inexistente, revogada ou expirada."""
    if not token:
        return None
    row = session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = clock.now()
    idle = dt.timedelta(minutes=get_settings().session_idle_minutes)
    if now >= row.expires_at or now - row.last_seen_at > idle:
        row.revoked_at = now
        return None
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        row.revoked_at = now
        return None
    row.last_seen_at = now
    return to_current_user(user)


def logout(session: Session, token: str | None, actor: CurrentUser | None = None) -> None:
    if not token:
        return
    row = session.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = clock.now()
        if actor:
            audit.record(session, "LOGOUT", actor=actor)


def revoke_all_sessions(session: Session, user_id: int, *, except_token: str | None = None) -> None:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_token:
        stmt = stmt.where(UserSession.token_hash != hash_token(except_token))
    session.execute(stmt.values(revoked_at=clock.now()))


def change_password(
    session: Session, actor: CurrentUser, current_password: str, new_password: str, *, keep_token: str | None = None
) -> None:
    user = session.get(User, actor.id)
    if user is None or not passwords.verify_password(user.password_hash, current_password or ""):
        raise AuthenticationError("A palavra-passe atual está incorreta.")
    if passwords.verify_password(user.password_hash, new_password):
        raise ValidationError("A nova palavra-passe tem de ser diferente da atual.")
    errors = validate_password_strength(new_password, username=user.username)
    if errors:
        raise ValidationError(errors)
    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = clock.now()
    revoke_all_sessions(session, user.id, except_token=keep_token)
    audit.record(session, "PASSWORD_ALTERADA", actor=actor)


def issue_reset_token(session: Session, admin: CurrentUser, user_id: int) -> str:
    """O administrador gera um código de uso único para o utilizador. Só o hash fica guardado.

    A entrega é feita pelo administrador por um canal seguro. Não há envio automático de email.
    """
    from app.domain.permissions import Permission, require_permission

    require_permission(admin, Permission.MANAGE_USERS)
    user = session.get(User, user_id)
    if user is None:
        raise ValidationError("Utilizador inexistente.")
    now = clock.now()
    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = generate_token(24)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + dt.timedelta(minutes=get_settings().reset_token_minutes),
            issued_by_id=admin.id,
        )
    )
    audit.record(session, "RECUPERACAO_EMITIDA", actor=admin, entity_type="user", entity_id=user.id)
    session.flush()
    return token


def reset_password_with_token(session: Session, username: str, token: str, new_password: str) -> None:
    generic = "Código inválido ou expirado."
    uname = normalize_username(username)
    user = session.scalar(select(User).where(User.username == uname))
    row = session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token or "")))
    now = clock.now()
    if user is None or row is None or row.user_id != user.id or row.used_at is not None or now >= row.expires_at:
        audit.record(session, "RECUPERACAO_FALHADA", username=uname)
        session.commit()
        raise AuthenticationError(generic)
    errors = validate_password_strength(new_password, username=user.username)
    if errors:
        raise ValidationError(errors)
    row.used_at = now
    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = now
    revoke_all_sessions(session, user.id)
    session.execute(delete(LoginAttempt).where(LoginAttempt.username == uname))
    audit.record(session, "PASSWORD_RECUPERADA", username=uname, entity_type="user", entity_id=user.id)

