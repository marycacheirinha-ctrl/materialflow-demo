"""Logs sem dados sensíveis: um formatador mascara padrões comuns (segredos, tokens, chaves)."""

import logging
import re

_KEYVALUE = re.compile(
    r"(?i)(password|passwd|palavra[-_ ]?passe|secret|token|api[-_]?key|authorization)(\s*[=:]\s*)([^\s,;]+)"
)
_OPENAI_KEY = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")


def redact(text: str) -> str:
    # O padrão Bearer tem de vir primeiro: «Authorization: Bearer xyz» não pode ficar só com «Bearer» mascarado.
    text = _BEARER.sub("Bearer ***", text)
    text = _OPENAI_KEY.sub("***", text)
    return _KEYVALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if getattr(root, "_materialflow_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
    root._materialflow_configured = True  # type: ignore[attr-defined]
