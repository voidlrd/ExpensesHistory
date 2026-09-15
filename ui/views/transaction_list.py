from collections import defaultdict
from datetime import date
from decimal import Decimal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel,
    QGroupBox, QDateEdit, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, QDate, QTimer
from repositories.transaction_repo import TransactionRepository
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository
from repositories.reports_repo import month_bounds, shift_month
from ui.views.record_dialogs import IncomeDetailDialog, TransactionDetailDialog, TransactionEditDialog
from ui.widgets import number_item, repopulate_combo

__all__ = ["TransactionListView", "TransactionDetailDialog", "TransactionEditDialog", "IncomeDetailDialog"]

EXPENSE_COLUMNS = ["Date", "Counterparty", "Receipt No", "Total", "Items", "Currency", "Payment Type"]
INCOME_COLUMNS = ["Date", "Source", "Net Amount", "Currency", "Payment Type"]

PERIODS = ("This month", "Last month", "Last 3 months", "This year", "Last year", "All time", "Custom")

def period_range(period, today):
    """(start, end) for a preset period, or None for Custom."""
    this_start, this_end = month_bounds(today.year, today.month)
    if period == "This month":
        return this_start, this_end
    if period == "Last month":
        return month_bounds(*shift_month(today.year, today.month, -1))
    if period == "Last 3 months":
        return month_bounds(*shift_month(today.year, today.month, -2))[0], this_end
    if period == "This year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if period == "Last year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if period == "All time":
        return date(2000, 1, 1), this_end
    return None

def _qdate(value):
    return QDate(value.year, value.month, value.day)

class TransactionListView(QWidget):
    def __init__(self):
        super().__init__()
        self.trans_repo = TransactionRepository()
        self.income_repo = IncomeRepository()
        self.ref_repo = ReferenceRepository()
        self._setting_period = False

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.load_data)

        self.setup_ui()
        self.load_reference_data()
        self.apply_period()
        self.on_type_changed()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        title_label = QLabel("Transaction History")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        filter_group = QGroupBox("Filters")
        filter_layout = QVBoxLayout(filter_group)

        self.type_selector = QComboBox()
        self.type_selector.addItems(["Expenses", "Income"])

        self.period_selector = QComboBox()
        self.period_selector.addItems(PERIODS)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)

        self.cb_counterparty = QComboBox()
        self.cb_currency = QComboBox()

        first_row = QHBoxLayout()
        for label, widget in (("Type:", self.type_selector), ("Period:", self.period_selector),
                              ("From:", self.start_date), ("To:", self.end_date),
                              ("Source/Store:", self.cb_counterparty), ("Currency:", self.cb_currency)):
            first_row.addWidget(QLabel(label))
            first_row.addWidget(widget)
        first_row.addStretch()
        filter_layout.addLayout(first_row)

        second_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search store, receipt ID or product...")
        self.search_input.setClearButtonEnabled(True)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_filters)
        second_row.addWidget(QLabel("Search:"))
        second_row.addWidget(self.search_input, 1)
        second_row.addWidget(self.reset_btn)
        filter_layout.addLayout(second_row)

        layout.addWidget(filter_group)

        self.table = QTableWidget(0, len(EXPENSE_COLUMNS))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.show_details)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.summary_label)

        self.type_selector.currentIndexChanged.connect(self.on_type_changed)
        self.period_selector.currentIndexChanged.connect(self.apply_period)
        self.start_date.dateChanged.connect(self.on_dates_edited)
        self.end_date.dateChanged.connect(self.on_dates_edited)
        self.cb_counterparty.currentIndexChanged.connect(self.load_data)
        self.cb_currency.currentIndexChanged.connect(self.load_data)
        self.search_input.textChanged.connect(self._search_timer.start)

    def on_type_changed(self):
        columns = EXPENSE_COLUMNS if self.type_selector.currentText() == "Expenses" else INCOME_COLUMNS
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.load_data()

    def apply_period(self):
        dates = period_range(self.period_selector.currentText(), date.today())
        if dates is None:
            return
        self._setting_period = True
        self.start_date.setDate(_qdate(dates[0]))
        self.end_date.setDate(_qdate(dates[1]))
        self._setting_period = False
        self.load_data()

    def on_dates_edited(self):
        if self._setting_period:
            return
        self.period_selector.blockSignals(True)
        self.period_selector.setCurrentText("Custom")
        self.period_selector.blockSignals(False)
        self.load_data()

    def load_reference_data(self):
        repopulate_combo(
            self.cb_counterparty,
            [(cp.name, cp.id) for cp in self.ref_repo.get_all_counterparties()],
            placeholder=("All Stores", None),
            block_signals=True
        )
        repopulate_combo(
            self.cb_currency,
            [(cur.code, cur.code) for cur in self.ref_repo.get_all_currencies()],
            placeholder=("All Currencies", None),
            block_signals=True
        )

    def reset_filters(self):
        for widget in (self.search_input, self.cb_counterparty, self.cb_currency, self.period_selector):
            widget.blockSignals(True)
        self.search_input.clear()
        self.cb_counterparty.setCurrentIndex(0)
        self.cb_currency.setCurrentIndex(0)
        self.period_selector.setCurrentText("This month")
        for widget in (self.search_input, self.cb_counterparty, self.cb_currency, self.period_selector):
            widget.blockSignals(False)
        self.apply_period()

    def _add_row(self, record_id, record_type, record_date, cells):
        row = self.table.rowCount()
        self.table.insertRow(row)

        date_item = QTableWidgetItem(record_date.strftime("%Y-%m-%d"))
        date_item.setData(Qt.ItemDataRole.UserRole, record_id)
        date_item.setData(Qt.ItemDataRole.UserRole + 1, record_type)
        self.table.setItem(row, 0, date_item)

        for col, cell in enumerate(cells, start=1):
            self.table.setItem(row, col, cell if isinstance(cell, QTableWidgetItem) else QTableWidgetItem(cell))

    def load_data(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        filters = (
            self.start_date.date().toPyDate(),
            self.end_date.date().toPyDate(),
            self.cb_counterparty.currentData(),
            self.cb_currency.currentData(),
            self.search_input.text(),
        )
        totals = defaultdict(Decimal)

        if self.type_selector.currentText() == "Expenses":
            records = self.trans_repo.search_transactions(*filters)
            for tx in records:
                cp_name = tx.counterparty.name if tx.counterparty else "Unknown"
                if tx.location:
                    cp_name += f" ({tx.location.label})"
                self._add_row(tx.id, "expense", tx.date, [
                    cp_name,
                    tx.number or "",
                    number_item(tx.total_amount or 0),
                    number_item(len(tx.items), str(len(tx.items))),
                    tx.currency_code,
                    tx.payment_type.type if tx.payment_type else "Unknown",
                ])
                totals[tx.currency_code] += Decimal(str(tx.total_amount or 0))
            noun, empty = "receipt", "No receipts match these filters."
        else:
            records = self.income_repo.search_incomes(*filters)
            for inc in records:
                self._add_row(inc.id, "income", inc.date, [
                    inc.counterparty.name if inc.counterparty else "Unknown",
                    number_item(inc.net_amount),
                    inc.currency_code,
                    inc.payment_type.type if inc.payment_type else "Unknown",
                ])
                totals[inc.currency_code] += Decimal(str(inc.net_amount))
            noun, empty = "income record", "No income matches these filters."

        self.table.setSortingEnabled(True)

        if records:
            count = len(records)
            amounts = " · ".join(f"{totals[code]:,.2f} {code}" for code in sorted(totals))
            self.summary_label.setText(f"{count} {noun}{'s' if count != 1 else ''} · {amounts}")
        else:
            self.summary_label.setText(empty)

    def show_details(self, item):
        first_cell = self.table.item(item.row(), 0)
        if not first_cell:
            return
        rec_id = first_cell.data(Qt.ItemDataRole.UserRole)
        rec_type = first_cell.data(Qt.ItemDataRole.UserRole + 1)

        if rec_type == "expense":
            tx = self.trans_repo.get_transaction_with_items(rec_id)
            if tx:
                dialog = TransactionDetailDialog(tx, self)
                dialog.transaction_deleted.connect(self.load_data)
                dialog.transaction_changed.connect(self.load_data)
                dialog.exec()
        else:
            income = self.income_repo.get_income(rec_id)
            if income:
                dialog = IncomeDetailDialog(income, self)
                dialog.income_changed.connect(self.load_data)
                dialog.exec()
