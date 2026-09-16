"""Offscreen checks that the tabs still work end to end."""
from datetime import date

import pytest
from PyQt6.QtCore import QDate, QItemSelectionModel, QSettings

from conftest import item
from repositories.product_repo import ProductRepository
from repositories.reference_repo import ReferenceRepository
from repositories.transaction_repo import TransactionRepository

SEPT = date(2026, 9, 14)
AUG = date(2026, 8, 14)
HIDDEN_MARK = "\U0001F6AB "


@pytest.fixture
def shop_data(save_receipt):
    save_receipt(SEPT, "Lidl", [
        item("Banane", amount="1.016", unit="kg", price="8.99", category="Fruit"),
        item("Punga", price="0.81"),
    ], number="1234 5678")
    save_receipt(AUG, "LIDL Romania", [item("Paine", price="3.50", category="Pastry")])
    save_receipt(date(2026, 9, 2), "Dabo", [item("Banane", amount="0.5", unit="kg", price="8.99")])


@pytest.fixture
def data_manager(qt_env, shop_data):
    from ui.views.data_manager import DataManagerView
    return DataManagerView()


@pytest.fixture
def main_window(qt_env, shop_data):
    from ui.main_window import MainWindow
    return MainWindow()


def select_stores(panel, *names):
    """Select rows by store name; selectRow() would drop the previous one."""
    table = panel.cp_table
    model = table.selectionModel()
    table.clearSelection()
    for row in range(table.rowCount()):
        if table.item(row, 0).text().replace(HIDDEN_MARK, "") in names:
            model.select(table.model().index(row, 0),
                         QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    return panel.selected_cp_ids()


# ---------- shell ----------

def test_main_window_builds_every_tab(main_window):
    titles = [main_window.tabs.tabText(i) for i in range(main_window.tabs.count())]

    assert titles == ["Dashboard", "New Transaction", "New Income", "History",
                      "Price Tracker", "Data Manager"]


def test_dashboard_shows_the_month(main_window):
    dashboard = main_window.dashboard_tab
    dashboard.refresh()

    assert dashboard.expense_label.text().endswith("RON")
    assert dashboard.breakdown_table.rowCount() >= 1


def test_history_summarises_what_is_shown(main_window):
    history = main_window.history_tab
    history.period_selector.setCurrentText("All time")
    history.apply_period()

    assert history.table.rowCount() == 3
    assert "3 receipts" in history.summary_label.text()


# ---------- stores & people ----------

def test_store_table_shows_spending_and_last_activity(data_manager):
    entry = next(e for e in data_manager.overview if e.counterparty.name == "Lidl")

    assert data_manager.cp_table.rowCount() == 3
    assert str(entry.spent["RON"]) == "9.94"
    assert entry.last_date == SEPT


def test_store_search_filters_the_table(data_manager):
    data_manager.cp_search.setText("lidl")
    assert data_manager.cp_table.rowCount() == 2

    data_manager.cp_search.setText("")
    assert data_manager.cp_table.rowCount() == 3


def test_selecting_one_store_fills_the_edit_form(data_manager):
    select_stores(data_manager, "Lidl")

    assert data_manager.cp_name_input.text() == "Lidl"
    assert "receipt" in data_manager.cp_usage_label.text()
    assert not data_manager.cp_merge_btn.isEnabled()


def test_merge_stores_moves_receipts_and_keeps_totals(data_manager, popups, monkeypatch):
    # popups also stubs the confirmation; without it the dialog would block forever
    from PyQt6.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda parent, title, label, items, *a, **k: (items[0], True)))

    before = sum(float(t.total_amount) for t in TransactionRepository.search_transactions())
    ids = select_stores(data_manager, "Lidl", "LIDL Romania")
    assert len(ids) == 2 and data_manager.cp_merge_btn.isEnabled()

    data_manager.merge_selected_cps()

    names = [e.counterparty.name for e in data_manager.overview]
    after = sum(float(t.total_amount) for t in TransactionRepository.search_transactions())
    assert "LIDL Romania" not in names
    assert after == pytest.approx(before)
    assert "Merged" in data_manager.cp_status_label.text()


def test_typing_a_new_category_creates_it(data_manager, popups):
    select_stores(data_manager, "Dabo")
    data_manager.cp_cat_input.setCurrentText("Utilities")

    data_manager.save_cp_changes()

    categories = {c.name for c in ReferenceRepository.get_all_counterparty_categories()}
    dabo = next(e.counterparty for e in data_manager.overview if e.counterparty.name == "Dabo")
    assert "Utilities" in categories
    assert dabo.category.name == "Utilities"
    assert not any(kind == "warn" for kind, _ in popups)


def test_hide_and_unhide_a_store(data_manager):
    select_stores(data_manager, "Dabo")
    data_manager.set_cp_hidden(True)
    assert any(e.counterparty.hidden for e in data_manager.overview)

    select_stores(data_manager, "Dabo")
    data_manager.set_cp_hidden(False)
    assert not any(e.counterparty.hidden for e in data_manager.overview)


def test_delete_is_refused_for_a_store_with_receipts(data_manager, popups):
    select_stores(data_manager, "Dabo")

    data_manager.delete_selected_cps()

    assert any(kind == "warn" for kind, _ in popups)
    assert any(e.counterparty.name == "Dabo" for e in data_manager.overview)


def test_rename_a_location(data_manager, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    lidl = next(e.counterparty.id for e in data_manager.overview if e.counterparty.name == "Lidl")
    ReferenceRepository.add_location(lidl, "Centru")
    data_manager.load_data()
    select_stores(data_manager, "Lidl")
    assert data_manager.loc_list.count() == 1

    data_manager.loc_list.setCurrentRow(0)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Centru Nou", True)))
    data_manager.rename_location()

    assert data_manager.loc_list.item(0).text() == "Centru Nou"


# ---------- backups ----------

def test_backup_list_starts_empty_without_a_fake_row(data_manager):
    data_manager.load_backups()

    assert data_manager.backup_table.rowCount() == 0
    assert "No backups yet" in data_manager.backup_status_label.text()


def test_create_a_backup_without_a_popup(data_manager, popups):
    data_manager.create_backup()

    assert data_manager.backup_table.rowCount() == 1
    assert popups == []
    assert "Backup created" in data_manager.backup_status_label.text()


def test_restore_rolls_the_data_back(data_manager, popups, save_receipt):
    data_manager.create_backup()
    before = len(TransactionRepository.search_transactions())

    save_receipt(date(2026, 9, 20), "Extra Shop", [item("Ceva", price="50.00")])
    assert len(TransactionRepository.search_transactions()) == before + 1

    data_manager.backup_table.selectRow(0)
    data_manager.restore_selected()

    assert len(TransactionRepository.search_transactions()) == before
    assert "Before restore" in [kind for _, kind, _, _ in _backups(data_manager)]
    assert "Restored" in data_manager.backup_status_label.text()


def _backups(panel):
    from database import backup
    return backup.list_backups()


# ---------- new income ----------

def test_income_form_leaves_shops_out_of_the_sources(qt_env, shop_data):
    from ui.views.new_income import NewIncomeView
    view = NewIncomeView()

    sources = [view.counterparty_input.itemText(i) for i in range(view.counterparty_input.count())]
    assert "Lidl" not in sources


def test_income_refuses_a_zero_amount(qt_env, popups):
    from ui.views.new_income import NewIncomeView
    view = NewIncomeView()
    view.counterparty_input.setCurrentText("Acme")
    view.amount_input.setValue(0)

    view.save_income()

    assert any(kind == "warn" for kind, _ in popups)


def test_income_saves_inline_and_lists_it(qt_env, popups):
    from ui.views.new_income import NewIncomeView
    view = NewIncomeView()
    view.counterparty_input.setCurrentText("Acme")
    view.amount_input.setValue(2500)

    view.save_income()

    assert popups == []
    assert "Saved" in view.status_label.text()
    assert view.recent_table.rowCount() == 1
    assert view.amount_input.value() == 0

    view.refresh()
    sources = [view.counterparty_input.itemText(i) for i in range(view.counterparty_input.count())]
    assert "Acme" in sources


def test_income_warns_about_a_duplicate(qt_env, popups, save_income):
    from ui.views.new_income import NewIncomeView
    save_income(SEPT, "Acme", "2500.00")

    view = NewIncomeView()
    view.date_input.setDate(QDate(SEPT.year, SEPT.month, SEPT.day))
    view.counterparty_input.setCurrentText("Acme")
    view.amount_input.setValue(2500)
    view._run_duplicate_check()

    assert view.duplicate_warning_label.text().startswith("⚠")


# ---------- new transaction ----------

def test_receipt_saves_with_an_inline_confirmation(qt_env, shop_data, popups):
    from ui.views.new_transaction import NewTransactionView
    view = NewTransactionView()
    view.counterparty_input.setCurrentText("Dabo")
    view._add_filled_row("Covrig", 2, "pcs", "2.50", 0, False)

    view.save_transaction()

    assert popups == []
    assert "Saved" in view.status_label.text()
    assert len(TransactionRepository.search_transactions()) == 4


def test_receipt_needs_a_product(qt_env, shop_data, popups):
    from ui.views.new_transaction import NewTransactionView
    view = NewTransactionView()
    view.counterparty_input.setCurrentText("Dabo")

    view.save_transaction()

    assert any(kind == "warn" for kind, _ in popups)
    assert len(TransactionRepository.search_transactions()) == 3


# ---------- price tracker ----------

def test_price_tracker_filters_products(qt_env, shop_data):
    from ui.views.price_tracker import PriceTrackerView
    view = PriceTrackerView()

    view.product_filter.setText("banan")
    assert view.product_search.count() == 2  # the blank entry plus Banane

    view.product_filter.setText("")
    assert view.product_search.count() == 4


def test_products_tab_opens_the_price_history(main_window):
    banane = next(p.id for p in ProductRepository.get_all_products() if p.name == "Banane")

    main_window.open_price_history(banane)
    tracker = main_window.price_tracker_tab

    assert main_window.tabs.currentWidget() is tracker
    assert tracker.product_search.currentData() == banane
    assert tracker.table.rowCount() == 2
    assert "Average per store" in tracker.store_summary.text()


# ---------- window state ----------

def test_window_remembers_its_size_and_tab(main_window):
    from ui.main_window import MainWindow

    main_window.tabs.setCurrentIndex(3)
    # the offscreen screen is 800x600 and restoreGeometry clamps to it
    main_window.resize(700, 500)
    main_window.close()

    settings = QSettings("ExpensesHistory", "ExpenseTracker")
    assert settings.value("tab", 0, type=int) == 3
    assert settings.value("geometry") is not None

    reopened = MainWindow()
    assert reopened.tabs.currentIndex() == 3
    assert (reopened.width(), reopened.height()) == (700, 500)
