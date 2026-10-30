"""Validação de ficheiros carregados: conteúdo real (não só extensão), tamanho e integridade."""

import hashlib
import io
import re
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.domain.enums import AttachmentKind
from app.domain.errors import ValidationError

MAX_IMAGE_PIXELS = 50_000_000
ALLOWED_EXTENSIONS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
}
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(frozen=True)
class ValidatedUpload:
    content_type: str
    safe_filename: str
    size_bytes: int
    sha256: str


def sniff_content_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def sanitize_filename(name: str) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._ \-áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", "_", base).strip(" .")
    return base[:120] or "ficheiro"


def _extension(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


def validate_upload(
    filename: str, data: bytes, kind: AttachmentKind, *, max_image_bytes: int, max_pdf_bytes: int
) -> ValidatedUpload:
    if not data:
        raise ValidationError("O ficheiro está vazio.")
    content_type = sniff_content_type(data)
    if content_type is None:
        raise ValidationError("Formato não permitido. Use JPG, PNG, WEBP (fotografias) ou PDF (fichas técnicas).")

    is_image = content_type in _IMAGE_TYPES
    if kind == AttachmentKind.FOTOGRAFIA and not is_image:
        raise ValidationError("Uma fotografia tem de ser uma imagem JPG, PNG ou WEBP.")
    if kind == AttachmentKind.FICHA_TECNICA and content_type != "application/pdf":
        raise ValidationError("Uma ficha técnica tem de ser um ficheiro PDF.")

    limit = max_image_bytes if is_image else max_pdf_bytes
    if len(data) > limit:
        raise ValidationError(f"O ficheiro excede o limite de {limit // (1024 * 1024)} MB.")

    safe = sanitize_filename(filename)
    if _extension(safe) not in ALLOWED_EXTENSIONS[content_type]:
        raise ValidationError("A extensão do ficheiro não corresponde ao seu conteúdo.")

    if is_image:
        try:
            with Image.open(io.BytesIO(data)) as img:
                width, height = img.size
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise ValidationError("A imagem está corrompida ou não pode ser lida.") from exc
        if width * height > MAX_IMAGE_PIXELS:
            raise ValidationError("A imagem tem dimensões excessivas.")
    elif b"%%EOF" not in data[-4096:]:
        raise ValidationError("O PDF parece incompleto ou corrompido.")

    return ValidatedUpload(
        content_type=content_type,
        safe_filename=safe,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
