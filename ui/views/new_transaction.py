from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDateEdit, QPushButton,
    QTableWidget, QHeaderView, QLabel, QDoubleSpinBox,
    QMessageBox, QCompleter, QCheckBox
)
from PyQt6.QtCore import QDate, Qt
from repositories.reference_repo import ReferenceRepository
from repositories.product_repo import ProductRepository
from repositories.transaction_repo import TransactionRepository

class PriceSpinBox(QDoubleSpinBox):
    def __init__(self, add_row_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_row_callback = add_row_callback

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.add_row_callback()

class NewTransactionView(QWidget):
    def __init__(self):
        super().__init__()
        self.ref_repo = ReferenceRepository()
        self.product_repo = ProductRepository()

        self.products = self.product_repo.get_all_products()

        self.setup_ui()
        self.load_reference_data()
        self.apply_smart_defaults()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)

        self.counterparty_input = QComboBox()
        self.counterparty_input.setEditable(True)
        self.counterparty_input.setPlaceholderText("Type or select store/person...")

        cp_completer = QCompleter(self.counterparty_input.model())
        cp_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        cp_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.counterparty_input.setCompleter(cp_completer)
        self.counterparty_input.currentTextChanged.connect(self.on_counterparty_changed)

        self.location_input = QComboBox()
        self.location_input.setVisible(False)
        self.location_label = QLabel("Location:")
        self.location_label.setVisible(False)

        self.receipt_number_input = QLineEdit()
        self.receipt_number_input.setPlaceholderText("e.g., Bon Fiscal number")

        self.payment_type_input = QComboBox()
        self.currency_input = QComboBox()

        form_layout.addRow("Date:", self.date_input)
        form_layout.addRow("Counterparty:", self.counterparty_input)
        form_layout.addRow(self.location_label, self.location_input)
        form_layout.addRow("Receipt No:", self.receipt_number_input)
        form_layout.addRow("Payment Type:", self.payment_type_input)
        form_layout.addRow("Currency:", self.currency_input)
        layout.addLayout(form_layout)

        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(["Product", "Override", "Amount", "Price", "Refund", "Total", ""])
        self.items_table.verticalHeader().setVisible(False)

        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.setColumnWidth(1, 120)
        self.items_table.setColumnWidth(2, 90)
        self.items_table.setColumnWidth(3, 90)
        self.items_table.setColumnWidth(4, 60)
        self.items_table.setColumnWidth(5, 80)
        self.items_table.setColumnWidth(6, 40)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.items_table)

        self.add_item_btn = QPushButton("Add Item Row")
        self.add_item_btn.clicked.connect(self.add_empty_row)
        layout.addWidget(self.add_item_btn)

        footer_layout = QHBoxLayout()

        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0.00, 9999.99)
        self.discount_input.setDecimals(2)
        self.discount_input.valueChanged.connect(self.calculate_totals)

        self.duplicate_warning_label = QLabel("⚠️ Duplicate Detected!")
        self.duplicate_warning_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 14px;")
        self.duplicate_warning_label.setVisible(False)

        self.total_label = QLabel("Total: 0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        self.save_btn = QPushButton("Save Transaction (Ctrl+S)")
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 15px;")
        self.save_btn.clicked.connect(self.save_transaction)

        footer_layout.addStretch()
        footer_layout.addWidget(QLabel("Discount:"))
        footer_layout.addWidget(self.discount_input)
        footer_layout.addSpacing(20)
        footer_layout.addWidget(self.duplicate_warning_label)
        footer_layout.addSpacing(10)
        footer_layout.addWidget(self.total_label)
        footer_layout.addWidget(self.save_btn)

        layout.addLayout(footer_layout)

        self.date_input.dateChanged.connect(self.check_for_duplicate)

        self.add_empty_row()

    def on_counterparty_changed(self, text):
        locations = self.ref_repo.get_locations_for_counterparty(text.strip())
        self.location_input.clear()

        if len(locations) > 1:
            for loc in locations:
                self.location_input.addItem(loc.label, userData=loc.id)
            self.location_label.setVisible(True)
            self.location_input.setVisible(True)
        else:
            self.location_label.setVisible(False)
            self.location_input.setVisible(False)

        self.check_for_duplicate()

    def load_reference_data(self):
        curr_currency = self.currency_input.currentData()
        curr_payment = self.payment_type_input.currentData()
        curr_cp = self.counterparty_input.currentText()

        self.products = self.product_repo.get_all_products(include_hidden=False)

        self.currency_input.clear()
        self.payment_type_input.clear()
        self.counterparty_input.clear()

        for cur in self.ref_repo.get_all_currencies():
            self.currency_input.addItem(cur.code, userData=cur.code)

        for pt in self.ref_repo.get_all_payment_types():
            self.payment_type_input.addItem(pt.type, userData=pt.id)

        for cp in self.ref_repo.get_all_counterparties():
            self.counterparty_input.addItem(cp.name, userData=cp.id)

        if curr_currency:
            idx = self.currency_input.findData(curr_currency)
            if idx >= 0: self.currency_input.setCurrentIndex(idx)

        if curr_payment:
            idx = self.payment_type_input.findData(curr_payment)
            if idx >= 0: self.payment_type_input.setCurrentIndex(idx)

        if curr_cp:
            self.counterparty_input.setCurrentText(curr_cp)

    def apply_smart_defaults(self):
        last_pt, last_cur = TransactionRepository.get_last_used_defaults()
        if last_pt:
            idx = self.payment_type_input.findData(last_pt)
            if idx >= 0: self.payment_type_input.setCurrentIndex(idx)
        if last_cur:
            idx = self.currency_input.findData(last_cur)
            if idx >= 0: self.currency_input.setCurrentIndex(idx)

    def add_empty_row(self):
        row_count = self.items_table.rowCount()

        if row_count > 0:
            last_product_cb = self.items_table.cellWidget(row_count - 1, 0)
            if last_product_cb and not last_product_cb.currentText().strip():
                last_product_cb.setFocus()
                return

        row_idx = self.items_table.rowCount()
        self.items_table.insertRow(row_idx)

        product_cb = QComboBox()
        product_cb.setEditable(True)
        product_cb.setPlaceholderText("Type product name...")

        prod_completer = QCompleter(product_cb.model())
        prod_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        prod_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        product_cb.setCompleter(prod_completer)

        for p in self.products:
            product_cb.addItem(p.name, userData=p.id)
        self.items_table.setCellWidget(row_idx, 0, product_cb)

        override_le = QLineEdit()
        override_le.setPlaceholderText("Optional...")
        self.items_table.setCellWidget(row_idx, 1, override_le)

        amount_sb = QDoubleSpinBox()
        amount_sb.setRange(0.001, 9999.999)
        amount_sb.setDecimals(3)
        amount_sb.setValue(1.0)
        amount_sb.valueChanged.connect(self.calculate_totals)
        self.items_table.setCellWidget(row_idx, 2, amount_sb)

        price_sb = PriceSpinBox(self.add_empty_row)
        price_sb.setRange(0.00, 99999.99)
        price_sb.setDecimals(2)
        price_sb.valueChanged.connect(self.calculate_totals)
        self.items_table.setCellWidget(row_idx, 3, price_sb)

        refund_cb = QCheckBox()
        refund_cb.stateChanged.connect(self.calculate_totals)
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(refund_cb)
        chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk_layout.setContentsMargins(0,0,0,0)
        chk_widget.refund_cb = refund_cb
        self.items_table.setCellWidget(row_idx, 4, chk_widget)

        row_total_lbl = QLabel("0.00")
        row_total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.items_table.setCellWidget(row_idx, 5, row_total_lbl)

        del_btn = QPushButton("X")
        del_btn.setStyleSheet("color: red; font-weight: bold; max-width: 30px;")
        del_btn.clicked.connect(lambda checked, b=del_btn: self.remove_row(b))
        self.items_table.setCellWidget(row_idx, 6, del_btn)

        product_cb.setFocus()

    def remove_row(self, btn):
        for row in range(self.items_table.rowCount()):
            if self.items_table.cellWidget(row, 6) == btn:
                self.items_table.removeRow(row)
                self.calculate_totals()
                break

    def calculate_totals(self, *args):
        raw_total = 0.0

        for row in range(self.items_table.rowCount()):
            amount_widget = self.items_table.cellWidget(row, 2)
            price_widget = self.items_table.cellWidget(row, 3)
            refund_widget = self.items_table.cellWidget(row, 4)
            total_label = self.items_table.cellWidget(row, 5)

            if amount_widget and price_widget and total_label and refund_widget:
                amount = amount_widget.value()
                price = price_widget.value()
                is_refund = refund_widget.refund_cb.isChecked()

                row_total = amount * price
                if is_refund:
                    row_total = -row_total

                total_label.setText(f"{row_total:.2f}")
                raw_total += row_total

        grand_total = raw_total - self.discount_input.value()
        self.total_label.setText(f"Total: {grand_total:.2f}")

        self.check_for_duplicate()

    def check_for_duplicate(self):
        counterparty_name = self.counterparty_input.currentText().strip()

        total_text = self.total_label.text().replace("Total: ", "")
        try:
            final_amount = float(total_text)
        except ValueError:
            final_amount = 0.0

        if not counterparty_name or final_amount <= 0:
            self.duplicate_warning_label.setVisible(False)
            return

        date = self.date_input.date().toPyDate()

        is_duplicate = TransactionRepository.check_potential_duplicate(date, counterparty_name, final_amount)
        self.duplicate_warning_label.setVisible(is_duplicate)

    def save_transaction(self):
        counterparty_name = self.counterparty_input.currentText().strip()
        if not counterparty_name:
            QMessageBox.warning(self, "Validation Error", "Please specify a counterparty (e.g. store name).")
            return

        items_data = []
        raw_total = 0.0

        for row in range(self.items_table.rowCount()):
            product_cb = self.items_table.cellWidget(row, 0)
            override_le = self.items_table.cellWidget(row, 1)
            amount_sb = self.items_table.cellWidget(row, 2)
            price_sb = self.items_table.cellWidget(row, 3)
            refund_widget = self.items_table.cellWidget(row, 4)

            if not product_cb:
                continue

            product_name = product_cb.currentText().strip()
            if not product_name:
                continue

            amount = amount_sb.value()
            price = price_sb.value()
            is_refund = refund_widget.refund_cb.isChecked()

            items_data.append({
                "product_name": product_name,
                "override": override_le.text().strip() or None,
                "amount": amount,
                "price": price,
                "refund": is_refund
            })

            line_total = amount * price
            if is_refund:
                raw_total -= line_total
            else:
                raw_total += line_total

        if not items_data:
            QMessageBox.warning(self, "Validation Error", "Please add at least one valid item.")
            return

        date = self.date_input.date().toPyDate()
        receipt_no = self.receipt_number_input.text().strip() or None
        payment_type_id = self.payment_type_input.currentData()
        currency_code = self.currency_input.currentData()
        discount = self.discount_input.value()

        final_amount = raw_total - discount

        location_id = None
        if self.location_input.isVisible() and self.location_input.count() > 0:
            location_id = self.location_input.currentData()

        is_duplicate = TransactionRepository.check_potential_duplicate(date, counterparty_name, final_amount)
        if is_duplicate:
            reply = QMessageBox.question(
                self,
                "Potential Duplicate Detected",
                f"A transaction at '{counterparty_name}' for {final_amount:.2f} on {date} already exists.\n\n"
                "Are you sure this is a new, separate receipt and not the credit card copy of the same purchase?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            TransactionRepository.save_transaction(
                date=date,
                counterparty_name=counterparty_name,
                receipt_no=receipt_no,
                payment_type_id=payment_type_id,
                currency_code=currency_code,
                items_data=items_data,
                location_id=location_id,
                discount=discount
            )
            QMessageBox.information(self, "Success", "Transaction saved successfully!")
            self.reset_form()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save transaction:\n{str(e)}")

    def reset_form(self):
        self.receipt_number_input.clear()
        self.discount_input.setValue(0.0)
        self.items_table.setRowCount(0)
        self.date_input.setDate(QDate.currentDate())

        self.products = self.product_repo.get_all_products()
        self.load_reference_data()
        self.apply_smart_defaults()
        self.add_empty_row()
        self.calculate_totals()

        self.counterparty_input.setFocus()