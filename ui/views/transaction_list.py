from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel, QDialog,
    QGroupBox, QDateEdit, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, QDate
from repositories.transaction_repo import TransactionRepository
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository

class TransactionDetailDialog(QDialog):
    def __init__(self, transaction, parent=None):
        super().__init__(parent)
        self.tx_id = transaction.id

        counterparty_name = transaction.counterparty.name if transaction.counterparty else "Unknown"
        self.setWindowTitle(f"Receipt Details - {counterparty_name}")
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        discount_text = f" &nbsp;&nbsp;&nbsp; <b style='color:red;'>Discount:</b> - {transaction.discount:.2f}" if transaction.discount else ""
        info_text = (
            f"<b>Date:</b> {transaction.date} &nbsp;&nbsp;&nbsp; "
            f"<b>Receipt No:</b> {transaction.number or 'N/A'} &nbsp;&nbsp;&nbsp; "
            f"{discount_text} &nbsp;&nbsp;&nbsp; "
            f"<b>Total:</b> {transaction.total_amount:.2f} {transaction.currency_code}"
        )
        info_label = QLabel(info_text)
        info_label.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(info_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Product", "Amount", "Price", "Row Total"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row_idx, item in enumerate(transaction.items):
            self.table.insertRow(row_idx)

            base_name = item.product.name if item.product else "Unknown"
            display_name = f"{item.item_name_override} ({base_name})" if item.item_name_override else base_name
            self.table.setItem(row_idx, 0, QTableWidgetItem(display_name))

            amount_item = QTableWidgetItem(f"{item.amount:.3f}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 1, amount_item)

            price_item = QTableWidgetItem(f"{item.price:.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 2, price_item)

            row_total = item.amount * item.price
            if item.refund:
                row_total = -row_total

            total_item = QTableWidgetItem(f"{row_total:.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 3, total_item)

        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()

        delete_btn = QPushButton("Delete Transaction")
        delete_btn.setStyleSheet("background-color: #F44336; color: white;")
        delete_btn.clicked.connect(self.delete_tx)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def delete_tx(self):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to completely delete this transaction? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            TransactionRepository.delete_transaction(self.tx_id)
            self.accept()

            if hasattr(self.parent(), 'load_data'):
                self.parent().load_data()

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

        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout()

        self.type_selector = QComboBox()
        self.type_selector.addItems(["Expenses", "Income"])
        self.type_selector.currentIndexChanged.connect(self.on_type_changed)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-30))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())

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
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.end_date.setDate(QDate.currentDate())
        self.cb_counterparty.setCurrentIndex(0)
        self.cb_currency.setCurrentIndex(0)
        self.load_data()

    def load_data(self):
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

                cp_item = QTableWidgetItem(tx.counterparty.name if tx.counterparty else "Unknown")
                self.table.setItem(row_idx, 1, cp_item)

                receipt_item = QTableWidgetItem(tx.number or "")
                self.table.setItem(row_idx, 2, receipt_item)

                total_item = QTableWidgetItem(f"{tx.total_amount:.2f}")
                total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, 3, total_item)

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

                amount_item = QTableWidgetItem(f"{inc.net_amount:.2f}")
                amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, 2, amount_item)

                self.table.setItem(row_idx, 3, QTableWidgetItem(inc.currency_code))
                self.table.setItem(row_idx, 4, QTableWidgetItem(inc.payment_type.type if inc.payment_type else "Unknown"))

    def show_details(self, item):
        row = item.row()
        first_cell = self.table.item(row, 0)
        rec_id = first_cell.data(Qt.ItemDataRole.UserRole)
        rec_type = first_cell.data(Qt.ItemDataRole.UserRole + 1)

        if rec_type == "expense":
            tx = self.trans_repo.get_transaction_with_items(rec_id)
            if tx:
                dialog = TransactionDetailDialog(tx, self)
                dialog.exec()
        else:
            reply = QMessageBox.question(
                self, "Delete Income",
                "Do you want to completely delete this income record? This cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.income_repo.delete_income(rec_id)
                self.load_data()