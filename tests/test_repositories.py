from datetime import date
from decimal import Decimal

import pytest

from conftest import item
from repositories.income_repo import IncomeRepository
from repositories.product_repo import ProductRepository
from repositories.reference_repo import ReferenceRepository
from repositories.reports_repo import ReportsRepository
from repositories.transaction_repo import TransactionRepository

SEPT = date(2026, 9, 14)
AUG = date(2026, 8, 14)


def store_id(name):
    return next(cp.id for cp in ReferenceRepository.get_all_counterparties() if cp.name == name)


def product_id(name):
    return next(p.id for p in ProductRepository.get_all_products(include_hidden=True) if p.name == name)


# ---------- saving receipts ----------

def test_save_transaction_rounds_each_line_into_the_total(save_receipt):
    save_receipt(SEPT, "Lidl", [
        item("Banane", amount="1.016", unit="kg", price="8.99"),
        item("Punga", price="0.81"),
    ])

    tx = TransactionRepository.search_transactions()[0]
    assert tx.total_amount == Decimal("9.94")


def test_save_transaction_creates_the_store_and_products(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Banane", unit="kg", price="8.99", category="Fruit")])

    product = ProductRepository.get_product_overview()[0].product
    assert product.name == "Banane"
    assert product.unit_of_measure == "kg"
    assert product.category.name == "Fruit"
    assert store_id("Lidl")


def test_existing_product_gains_a_category_but_keeps_the_one_it_has(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Banane", unit="kg", price="8.99")])
    save_receipt(SEPT, "Lidl", [item("banane", unit="kg", price="8.99", category="Fruit")])
    save_receipt(SEPT, "Lidl", [item("Banane", unit="kg", price="8.99", category="Vegetable")])

    products = ProductRepository.get_product_overview()
    assert len(products) == 1
    assert products[0].product.category.name == "Fruit"


def test_changing_a_product_to_a_weighed_unit_drops_its_package_size(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Rosii", price="9.99")])
    ProductRepository.update_product(product_id("Rosii"), "Rosii", "pcs", None, Decimal("500"), "g")

    save_receipt(SEPT, "Lidl", [item("Rosii", unit="kg", price="9.99")])

    product = ProductRepository.get_all_products()[0]
    assert product.unit_of_measure == "kg"
    assert product.package_size is None


def test_update_transaction_replaces_the_items_and_the_total(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    tx = TransactionRepository.search_transactions()[0]

    TransactionRepository.update_transaction(
        tx.id, SEPT, "Lidl", "BF12", tx.payment_type_id, "RON",
        [item("Paine", price="3.50"), item("Lapte", price="5.49")]
    )

    updated = TransactionRepository.get_transaction_with_items(tx.id)
    assert updated.total_amount == Decimal("8.99")
    assert {i.product.name for i in updated.items} == {"Paine", "Lapte"}


def test_delete_transaction_removes_it(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    tx = TransactionRepository.search_transactions()[0]

    TransactionRepository.delete_transaction(tx.id)

    assert TransactionRepository.search_transactions() == []


# ---------- searching ----------

@pytest.fixture
def receipts(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Pâine", price="3.50"), item("Roșii cherry", price="9.99")],
                 number="1234 5678")
    save_receipt(AUG, "Dabo", [item("Lapte", price="5.49")], number="BF99")
    save_receipt(SEPT, "Casa Mureșana", [item("Cozonac", price="20.00")], currency="EUR")


def test_search_by_product_name_ignores_accents(receipts):
    assert len(TransactionRepository.search_transactions(text="rosii")) == 1
    assert len(TransactionRepository.search_transactions(text="ROȘII")) == 1


def test_search_by_store_ignores_accents(receipts):
    assert len(TransactionRepository.search_transactions(text="muresana")) == 1


def test_search_by_receipt_number(receipts):
    assert len(TransactionRepository.search_transactions(text="5678")) == 1


def test_search_filters_by_date_store_and_currency(receipts):
    assert len(TransactionRepository.search_transactions(start_date=SEPT)) == 2
    assert len(TransactionRepository.search_transactions(counterparty_id=store_id("Dabo"))) == 1
    assert len(TransactionRepository.search_transactions(currency_code="EUR")) == 1


def test_search_returns_everything_without_a_query(receipts):
    assert len(TransactionRepository.search_transactions()) == 3


def test_find_by_receipt_number_ignores_spacing(receipts):
    assert len(TransactionRepository.find_by_receipt_number("12345678")) == 1
    assert TransactionRepository.find_by_receipt_number("") == []

    saved = TransactionRepository.find_by_receipt_number("12345678")[0]
    assert TransactionRepository.find_by_receipt_number("12345678", exclude_id=saved.id) == []


def test_check_potential_duplicate(receipts):
    assert TransactionRepository.check_potential_duplicate(SEPT, "Lidl", Decimal("13.49"), "RON")
    assert not TransactionRepository.check_potential_duplicate(SEPT, "Lidl", Decimal("99.00"), "RON")
    assert not TransactionRepository.check_potential_duplicate(SEPT, "Nowhere", Decimal("13.49"), "RON")


# ---------- products ----------

def test_merge_products_moves_purchases_and_fills_the_gaps(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49")])
    save_receipt(AUG, "Lidl", [item("LAPTE Zuzu", price="5.99", category="Dairy")])

    keep, other = product_id("Lapte"), product_id("LAPTE Zuzu")
    moved = ProductRepository.merge_products(keep, [other])

    products = ProductRepository.get_product_overview()
    assert moved == 1
    assert len(products) == 1
    assert products[0].product.name == "Lapte"
    assert products[0].product.category.name == "Dairy"


def test_merge_products_keeps_the_receipt_totals(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49"), item("LAPTE Zuzu", price="5.99")])
    before = TransactionRepository.search_transactions()[0].total_amount

    ProductRepository.merge_products(product_id("Lapte"), [product_id("LAPTE Zuzu")])

    assert TransactionRepository.search_transactions()[0].total_amount == before


def test_delete_unused_products_refuses_bought_ones(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49")])

    with pytest.raises(ValueError, match="Lapte"):
        ProductRepository.delete_unused_products([product_id("Lapte")])


def test_set_category_and_hidden_in_bulk(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49"), item("Paine", price="3.50")])
    ids = [product_id("Lapte"), product_id("Paine")]

    ProductRepository.set_category(ids, "Basics")
    ProductRepository.set_hidden(ids, True)

    assert ProductRepository.get_all_products() == []
    hidden = ProductRepository.get_product_overview()
    assert {e.product.category.name for e in hidden} == {"Basics"}


# ---------- brands ----------

def test_saving_with_a_brand_creates_it_once(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])
    save_receipt(AUG, "Lidl", [item("Lapte", price="5.49", brand="zuzu")])

    brands = ProductRepository.get_brands(product_id("Lapte"))
    assert [b.label for b in brands] == ["Zuzu"]


def test_a_blank_brand_is_allowed_and_stays_blank(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49")])

    tx = TransactionRepository.get_transaction_with_items(
        TransactionRepository.search_transactions()[0].id)
    assert ProductRepository.get_brands(product_id("Lapte")) == []
    assert tx.items[0].brand is None


def test_two_brands_live_under_one_product(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])
    save_receipt(SEPT, "Dabo", [item("Lapte", price="5.99", brand="Napolact")])

    overview = ProductRepository.get_product_overview()
    assert len(overview) == 1
    assert sorted(overview[0].brands) == ["Napolact", "Zuzu"]


def test_renaming_a_brand_fixes_past_purchases(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])
    brand = ProductRepository.get_brands(product_id("Lapte"))[0]

    ProductRepository.rename_brand(brand.id, "Zuzu Lapte")

    tx = TransactionRepository.get_transaction_with_items(
        TransactionRepository.search_transactions()[0].id)
    assert tx.items[0].brand.label == "Zuzu Lapte"


def test_a_brand_in_use_cannot_be_removed(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])
    brand = ProductRepository.get_brands(product_id("Lapte"))[0]

    with pytest.raises(ValueError, match="past purchases"):
        ProductRepository.remove_brand(brand.id)


def test_an_unused_brand_can_be_added_and_removed(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49")])
    pid = product_id("Lapte")

    ProductRepository.add_brand(pid, "Napolact")
    assert [b.label for b in ProductRepository.get_brands(pid)] == ["Napolact"]

    with pytest.raises(ValueError, match="already has that brand"):
        ProductRepository.add_brand(pid, "napolact")

    ProductRepository.remove_brand(ProductRepository.get_brands(pid)[0].id)
    assert ProductRepository.get_brands(pid) == []


def test_brand_index_offers_brands_and_the_last_one_used(save_receipt):
    save_receipt(AUG, "Lidl", [item("Lapte", price="5.49", brand="Napolact")])
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])

    index = ProductRepository.get_brand_index()

    assert sorted(index["lapte"]["brands"]) == ["Napolact", "Zuzu"]
    assert index["lapte"]["last"] == "Zuzu"


def test_receipts_can_be_searched_by_brand(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])
    save_receipt(SEPT, "Dabo", [item("Paine", price="3.50")])

    assert len(TransactionRepository.search_transactions(text="zuzu")) == 1


def test_merging_products_folds_their_brands(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Lapte", price="5.49", brand="Zuzu")])
    save_receipt(AUG, "Lidl", [item("LAPTE Zuzu", price="5.99", brand="Zuzu")])
    save_receipt(AUG, "Dabo", [item("LAPTE Zuzu", price="5.99", brand="Napolact")])

    keep, other = product_id("Lapte"), product_id("LAPTE Zuzu")
    ProductRepository.merge_products(keep, [other])

    brands = [b.label for b in ProductRepository.get_brands(keep)]
    lines = ProductRepository.get_product_price_history(keep)
    assert sorted(brands) == ["Napolact", "Zuzu"]
    assert sorted(line.brand.label for line in lines) == ["Napolact", "Zuzu", "Zuzu"]


# ---------- stores and people ----------

def test_merge_counterparties_moves_receipts_and_income(save_receipt, save_income):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    save_receipt(AUG, "LIDL Romania", [item("Paine", price="3.50")])
    save_income(SEPT, "LIDL Romania", "100.00")

    keep, other = store_id("Lidl"), store_id("LIDL Romania")
    receipts, incomes = ReferenceRepository.merge_counterparties(keep, [other])

    assert (receipts, incomes) == (1, 1)
    assert [cp.name for cp in ReferenceRepository.get_all_counterparties()] == ["Lidl"]
    assert len(TransactionRepository.search_transactions(counterparty_id=keep)) == 2


def test_merge_counterparties_folds_locations_with_the_same_name(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    save_receipt(AUG, "LIDL Romania", [item("Paine", price="3.50")])
    keep, other = store_id("Lidl"), store_id("LIDL Romania")

    ReferenceRepository.add_location(keep, "Centru")
    ReferenceRepository.add_location(other, "Centru")
    ReferenceRepository.add_location(other, "Gara")

    ReferenceRepository.merge_counterparties(keep, [other])

    labels = sorted(loc.label for loc in ReferenceRepository.get_locations_for_counterparty("Lidl"))
    assert labels == ["Centru", "Gara"]


def test_merge_counterparties_keeps_a_receipt_pointing_at_the_surviving_location(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    save_receipt(AUG, "LIDL Romania", [item("Paine", price="3.50")])
    keep, other = store_id("Lidl"), store_id("LIDL Romania")

    ReferenceRepository.add_location(keep, "Centru")
    ReferenceRepository.add_location(other, "Centru")
    other_location = ReferenceRepository.get_locations_for_counterparty("LIDL Romania")[0]

    tx = TransactionRepository.search_transactions(counterparty_id=other)[0]
    TransactionRepository.update_transaction(
        tx.id, AUG, "LIDL Romania", None, tx.payment_type_id, "RON",
        [item("Paine", price="3.50")], location_id=other_location.id
    )

    ReferenceRepository.merge_counterparties(keep, [other])

    surviving = ReferenceRepository.get_locations_for_counterparty("Lidl")
    moved = TransactionRepository.search_transactions(counterparty_id=keep)
    assert len(surviving) == 1
    assert {t.location_id for t in moved if t.location_id} == {surviving[0].id}


def test_delete_counterparties_refuses_ones_with_records(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])

    with pytest.raises(ValueError, match="Lidl"):
        ReferenceRepository.delete_counterparties([store_id("Lidl")])


def test_delete_counterparties_removes_an_unused_one(db):
    ReferenceRepository.merge_counterparties  # noqa: B018 - keep the repo imported for clarity
    from database.engine import get_session
    from database.models import Counterparty, CounterpartyCategory

    with get_session() as session:
        category = session.query(CounterpartyCategory).first()
        session.add(Counterparty(name="Unused Shop", category_id=category.id))
        session.commit()

    ReferenceRepository.delete_counterparties([store_id("Unused Shop")])

    assert [cp.name for cp in ReferenceRepository.get_all_counterparties()] == []


def test_counterparty_overview_counts_spending_and_income(save_receipt, save_income):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    save_receipt(AUG, "Lidl", [item("Paine", price="3.50")])
    save_income(SEPT, "Acme", "100.00")

    overview = {e.counterparty.name: e for e in ReferenceRepository.get_counterparty_overview()}

    assert overview["Lidl"].receipts == 2
    assert overview["Lidl"].spent == {"RON": Decimal("4.31")}
    assert overview["Lidl"].last_date == SEPT
    assert overview["Acme"].incomes == 1
    assert overview["Acme"].earned == {"RON": Decimal("100.00")}


def test_income_sources_leave_out_shops(save_receipt, save_income):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    save_income(SEPT, "Acme", "100.00")

    assert [cp.name for cp in ReferenceRepository.get_income_sources()] == ["Acme"]


def test_counterparty_category_is_created_when_the_name_is_new(db):
    before = {c.name for c in ReferenceRepository.get_all_counterparty_categories()}

    new_id = ReferenceRepository.get_or_create_counterparty_category_id("Utility Provider")
    same_id = ReferenceRepository.get_or_create_counterparty_category_id("utility provider")

    after = {c.name for c in ReferenceRepository.get_all_counterparty_categories()}
    assert "Utility Provider" not in before
    assert "Utility Provider" in after
    assert new_id == same_id


def test_rename_location_rejects_a_clash(save_receipt):
    save_receipt(SEPT, "Lidl", [item("Punga", price="0.81")])
    cp = store_id("Lidl")
    ReferenceRepository.add_location(cp, "Centru")
    ReferenceRepository.add_location(cp, "Gara")
    gara = next(l for l in ReferenceRepository.get_locations_for_counterparty("Lidl") if l.label == "Gara")

    with pytest.raises(ValueError, match="already exists"):
        ReferenceRepository.rename_location(gara.id, "centru")

    ReferenceRepository.rename_location(gara.id, "Garii")
    assert sorted(l.label for l in ReferenceRepository.get_locations_for_counterparty("Lidl")) == ["Centru", "Garii"]


# ---------- income ----------

def test_income_search_and_duplicates(save_income):
    save_income(SEPT, "Acme Cluj", "100.00")
    save_income(AUG, "Acme Cluj", "100.00")

    assert len(IncomeRepository.search_incomes(text="acme")) == 2
    assert len(IncomeRepository.search_incomes(start_date=SEPT)) == 1
    assert IncomeRepository.check_potential_duplicate(SEPT, "Acme Cluj", "100.00", "RON")
    assert not IncomeRepository.check_potential_duplicate(SEPT, "Acme Cluj", "50.00", "RON")


def test_recent_incomes_are_newest_first(save_income):
    save_income(AUG, "Acme", "100.00")
    save_income(SEPT, "Acme", "200.00")

    recent = IncomeRepository.get_recent_incomes()
    assert [float(i.net_amount) for i in recent] == [200.0, 100.0]


# ---------- reports ----------

@pytest.fixture
def month_of_data(save_receipt, save_income):
    save_receipt(SEPT, "Lidl", [
        item("Banane", amount="1.016", unit="kg", price="8.99", category="Fruit"),
        item("Punga", price="0.81"),
    ])
    save_receipt(SEPT, "Dabo", [item("Paine", price="3.50", category="Pastry")])
    save_receipt(AUG, "Lidl", [item("Lapte", price="5.49")])
    save_income(SEPT, "Acme", "1000.00")


def test_month_summary(month_of_data):
    income, expenses = ReportsRepository.get_month_summary("RON", 2026, 9)

    assert income == pytest.approx(1000.00)
    assert expenses == pytest.approx(13.44)


def test_store_breakdown_is_biggest_first(month_of_data):
    breakdown = ReportsRepository.get_store_breakdown("RON", 2026, 9)

    assert [name for _, name, _ in breakdown] == ["Lidl", "Dabo"]
    assert breakdown[0][2] == pytest.approx(9.94)


def test_category_breakdown_adds_up_to_the_month(month_of_data):
    _, expenses = ReportsRepository.get_month_summary("RON", 2026, 9)
    breakdown = ReportsRepository.get_category_breakdown("RON", 2026, 9)

    assert sum(total for _, _, total in breakdown) == pytest.approx(expenses)
    assert {name for _, name, _ in breakdown} == {"Fruit", "Pastry", "Uncategorized"}


def test_monthly_totals_cover_every_month_in_the_window(month_of_data):
    totals = ReportsRepository.get_monthly_totals("RON", 2026, 9, months=3)

    assert [(y, m) for y, m, _, _ in totals] == [(2026, 7), (2026, 8), (2026, 9)]
    assert totals[1][3] == pytest.approx(5.49)
    assert totals[2][2] == pytest.approx(1000.00)


def test_month_lines_can_be_filtered(month_of_data):
    all_lines = ReportsRepository.get_month_lines("RON", 2026, 9)
    lidl = ReportsRepository.get_month_lines("RON", 2026, 9, store_id=store_id("Lidl"))
    uncategorized = ReportsRepository.get_month_lines("RON", 2026, 9, uncategorized=True)

    assert len(all_lines) == 3
    assert len(lidl) == 2
    assert [line.product.name for line in uncategorized] == ["Punga"]


def test_available_years_include_the_data_and_today(month_of_data):
    years = ReportsRepository.get_available_years()

    assert 2026 in years
    assert years == sorted(years)
