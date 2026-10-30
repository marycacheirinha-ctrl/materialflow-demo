import io

import pytest
from PIL import Image

from app.config import reload_settings
from app.domain.enums import AttachmentKind
from app.domain.errors import ValidationError
from app.logging_setup import redact
from app.security.password_policy import validate_password_strength
from app.security.tokens import generate_token, hash_token
from app.security.uploads import sanitize_filename, validate_upload

LIM = dict(max_image_bytes=1024 * 1024, max_pdf_bytes=2 * 1024 * 1024)


def _png(size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, "PNG")
    return buf.getvalue()


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def test_politica_de_palavra_passe():
    reload_settings()
    assert validate_password_strength("Curta1!") != []
    assert validate_password_strength("uma frase longa e unica 2026") == []
    assert validate_password_strength("palavrapasse") != []
    assert validate_password_strength("maria.silva-1234567", username="maria.silva") != []
    assert validate_password_strength("aaaaaaaaaaaaaaaa") != []


def test_tokens_guardam_apenas_hash():
    t = generate_token()
    assert len(t) >= 40
    assert hash_token(t) != t and len(hash_token(t)) == 64
    assert hash_token(t) == hash_token(t)
    assert generate_token() != generate_token()


def test_logs_mascaram_segredos():
    assert "hunter2" not in redact("login password=hunter2 ok")
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redact("chave sk-abcdefghijklmnopqrstuvwxyz")
    assert "abc.def" not in redact("Authorization: Bearer abc.def")


def test_upload_valido():
    r = validate_upload("foto.png", _png(), AttachmentKind.FOTOGRAFIA, **LIM)
    assert r.content_type == "image/png" and len(r.sha256) == 64
    assert validate_upload("ficha.pdf", PDF, AttachmentKind.FICHA_TECNICA, **LIM).content_type == "application/pdf"


@pytest.mark.parametrize(
    "name,data,kind",
    [
        ("x.exe", b"MZ\x90\x00", AttachmentKind.FOTOGRAFIA),
        ("foto.png", PDF, AttachmentKind.FOTOGRAFIA),
        ("ficha.pdf", _png(), AttachmentKind.FICHA_TECNICA),
        ("foto.pdf", _png(), AttachmentKind.FOTOGRAFIA),
        ("foto.png", b"\x89PNG\r\n\x1a\nlixo", AttachmentKind.FOTOGRAFIA),
        ("ficha.pdf", b"%PDF-1.4 truncado", AttachmentKind.FICHA_TECNICA),
        ("vazio.png", b"", AttachmentKind.FOTOGRAFIA),
    ],
)
def test_upload_invalido(name, data, kind):
    with pytest.raises(ValidationError):
        validate_upload(name, data, kind, **LIM)


def test_upload_excede_limite():
    with pytest.raises(ValidationError):
        validate_upload("foto.png", _png(), AttachmentKind.FOTOGRAFIA, max_image_bytes=10, max_pdf_bytes=10)


def test_nome_de_ficheiro_seguro():
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert sanitize_filename("..\\x.png") == "x.png"
    assert sanitize_filename("") == "ficheiro"
