from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLabel, QDialog, QDateEdit, QComboBox, QMessageBox, QFormLayout, QDoubleSpinBox
)
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtCore import QDate, Qt, pyqtSignal
from decimal import Decimal
from repositories.transaction_repo import TransactionRepository, line_total
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository
from ui.views.new_transaction import NewTransactionView
from ui.widgets import SortItem, ask_yes_no, format_amount, number_item
from units import describe_package, normalize_unit

class TransactionEditDialog(QDialog):
    def __init__(self, tx_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Transaction")
        self.resize(1000, 600)

        layout = QVBoxLayout(self)
        self.form = NewTransactionView(edit_tx_id=tx_id)
        layout.addWidget(self.form)
        self.form.transaction_saved.connect(self.accept)


class IncomeDetailDialog(QDialog):
    income_changed = pyqtSignal()

    def __init__(self, income, parent=None):
        super().__init__(parent)
        self.income_id = income.id
        self.ref_repo = ReferenceRepository()

        self.setWindowTitle("Income Details")
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate(income.date.year, income.date.month, income.date.day))

        self.counterparty_input = QComboBox()
        self.counterparty_input.setEditable(True)
        self.counterparty_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 9999999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(float(income.net_amount))

        self.currency_input = QComboBox()
        self.payment_type_input = QComboBox()

        for cp in self.ref_repo.get_all_counterparties():
            self.counterparty_input.addItem(cp.name, userData=cp.id)
        for cur in self.ref_repo.get_all_currencies():
            self.currency_input.addItem(cur.code, userData=cur.code)
        for pt in self.ref_repo.get_all_payment_types():
            self.payment_type_input.addItem(pt.type, userData=pt.id)

        if income.counterparty:
            self.counterparty_input.setCurrentText(income.counterparty.name)
        idx = self.currency_input.findData(income.currency_code)
        if idx >= 0:
            self.currency_input.setCurrentIndex(idx)
        idx = self.payment_type_input.findData(income.payment_type_id)
        if idx >= 0:
            self.payment_type_input.setCurrentIndex(idx)

        form.addRow("Date:", self.date_input)
        form.addRow("Source:", self.counterparty_input)
        form.addRow("Net Amount:", self.amount_input)
        form.addRow("Currency:", self.currency_input)
        form.addRow("Payment Type:", self.payment_type_input)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        delete_btn = QPushButton("Delete Income")
        delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        delete_btn.clicked.connect(self.delete_income)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        save_btn.clicked.connect(self.save_changes)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def save_changes(self):
        name = self.counterparty_input.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please specify the income source.")
            return

        try:
            IncomeRepository.update_income(
                self.income_id,
                date=self.date_input.date().toPyDate(),
                counterparty_name=name,
                net_amount=self.amount_input.value(),
                currency_code=self.currency_input.currentData(),
                payment_type_id=self.payment_type_input.currentData()
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", "Failed to update income:\n" + str(e))
            return

        self.income_changed.emit()
        self.accept()

    def delete_income(self):
        if ask_yes_no(self, "Confirm Delete", "Delete this income record? This cannot be undone."):
            IncomeRepository.delete_income(self.income_id)
            self.income_changed.emit()
            self.accept()


class TransactionDetailDialog(QDialog):
    transaction_deleted = pyqtSignal()
    transaction_changed = pyqtSignal()

    def __init__(self, transaction, parent=None):
        super().__init__(parent)
        self.tx_id = transaction.id

        counterparty_name = transaction.counterparty.name if transaction.counterparty else "Unknown"
        if transaction.location:
            counterparty_name += f" ({transaction.location.label})"

        self.setWindowTitle(f"Receipt Details - {counterparty_name}")
        self.resize(800, 450)

        layout = QVBoxLayout(self)

        info_text = (
            f"<b>Date:</b> {transaction.date} &nbsp;&nbsp;&nbsp; "
            f"<b>Receipt No:</b> {transaction.number or 'N/A'} &nbsp;&nbsp;&nbsp; "
            f"<b>Total:</b> {transaction.total_amount:.2f} {transaction.currency_code}"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Product", "Category", "Brand", "Amount", "Unit", "Price", "Discount", "Row Total"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, width in ((1, 120), (2, 90), (3, 60), (4, 90), (5, 60), (6, 70), (7, 80)):
            self.table.setColumnWidth(col, width)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        for row_idx, item in enumerate(transaction.items):
            self.table.insertRow(row_idx)
            product = item.product

            base_name = product.name if product else "Unknown"
            display_name = f"{item.item_name_override} ({base_name})" if item.item_name_override else base_name
            self.table.setItem(row_idx, 0, QTableWidgetItem(display_name))
            self.table.setItem(row_idx, 1, QTableWidgetItem(product.category.name if product and product.category else ""))
            self.table.setItem(row_idx, 2, QTableWidgetItem(product.brand if product else ""))
            self.table.setItem(row_idx, 3, number_item(item.amount, format_amount(item.amount)))

            unit_name = ""
            if product:
                unit_name = normalize_unit(product.unit_of_measure)
                package = describe_package(product.package_size, product.package_unit)
                if package:
                    unit_name = f"{unit_name} ({package})"
            self.table.setItem(row_idx, 4, QTableWidgetItem(unit_name))

            self.table.setItem(row_idx, 5, number_item(item.price))
            disc_item = number_item(item.discount)
            if item.discount > 0:
                disc_item.setForeground(QBrush(QColor("red")))
            self.table.setItem(row_idx, 6, disc_item)
            self.table.setItem(row_idx, 7, number_item(line_total(item.amount, item.price, item.discount, item.refund)))

        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()

        delete_btn = QPushButton("Delete Transaction")
        delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        delete_btn.clicked.connect(self.delete_tx)

        edit_btn = QPushButton("Edit Transaction")
        edit_btn.setStyleSheet("background-color: #2196F3; color: white;")
        edit_btn.clicked.connect(self.edit_tx)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(edit_btn)

        layout.addLayout(btn_layout)

    def edit_tx(self):
        dialog = TransactionEditDialog(self.tx_id, self)
        if dialog.exec():
            self.transaction_changed.emit()
            self.accept()

    def delete_tx(self):
        if ask_yes_no(self, "Confirm Delete",
                      "Are you sure you want to completely delete this transaction? This cannot be undone."):
            TransactionRepository.delete_transaction(self.tx_id)
            self.transaction_deleted.emit()
            self.accept()


class MonthLinesDialog(QDialog):
    """Receipt lines behind a dashboard row; double-click opens the receipt."""
    receipts_changed = pyqtSignal()

    COLUMNS = ["Date", "Store", "Product", "Amount", "Price", "Discount", "Total"]

    def __init__(self, title, currency_code, loader, parent=None):
        super().__init__(parent)
        self.currency_code = currency_code
        self.loader = loader

        self.setWindowTitle(title)
        self.resize(820, 480)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col in range(len(self.COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(lambda item: self.open_receipt(item.row()))
        layout.addWidget(self.table)

        footer = QHBoxLayout()
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold;")
        hint = QLabel("Double-click a line to open its receipt.")
        hint.setStyleSheet("color: #9E9E9E;")
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(self.summary_label)
        footer.addSpacing(15)
        footer.addWidget(hint)
        footer.addStretch()
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        self.load()

    def load(self):
        lines = self.loader()
        total = Decimal(0)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row, item in enumerate(lines):
            self.table.insertRow(row)
            tx = item.transaction
            product = item.product
            unit = normalize_unit(product.unit_of_measure) if product else ""
            name = product.name if product else "Unknown"
            if item.item_name_override:
                name = f"{item.item_name_override} ({name})"
            row_total = line_total(item.amount, item.price, item.discount, item.refund)
            total += row_total

            date_item = SortItem(str(tx.date))
            date_item.setData(Qt.ItemDataRole.UserRole, tx.id)
            self.table.setItem(row, 0, date_item)
            self.table.setItem(row, 1, QTableWidgetItem(tx.counterparty.name if tx.counterparty else "Unknown"))
            self.table.setItem(row, 2, QTableWidgetItem(name))
            self.table.setItem(row, 3, number_item(item.amount, f"{format_amount(item.amount)} {unit}".strip()))
            self.table.setItem(row, 4, number_item(item.price))
            self.table.setItem(row, 5, number_item(item.discount))
            self.table.setItem(row, 6, number_item(row_total))
        self.table.setSortingEnabled(True)

        count = len(lines)
        self.summary_label.setText(f"{count} line{'s' if count != 1 else ''} · {total:,.2f} {self.currency_code}")

    def open_receipt(self, row):
        date_item = self.table.item(row, 0)
        if date_item is None:
            return
        tx = TransactionRepository.get_transaction_with_items(date_item.data(Qt.ItemDataRole.UserRole))
        if tx is None:
            return
        dialog = TransactionDetailDialog(tx, self)
        dialog.transaction_deleted.connect(self._receipts_changed)
        dialog.transaction_changed.connect(self._receipts_changed)
        dialog.exec()

    def _receipts_changed(self):
        self.load()
        self.receipts_changed.emit()
