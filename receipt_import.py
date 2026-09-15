import json
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from units import normalize_unit

PROMPT = """
Read the shopping receipt in the attached photo(s) and extract it for an expense tracking app.

Reply with ONLY one JSON code block and no other text, in exactly this shape:

```json
{
  "store": "Kaufland",
  "date": "2026-08-18",
  "receipt_number": "12345678902026081814301200017",
  "currency": "RON",
  "payment_type": "Debit Card",
  "total": 23.92,
  "items": [
    {"name": "Banane", "amount": 1.016, "unit": "kg", "unit_price": 8.99, "discount": 0, "refund": false, "category": "Fruit"},
    {"name": "Rosii cherry", "amount": 2, "unit": "pcs", "unit_price": 9.99, "discount": 6.00, "refund": false, "category": "Vegetable"},
    {"name": "Punga", "amount": 1, "unit": "pcs", "unit_price": 0.81, "discount": 0, "refund": false, "category": null}
  ],
  "notes": []
}
```

Rules:
- One entry per product line, in receipt order. A product printed on several lines stays as several entries.
- unit is "kg" or "l" only when the line is weighed or measured (for example "1.016 KG x 8.99"). Everything else, including packaged goods such as "Rosii cherry 500g", is "pcs" with a whole-number amount.
- unit_price is the price of one unit (one piece, one kg or one litre) before any discount.
- discount: when a discount or reduction line (for example "DISCOUNT", "REDUCERE", or a negative amount) follows a product, put it in that product's "discount" as a positive number. Do not list it as a separate item.
- refund is true for returned or cancelled products (for example "STORNO" or "RETUR"), still with a positive amount and unit_price.
- Fees and deposits printed as lines (bags, "GARANTIE SGR", eco tax) are items too.
- total is the final amount paid, exactly as printed.
- receipt_number is the long unique ID printed near the bottom (for example after "ID UNIC"), all digits as one string without spaces. Only when the receipt has no such ID, use its shorter receipt number (for example after "BF" or "BON").
- Numbers are plain JSON numbers with a dot as the decimal separator and no currency symbols.
- date is YYYY-MM-DD. currency is a 3-letter code ("LEI" is "RON").
- store is the short shop or brand name, not the legal company name. Use a known store below when it is the same shop.
- payment_type is one of the known payment types below, or null.
- name: when the product is one of the known products below, use that exact name. Otherwise write a short readable name in the receipt's language, with normal capitalisation (not ALL CAPS) and obvious abbreviations written out.
- category is one of the known categories below (exact name) that fits the product, or null when none fits.
- If several photos show parts of one receipt, combine them and do not repeat lines that appear in more than one photo.
- If something is unreadable, give your best reading or null, and say what is uncertain in "notes". Never invent products or prices.
""".strip()


@dataclass
class ScannedItem:
    name: str
    amount: Decimal
    unit: str
    unit_price: Decimal
    discount: Decimal = Decimal(0)
    refund: bool = False
    category: str | None = None


@dataclass
class ReceiptScan:
    items: list
    store: str | None = None
    date: date | None = None
    receipt_number: str | None = None
    currency: str | None = None
    payment_type: str | None = None
    total: Decimal | None = None
    notes: list = field(default_factory=list)


class ScanParseError(ValueError):
    pass


def merge_identical_items(items):
    """Combine whole-number lines with the same name, unit, price and refund flag; returns (items, {name: lines combined})."""
    merged, positions, counts = [], {}, {}
    for item in items:
        key = (item.name.casefold(), item.unit, item.unit_price, item.refund)
        # weighed lines stay separate: merging them could move the rounded total by a cent
        whole = item.amount == item.amount.to_integral_value()
        if whole and key in positions:
            target = merged[positions[key]]
            target.amount += item.amount
            target.discount += item.discount
            counts[target.name] = counts.get(target.name, 1) + 1
        else:
            if whole:
                positions[key] = len(merged)
            merged.append(replace(item))
    return merged, counts


def build_prompt(stores, payment_types, products, categories=()):
    """products: (name, unit) or (name, unit, category) tuples."""
    def describe(product):
        name, unit, *rest = product
        return f"- {name} [{unit}, {rest[0] or 'no category'}]" if rest else f"- {name} [{unit}]"

    lines = [
        PROMPT,
        "",
        "Known stores: " + (", ".join(stores) or "none yet"),
        "Known payment types: " + (", ".join(payment_types) or "none"),
        "Known categories: " + (", ".join(categories) or "none yet"),
        "Known products (unit and category in brackets):",
    ]
    lines += [describe(p) for p in products] or ["- none yet"]
    return "\n".join(lines)


_FENCED = re.compile(r"```[A-Za-z]*\s*(\{.*?\})\s*```", re.S)


def _json_text(text):
    match = _FENCED.search(text)
    if match:
        return match.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1:
        raise ScanParseError("No result found in the pasted text. Copy the AI's whole reply, including the part in { }.")
    if end <= start:
        # cut off before the closing brace; let the JSON error explain it
        return text[start:]
    return text[start:end + 1]


def _loads(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    cleaned = raw.replace("“", '"').replace("”", '"')
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ScanParseError(
            f"The pasted result is incomplete or damaged (problem near line {e.lineno}). "
            "Copy the reply again, or ask the AI to reply with only the JSON block."
        ) from None


def _text(value):
    if value is None:
        return None
    return str(value).strip() or None


def _number(value, what, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ScanParseError(f"{what} should be a number, not {value!r}.")
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = re.sub(r"[^\d,.\-]", "", str(value))
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text:
        # whichever separator comes last is the decimal point
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ScanParseError(f"{what} should be a number, not {value!r}.") from None


def _receipt_number(value):
    text = _text(value)
    return re.sub(r"\s+", "", text) if text else None


def _date(value, notes):
    text = _text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    notes.append(f"Couldn't read the date \"{text}\", so the date was left unchanged.")
    return None


def parse_scan(text):
    if not text or not text.strip():
        raise ScanParseError("Paste the AI's reply first.")

    data = _loads(_json_text(text))
    if not isinstance(data, dict):
        raise ScanParseError('The result should be one JSON object with an "items" list.')

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ScanParseError("The result has no items. Check that the photo shows the receipt lines.")

    notes = [str(n).strip() for n in (data.get("notes") or []) if str(n).strip()]
    items = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise ScanParseError(f"Item {index} isn't in the expected format.")
        name = _text(raw.get("name"))
        if not name:
            notes.append(f"Item {index} had no name and was skipped.")
            continue

        label = f"Item {index} ({name})"
        amount = _number(raw.get("amount"), f"{label} amount", Decimal(1))
        price = _number(raw.get("unit_price", raw.get("price")), f"{label} price")
        if price is None:
            raise ScanParseError(f"{label} has no price.")
        if amount == 0:
            raise ScanParseError(f"{label} has an amount of 0.")

        refund = raw.get("refund") is True or str(raw.get("refund")).strip().lower() == "true"
        # some models write returns as negative numbers instead of setting refund
        if amount < 0 or price < 0:
            amount, price, refund = abs(amount), abs(price), True

        items.append(ScannedItem(
            name=name,
            amount=amount,
            unit=normalize_unit(raw.get("unit")),
            unit_price=price,
            discount=abs(_number(raw.get("discount"), f"{label} discount", Decimal(0))),
            refund=refund,
            category=_text(raw.get("category")),
        ))

    if not items:
        raise ScanParseError("None of the items had a name.")

    currency = _text(data.get("currency"))
    if currency:
        currency = "RON" if currency.upper() in ("LEI", "RON") else currency.upper()

    return ReceiptScan(
        items=items,
        store=_text(data.get("store")),
        date=_date(data.get("date"), notes),
        receipt_number=_receipt_number(data.get("receipt_number")),
        currency=currency,
        payment_type=_text(data.get("payment_type")),
        total=_number(data.get("total"), "The receipt total"),
        notes=notes,
    )
