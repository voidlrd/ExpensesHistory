from decimal import Decimal

from repositories.transaction_repo import line_total, normalize_receipt_number


def test_line_total_rounds_each_line_to_the_cent():
    # 1.016 kg x 8.99 = 9.13384
    assert line_total("1.016", "8.99", 0, False) == Decimal("9.13")


def test_line_total_rounds_half_up():
    assert line_total(1, "0.125", 0, False) == Decimal("0.13")


def test_line_total_subtracts_the_discount():
    assert line_total(2, "9.99", "6.00", False) == Decimal("13.98")


def test_line_total_negates_refunds():
    assert line_total(1, "4.00", 0, True) == Decimal("-4.00")


def test_normalize_receipt_number_ignores_spaces_and_case():
    assert normalize_receipt_number(" 1234 5678 ") == "12345678"
    assert normalize_receipt_number("BF-12a") == normalize_receipt_number("bf-12A")
    assert normalize_receipt_number(None) == ""
