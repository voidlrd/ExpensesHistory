from decimal import Decimal

UNITS = ("pcs", "kg", "l")
PACKAGE_UNITS = ("g", "kg", "ml", "l")

_ALIASES = {
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
}
_TO_BASE = {
    "g": ("kg", Decimal("0.001")),
    "kg": ("kg", Decimal("1")),
    "ml": ("l", Decimal("0.001")),
    "l": ("l", Decimal("1")),
}


def normalize_unit(value):
    """Map any stored label to pcs/kg/l; anything counted (boxes, packages...) is pcs."""
    return _ALIASES.get((value or "").strip().casefold(), "pcs")


def describe_package(package_size, package_unit):
    if not package_size or package_unit not in _TO_BASE:
        return ""
    return f"{Decimal(str(package_size)).normalize():f} {package_unit}"


def unit_price_after_discount(amount, price, discount):
    """What one unit really cost once the line's discount is spread over the amount."""
    amount = Decimal(str(amount))
    if amount <= 0:
        return float(price)
    return float((amount * Decimal(str(price)) - Decimal(str(discount))) / amount)


def price_per_base(unit_price, unit, package_size=None, package_unit=None):
    """Price per kg or l, or None when the product is counted without a known size."""
    unit = normalize_unit(unit)
    price = Decimal(str(unit_price))
    if unit in ("kg", "l"):
        return price, unit
    if package_size and package_unit in _TO_BASE:
        base, factor = _TO_BASE[package_unit]
        size = Decimal(str(package_size)) * factor
        if size > 0:
            return price / size, base
    return None
