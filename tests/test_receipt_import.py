from datetime import date
from decimal import Decimal

import pytest

from receipt_import import (
    ScanParseError, ScannedItem, build_prompt, merge_identical_items, parse_scan
)

GOOD = """
Here you go!

```json
{
  "store": "Lidl",
  "date": "2026-09-14",
  "receipt_number": "1234 5678 9012",
  "currency": "LEI",
  "payment_type": "Debit Card",
  "total": 18.98,
  "items": [
    {"name": "Banane", "amount": 1.016, "unit": "kg", "unit_price": 8.99, "discount": 0, "refund": false, "category": "Fruit"},
    {"name": "Punga", "amount": 1, "unit": "pcs", "unit_price": 0.81, "discount": 0, "refund": false, "category": null}
  ],
  "notes": ["the date was smudged"]
}
```
"""


def test_parse_scan_reads_a_fenced_block():
    scan = parse_scan(GOOD)

    assert scan.store == "Lidl"
    assert scan.date == date(2026, 9, 14)
    assert scan.receipt_number == "123456789012"
    assert scan.currency == "RON"
    assert scan.total == Decimal("18.98")
    assert scan.notes == ["the date was smudged"]
    assert [i.name for i in scan.items] == ["Banane", "Punga"]
    assert scan.items[0].unit == "kg"
    assert scan.items[0].category == "Fruit"


def test_parse_scan_reads_bare_json_with_smart_quotes_and_trailing_commas():
    text = '{“store”: “Dabo”, “items”: [{“name”: “Paine”, “amount”: 1, “unit_price”: 3.50,},],}'
    scan = parse_scan(text)

    assert scan.store == "Dabo"
    assert scan.items[0].unit_price == Decimal("3.50")


def test_parse_scan_accepts_decimal_commas_and_other_date_formats():
    scan = parse_scan('{"date": "14.09.2026", "total": "18,98", '
                      '"items": [{"name": "Lapte", "amount": "1", "unit_price": "5,49"}]}')

    assert scan.date == date(2026, 9, 14)
    assert scan.total == Decimal("18.98")
    assert scan.items[0].unit_price == Decimal("5.49")


def test_parse_scan_turns_negatives_into_refunds():
    scan = parse_scan('{"items": [{"name": "Retur", "amount": -1, "unit_price": -4.00}]}')

    assert scan.items[0].refund is True
    assert scan.items[0].amount == Decimal(1)
    assert scan.items[0].unit_price == Decimal("4.00")


def test_parse_scan_keeps_discounts_positive():
    scan = parse_scan('{"items": [{"name": "Rosii", "amount": 2, "unit_price": 9.99, "discount": -6}]}')

    assert scan.items[0].discount == Decimal(6)


def test_parse_scan_notes_an_unreadable_date():
    scan = parse_scan('{"date": "sometime", "items": [{"name": "X", "amount": 1, "unit_price": 1}]}')

    assert scan.date is None
    assert any("sometime" in note for note in scan.notes)


@pytest.mark.parametrize("text, fragment", [
    ("", "Paste"),
    ("no json here", "No result found"),
    ('{"items": []}', "no items"),
    ('{"store": "Lidl", "items": [{"name": "X", "amount": 1', "incomplete or damaged"),
    ('{"items": [{"name": "X", "amount": 1}]}', "has no price"),
    ('{"items": [{"name": "X", "amount": 0, "unit_price": 1}]}', "amount of 0"),
])
def test_parse_scan_errors_explain_themselves(text, fragment):
    with pytest.raises(ScanParseError) as error:
        parse_scan(text)
    assert fragment.lower() in str(error.value).lower()


def scanned(name, amount, price, unit="pcs", discount=0, refund=False):
    return ScannedItem(name=name, amount=Decimal(str(amount)), unit=unit,
                       unit_price=Decimal(str(price)), discount=Decimal(str(discount)), refund=refund)


def test_merge_identical_items_combines_whole_number_lines():
    items, counts = merge_identical_items([
        scanned("Punga", 1, "0.81"),
        scanned("Lapte", 1, "5.49"),
        scanned("Punga", 1, "0.81"),
    ])

    assert [i.name for i in items] == ["Punga", "Lapte"]
    assert items[0].amount == Decimal(2)
    assert counts == {"Punga": 2}


def test_merge_identical_items_keeps_weighed_lines_apart():
    items, counts = merge_identical_items([
        scanned("Banane", "1.016", "8.99", unit="kg"),
        scanned("Banane", "1.016", "8.99", unit="kg"),
    ])

    assert len(items) == 2
    assert counts == {}


def test_merge_identical_items_keeps_different_prices_apart():
    items, _ = merge_identical_items([scanned("Punga", 1, "0.81"), scanned("Punga", 1, "0.50")])

    assert len(items) == 2


def test_build_prompt_lists_what_the_app_knows():
    prompt = build_prompt(["Lidl"], ["Cash"], [("Banane", "kg", "Fruit"), ("Punga", "pcs", None)], ["Fruit"])

    assert "Known stores: Lidl" in prompt
    assert "- Banane [kg, Fruit]" in prompt
    assert "- Punga [pcs, no category]" in prompt
    assert "Known categories: Fruit" in prompt
