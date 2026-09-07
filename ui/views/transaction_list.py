from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel, QDialog,
    QGroupBox, QDateEdit, QComboBox, QMessageBox, QFormLayout, QDoubleSpinBox
)
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from repositories.transaction_repo import TransactionRepository, line_total
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository
from ui.views.new_transaction import NewTransactionView

class NumericItem(QTableWidgetItem):
    def __init__(self, value, text=None):
        super().__init__(text if text is not None else f"{value:.2f}")
        self.value = value
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self.value < other.value
        return super().__lt__(other)

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
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this income record? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
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
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 50)
        self.table.setColumnWidth(5, 60)
        self.table.setColumnWidth(6, 70)
        self.table.setColumnWidth(7, 80)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        for row_idx, item in enumerate(transaction.items):
            self.table.insertRow(row_idx)

            base_name = item.product.name if item.product else "Unknown"
            display_name = f"{item.item_name_override} ({base_name})" if item.item_name_override else base_name
            self.table.setItem(row_idx, 0, QTableWidgetItem(display_name))

            cat_name = item.product.category.name if (item.product and item.product.category) else ""
            self.table.setItem(row_idx, 1, QTableWidgetItem(cat_name))

            brand_name = item.product.brand if item.product else ""
            self.table.setItem(row_idx, 2, QTableWidgetItem(brand_name))

            
            amount_val = float(item.amount)
            if amount_val.is_integer():
                amount_str = str(int(amount_val))
            else:
                amount_str = f"{amount_val:.3f}".rstrip('0').rstrip('.')
            
            self.table.setItem(row_idx, 3, NumericItem(float(item.amount), amount_str))

            unit_name = item.product.unit_of_measure if item.product else ""
            self.table.setItem(row_idx, 4, QTableWidgetItem(unit_name))

            self.table.setItem(row_idx, 5, NumericItem(float(item.price)))

            disc_item = NumericItem(float(item.discount))
            if item.discount > 0:
                disc_item.setForeground(QBrush(QColor("red")))
            self.table.setItem(row_idx, 6, disc_item)

            row_total = line_total(item.amount, item.price, item.discount, item.refund)
            self.table.setItem(row_idx, 7, NumericItem(float(row_total)))

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
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to completely delete this transaction? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            TransactionRepository.delete_transaction(self.tx_id)

            self.transaction_deleted.emit()
            self.accept()

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

        filter_layout.addWidget(QLabel("Type:"))
        filter_layout.addWidget(self.type_selector)
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.end_date)
        filter_layout.addWidget(QLabel("Source/Store:"))
        filter_layout.addWidget(self.cb_counterparty)
        filter_layout.addWidget(QLabel("Currency:"))
        filter_layout.addWidget(self.cb_currency)

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

        self.table = QTableWidget(0, 6)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self.show_details)

        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def on_type_changed(self):
        if self.type_selector.currentText() == "Expenses":
            self.table.setColumnCount(6)
            self.table.setHorizontalHeaderLabels([
                "Date", "Counterparty", "Receipt No", "Total", "Currency", "Payment Type"
            ])
        else:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels([
                "Date", "Source", "Net Amount", "Currency", "Payment Type"
            ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.load_data()

    def load_reference_data(self):
        curr_cp = self.cb_counterparty.currentData()
        curr_cur = self.cb_currency.currentData()

        self.cb_counterparty.clear()
        self.cb_counterparty.addItem("All Stores", userData=None)
        for cp in self.ref_repo.get_all_counterparties():
            self.cb_counterparty.addItem(cp.name, userData=cp.id)

        self.cb_currency.clear()
        self.cb_currency.addItem("All Currencies", userData=None)
        for cur in self.ref_repo.get_all_currencies():
            self.cb_currency.addItem(cur.code, userData=cur.code)

        if curr_cp:
            idx = self.cb_counterparty.findData(curr_cp)
            if idx >= 0: self.cb_counterparty.setCurrentIndex(idx)
        if curr_cur:
            idx = self.cb_currency.findData(curr_cur)
            if idx >= 0: self.cb_currency.setCurrentIndex(idx)

    def reset_filters(self):
        today = QDate.currentDate()
        self.start_date.setDate(QDate(today.year(), today.month(), 1))
        self.end_date.setDate(today)
        self.cb_counterparty.setCurrentIndex(0)
        self.cb_currency.setCurrentIndex(0)
        self.load_data()

    def load_data(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        cp_id = self.cb_counterparty.currentData()
        curr = self.cb_currency.currentData()
        record_type = self.type_selector.currentText()

        if record_type == "Expenses":
            transactions = self.trans_repo.get_all_transactions(start, end, cp_id, curr)
            for row_idx, tx in enumerate(transactions):
                self.table.insertRow(row_idx)

                date_item = QTableWidgetItem(tx.date.strftime("%Y-%m-%d"))
                date_item.setData(Qt.ItemDataRole.UserRole, tx.id)
                date_item.setData(Qt.ItemDataRole.UserRole + 1, "expense")
                self.table.setItem(row_idx, 0, date_item)

                cp_name = tx.counterparty.name if tx.counterparty else "Unknown"
                if tx.location:
                    cp_name += f" ({tx.location.label})"

                cp_item = QTableWidgetItem(cp_name)
                self.table.setItem(row_idx, 1, cp_item)

                receipt_item = QTableWidgetItem(tx.number or "")
                self.table.setItem(row_idx, 2, receipt_item)

                self.table.setItem(row_idx, 3, NumericItem(float(tx.total_amount or 0)))

                curr_item = QTableWidgetItem(tx.currency_code)
                self.table.setItem(row_idx, 4, curr_item)

                pt_item = QTableWidgetItem(tx.payment_type.type if tx.payment_type else "Unknown")
                self.table.setItem(row_idx, 5, pt_item)
        else:
            incomes = self.income_repo.get_all_incomes(start, end, cp_id, curr)
            for row_idx, inc in enumerate(incomes):
                self.table.insertRow(row_idx)

                date_item = QTableWidgetItem(inc.date.strftime("%Y-%m-%d"))
                date_item.setData(Qt.ItemDataRole.UserRole, inc.id)
                date_item.setData(Qt.ItemDataRole.UserRole + 1, "income")
                self.table.setItem(row_idx, 0, date_item)

                cp_item = QTableWidgetItem(inc.counterparty.name if inc.counterparty else "Unknown")
                self.table.setItem(row_idx, 1, cp_item)

                self.table.setItem(row_idx, 2, NumericItem(float(inc.net_amount)))

                self.table.setItem(row_idx, 3, QTableWidgetItem(inc.currency_code))
                self.table.setItem(row_idx, 4, QTableWidgetItem(inc.payment_type.type if inc.payment_type else "Unknown"))

        self.table.setSortingEnabled(True)

    def show_details(self, item):
        row = item.row()
        first_cell = self.table.item(row, 0)
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