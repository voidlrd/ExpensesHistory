from datetime import date

from repositories.reports_repo import month_bounds, shift_month
from ui.views.transaction_list import period_range


def test_month_bounds():
    assert month_bounds(2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_bounds(2024, 2) == (date(2024, 2, 1), date(2024, 2, 29))
    assert month_bounds(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))


def test_shift_month_crosses_years():
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)
    assert shift_month(2026, 9, -12) == (2025, 9)
    assert shift_month(2026, 9, 0) == (2026, 9)


def test_period_range_presets():
    today = date(2026, 9, 15)

    assert period_range("This month", today) == (date(2026, 9, 1), date(2026, 9, 30))
    assert period_range("Last month", today) == (date(2026, 8, 1), date(2026, 8, 31))
    assert period_range("Last 3 months", today) == (date(2026, 7, 1), date(2026, 9, 30))
    assert period_range("This year", today) == (date(2026, 1, 1), date(2026, 12, 31))
    assert period_range("Last year", today) == (date(2025, 1, 1), date(2025, 12, 31))
    assert period_range("All time", today)[0].year == 2000
    assert period_range("Custom", today) is None


def test_period_range_in_january():
    today = date(2026, 1, 10)

    assert period_range("Last month", today) == (date(2025, 12, 1), date(2025, 12, 31))
    assert period_range("Last 3 months", today) == (date(2025, 11, 1), date(2026, 1, 31))
