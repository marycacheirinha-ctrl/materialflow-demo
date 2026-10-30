from decimal import Decimal

import pytest

from app.domain.numbers import format_decimal, parse_decimal


@pytest.mark.parametrize(
    "raw,expected",
    [("12,50", "12.50"), ("1.234,56", "1234.56"), ("1,234.56", "1234.56"), ("12.5", "12.5"), (" 7 ", "7")],
)
def test_parse_decimal(raw, expected):
    assert parse_decimal(raw) == Decimal(expected)


def test_parse_vazio_devolve_none():
    assert parse_decimal("  ") is None
    assert parse_decimal(None) is None


def test_parse_invalido():
    with pytest.raises(ValueError):
        parse_decimal("abc", field="preço")


def test_format_decimal():
    assert format_decimal(Decimal("12.5000")) == "12,5"
    assert format_decimal(Decimal("100")) == "100"
    assert format_decimal(None) == ""


def test_decimal_nao_usa_float():
    assert parse_decimal("0,1") + parse_decimal("0,2") == Decimal("0.3")
