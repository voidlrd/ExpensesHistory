from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel,
    QGroupBox, QDateEdit, QComboBox
)
from PyQt6.QtCore import Qt, QDate
from repositories.transaction_repo import TransactionRepository
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository
from ui.views.record_dialogs import IncomeDetailDialog, TransactionDetailDialog, TransactionEditDialog
from ui.widgets import number_item, repopulate_combo

__all__ = ["TransactionListView", "TransactionDetailDialog", "TransactionEditDialog", "IncomeDetailDialog"]

EXPENSE_COLUMNS = ["Date", "Counterparty", "Receipt No", "Total", "Currency", "Payment Type"]
INCOME_COLUMNS = ["Date", "Source", "Net Amount", "Currency", "Payment Type"]

class TransactionListView(QWidget):
    def __init__(self):
        super().__init__()
        self.trans_repo = TransactionRepository()
        self.income_repo = IncomeRepository()
        self.ref_repo = ReferenceRepository()
        self.setup_ui()
        self.load_reference_data()
        self.on_type_changed()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        title_label = QLabel("Transaction History")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        top_bar.addWidget(title_label)
        layout.addLayout(top_bar)

        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout()

        self.type_selector = QComboBox()
        self.type_selector.addItems(["Expenses", "Income"])
        self.type_selector.currentIndexChanged.connect(self.on_type_changed)

        today = QDate.currentDate()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate(today.year(), today.month(), 1))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(today)

        self.cb_counterparty = QComboBox()
        self.cb_currency = QComboBox()

        for label, widget in (("Type:", self.type_selector), ("From:", self.start_date), ("To:", self.end_date),
                              ("Source/Store:", self.cb_counterparty), ("Currency:", self.cb_currency)):
            filter_layout.addWidget(QLabel(label))
            filter_layout.addWidget(widget)

        self.apply_btn = QPushButton("Apply Filters")
        self.apply_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 4px 12px;")
        self.apply_btn.clicked.connect(self.load_data)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_filters)

        filter_layout.addStretch()
        filter_layout.addWidget(self.reset_btn)
        filter_layout.addWidget(self.apply_btn)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        self.table = QTableWidget(0, len(EXPENSE_COLUMNS))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.show_details)

        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def on_type_changed(self):
        columns = EXPENSE_COLUMNS if self.type_selector.currentText() == "Expenses" else INCOME_COLUMNS
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.load_data()

    def load_reference_data(self):
        repopulate_combo(
            self.cb_counterparty,
            [(cp.name, cp.id) for cp in self.ref_repo.get_all_counterparties()],
            placeholder=("All Stores", None)
        )
        repopulate_combo(
            self.cb_currency,
            [(cur.code, cur.code) for cur in self.ref_repo.get_all_currencies()],
            placeholder=("All Currencies", None)
        )

    def reset_filters(self):
        today = QDate.currentDate()
        self.start_date.setDate(QDate(today.year(), today.month(), 1))
        self.end_date.setDate(today)
        self.cb_counterparty.setCurrentIndex(0)
        self.cb_currency.setCurrentIndex(0)
        self.load_data()

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

        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        cp_id = self.cb_counterparty.currentData()
        curr = self.cb_currency.currentData()

        if self.type_selector.currentText() == "Expenses":
            for tx in self.trans_repo.get_all_transactions(start, end, cp_id, curr):
                cp_name = tx.counterparty.name if tx.counterparty else "Unknown"
                if tx.location:
                    cp_name += f" ({tx.location.label})"
                self._add_row(tx.id, "expense", tx.date, [
                    cp_name,
                    tx.number or "",
                    number_item(tx.total_amount or 0),
                    tx.currency_code,
                    tx.payment_type.type if tx.payment_type else "Unknown",
                ])
        else:
            for inc in self.income_repo.get_all_incomes(start, end, cp_id, curr):
                self._add_row(inc.id, "income", inc.date, [
                    inc.counterparty.name if inc.counterparty else "Unknown",
                    number_item(inc.net_amount),
                    inc.currency_code,
                    inc.payment_type.type if inc.payment_type else "Unknown",
                ])

        self.table.setSortingEnabled(True)

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
