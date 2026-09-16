from decimal import Decimal

import pytest

from units import describe_package, normalize_unit, price_per_base, unit_price_after_discount


@pytest.mark.parametrize("value, expected", [
    ("kg", "kg"), ("KG", "kg"), ("kilograms", "kg"),
    ("l", "l"), ("Litre", "l"),
    ("pcs", "pcs"), ("buc", "pcs"), ("box", "pcs"), ("", "pcs"), (None, "pcs"),
])
def test_normalize_unit(value, expected):
    assert normalize_unit(value) == expected


def test_describe_package():
    assert describe_package(Decimal("500"), "g") == "500 g"
    assert describe_package(Decimal("1.500"), "l") == "1.5 l"
    assert describe_package(None, "g") == ""
    assert describe_package(Decimal("500"), "pcs") == ""


def test_unit_price_after_discount_spreads_over_the_amount():
    assert unit_price_after_discount(2, "9.99", "6.00") == pytest.approx(6.99)
    assert unit_price_after_discount(1, "8.99", 0) == pytest.approx(8.99)


def test_unit_price_after_discount_with_no_amount_keeps_the_price():
    assert unit_price_after_discount(0, "8.99", "1.00") == pytest.approx(8.99)


def test_price_per_base_for_weighed_goods():
    assert price_per_base("8.99", "kg") == (Decimal("8.99"), "kg")


def test_price_per_base_uses_the_package_size():
    price, basis = price_per_base("5.00", "pcs", Decimal("500"), "g")
    assert basis == "kg"
    assert price == Decimal("10.00")


def test_price_per_base_is_none_without_a_size():
    assert price_per_base("5.00", "pcs") is None
    assert price_per_base("5.00", "pcs", Decimal("0"), "g") is None
