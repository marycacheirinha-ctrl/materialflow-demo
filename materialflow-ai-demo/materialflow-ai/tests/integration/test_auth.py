import pytest
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import AuditLog, User
from app.domain.errors import AccountLockedError, AuthenticationError, PermissionDenied, ValidationError
from app.services import auth
from tests.integration.conftest import PASSWORD, make_user


def _login(username="maria", password=PASSWORD):
    with db_session.session_scope() as s:
        return auth.authenticate(s, username, password)


def test_palavra_passe_guardada_com_argon2id(session):
    user = make_user(session, "maria")
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_login_valido_cria_sessao_e_resolve(session):
    make_user(session, "maria")
    session.commit()
    current, token = _login()
    assert current.username == "maria"
    with db_session.session_scope() as s:
        assert auth.resolve_session(s, token).username == "maria"


def test_o_token_nao_e_guardado_em_claro(session):
    make_user(session, "maria")
    session.commit()
    _, token = _login()
    with db_session.session_scope() as s:
        from app.db.models import UserSession

        assert all(row.token_hash != token for row in s.scalars(select(UserSession)))


def test_credenciais_erradas_dao_a_mesma_mensagem(session):
    make_user(session, "maria")
    session.commit()
    with pytest.raises(AuthenticationError) as wrong_password:
        _login("maria", "errada")
    with pytest.raises(AuthenticationError) as unknown_user:
        _login("ninguem", "errada")
    assert str(wrong_password.value) == str(unknown_user.value) == auth.GENERIC_LOGIN_ERROR


def test_bloqueio_apos_tentativas_repetidas_persiste(session, fake_clock):
    """As falhas têm de ficar gravadas apesar da exceção (rollback do chamador)."""
    make_user(session, "maria")
    session.commit()
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            _login("maria", "errada")
    with pytest.raises(AccountLockedError):
        _login("maria", PASSWORD)  # nem a palavra-passe certa entra durante o bloqueio


def test_bloqueio_expira(session, fake_clock):
    make_user(session, "maria")
    session.commit()
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            _login("maria", "errada")
    fake_clock.advance(minutes=16)
    current, _ = _login()
    assert current.username == "maria"


def test_bloqueio_tambem_para_utilizadores_inexistentes(session):
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            _login("fantasma", "x")
    with pytest.raises(AccountLockedError):
        _login("fantasma", "x")


def test_login_com_sucesso_zera_falhas(session, fake_clock):
    make_user(session, "maria")
    session.commit()
    for _ in range(4):
        with pytest.raises(AuthenticationError):
            _login("maria", "errada")
    fake_clock.advance(seconds=1)
    _login()
    fake_clock.advance(seconds=1)
    for _ in range(4):  # 4 + 4 falhas no total, mas só 4 desde o último sucesso
        with pytest.raises(AuthenticationError):
            _login("maria", "errada")
    fake_clock.advance(seconds=1)
    _login()  # ainda não bloqueou


def test_conta_inativa_nao_entra(session):
    make_user(session, "maria", active=False)
    session.commit()
    with pytest.raises(AuthenticationError):
        _login()


def test_sessao_expira_por_inatividade(session, fake_clock):
    make_user(session, "maria")
    session.commit()
    _, token = _login()
    fake_clock.advance(minutes=31)
    with db_session.session_scope() as s:
        assert auth.resolve_session(s, token) is None


def test_sessao_expira_no_limite_absoluto(session, fake_clock):
    make_user(session, "maria")
    session.commit()
    _, token = _login()
    for _ in range(17):  # 17 x 29 min = 493 min: atividade contínua não prolonga além de 8 horas
        fake_clock.advance(minutes=29)
        with db_session.session_scope() as s:
            auth.resolve_session(s, token)
    with db_session.session_scope() as s:
        assert auth.resolve_session(s, token) is None


def test_logout_revoga_a_sessao(session):
    make_user(session, "maria")
    session.commit()
    current, token = _login()
    with db_session.session_scope() as s:
        auth.logout(s, token, current)
    with db_session.session_scope() as s:
        assert auth.resolve_session(s, token) is None


def test_desativar_utilizador_invalida_sessoes(session):
    user = make_user(session, "maria")
    session.commit()
    _, token = _login()
    with db_session.session_scope() as s:
        s.get(User, user.id).is_active = False
    with db_session.session_scope() as s:
        assert auth.resolve_session(s, token) is None


def test_alterar_palavra_passe(session):
    make_user(session, "maria")
    session.commit()
    current, token = _login()
    _, other_token = _login()
    new = "outra frase longa e diferente 99"
    with db_session.session_scope() as s:
        auth.change_password(s, current, PASSWORD, new, keep_token=token)
    with db_session.session_scope() as s:
        assert auth.resolve_session(s, token) is not None
        assert auth.resolve_session(s, other_token) is None
    assert _login("maria", new)[0].username == "maria"
    with pytest.raises(AuthenticationError):
        _login("maria", PASSWORD)


def test_alterar_palavra_passe_exige_atual_correta_e_forca_minima(session):
    make_user(session, "maria")
    session.commit()
    current, _ = _login()
    with db_session.session_scope() as s, pytest.raises(AuthenticationError):
        auth.change_password(s, current, "errada", "outra frase longa e diferente 99")
    with db_session.session_scope() as s, pytest.raises(ValidationError):
        auth.change_password(s, current, PASSWORD, "curta")


def test_recuperacao_de_palavra_passe_codigo_de_uso_unico(session, admin, fake_clock):
    make_user(session, "maria")
    session.commit()
    with db_session.session_scope() as s:
        code = auth.issue_reset_token(s, admin, s.scalar(select(User.id).where(User.username == "maria")))
    new = "nova frase longa para recuperar 7"
    with db_session.session_scope() as s:
        auth.reset_password_with_token(s, "maria", code, new)
    assert _login("maria", new)[0].username == "maria"
    with pytest.raises(AuthenticationError):  # segunda utilização falha
        with db_session.session_scope() as s:
            auth.reset_password_with_token(s, "maria", code, "mais uma frase longa e unica 8")


def test_codigo_de_recuperacao_expira_e_e_so_do_utilizador(session, admin, fake_clock):
    make_user(session, "maria")
    make_user(session, "joao")
    session.commit()
    with db_session.session_scope() as s:
        code = auth.issue_reset_token(s, admin, s.scalar(select(User.id).where(User.username == "maria")))
    with pytest.raises(AuthenticationError):  # código de outra pessoa
        with db_session.session_scope() as s:
            auth.reset_password_with_token(s, "joao", code, "nova frase longa para recuperar 7")
    fake_clock.advance(minutes=31)
    with pytest.raises(AuthenticationError):
        with db_session.session_scope() as s:
            auth.reset_password_with_token(s, "maria", code, "nova frase longa para recuperar 7")


def test_so_o_administrador_emite_codigos(session, tec):
    maria = make_user(session, "maria")
    session.commit()
    with db_session.session_scope() as s, pytest.raises(PermissionDenied):
        auth.issue_reset_token(s, tec, maria.id)


def test_auditoria_regista_login_sem_segredos(session):
    make_user(session, "maria")
    session.commit()
    with pytest.raises(AuthenticationError):
        _login("maria", "segredo-errado-123")
    _login()
    with db_session.session_scope() as s:
        entries = list(s.scalars(select(AuditLog)))
    actions = {e.action for e in entries}
    assert {"LOGIN_FALHADO", "LOGIN"} <= actions
    blob = " ".join(str(e.details) for e in entries)
    assert "segredo-errado-123" not in blob and PASSWORD not in blob
