from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDateEdit, QPushButton,
    QTableWidget, QHeaderView, QLabel, QDoubleSpinBox,
    QMessageBox, QCompleter, QCheckBox
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from decimal import Decimal
from repositories.reference_repo import ReferenceRepository
from repositories.product_repo import ProductRepository
from repositories.transaction_repo import TransactionRepository, line_total

class FastTabSpinBox(QDoubleSpinBox):
    def __init__(self, add_row_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_row_callback = add_row_callback

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.add_row_callback()
            return
        super().keyPressEvent(event)

class NewTransactionView(QWidget):
    transaction_saved = pyqtSignal()

    def __init__(self, edit_tx_id=None):
        super().__init__()
        self.ref_repo = ReferenceRepository()
        self.product_repo = ProductRepository()

        self.edit_tx_id = edit_tx_id
        self.products = []
        self.raw_total = Decimal(0)

        self._dup_timer = QTimer(self)
        self._dup_timer.setSingleShot(True)
        self._dup_timer.setInterval(250)
        self._dup_timer.timeout.connect(self._run_duplicate_check)

        self._loc_timer = QTimer(self)
        self._loc_timer.setSingleShot(True)
        self._loc_timer.setInterval(250)
        self._loc_timer.timeout.connect(self._reload_locations)

        self.setup_ui()
        self.load_reference_data()

        if self.edit_tx_id:
            self.load_transaction(self.edit_tx_id)
        else:
            self.apply_smart_defaults()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)

        self.counterparty_input = QComboBox()
        self.counterparty_input.setEditable(True)
        self.counterparty_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.counterparty_input.setPlaceholderText("Type or select store/person...")

        cp_completer = QCompleter(self.counterparty_input.model())
        cp_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        cp_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.counterparty_input.setCompleter(cp_completer)

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

        self.items_table = QTableWidget(0, 8)
        self.items_table.setHorizontalHeaderLabels(["Product", "Override", "Amount", "Price", "Discount", "Refund", "Total", ""])
        self.items_table.verticalHeader().setVisible(False)

        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        self.items_table.setColumnWidth(1, 150)

        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.items_table)

        self.add_item_btn = QPushButton("Add Item Row")
        self.add_item_btn.clicked.connect(self.add_empty_row)
        layout.addWidget(self.add_item_btn)

        footer_layout = QHBoxLayout()
        self.duplicate_warning_label = QLabel("⚠️ Duplicate Detected!")
        self.duplicate_warning_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 14px;")
        self.duplicate_warning_label.setVisible(False)

        self.total_label = QLabel("Total: 0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        save_text = "Update Transaction (Ctrl+S)" if self.edit_tx_id else "Save Transaction (Ctrl+S)"
        self.save_btn = QPushButton(save_text)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 15px;")
        self.save_btn.clicked.connect(self.save_transaction)

        footer_layout.addStretch()
        footer_layout.addWidget(self.duplicate_warning_label)
        footer_layout.addSpacing(10)
        footer_layout.addWidget(self.total_label)
        footer_layout.addWidget(self.save_btn)

        layout.addLayout(footer_layout)

        self.date_input.dateChanged.connect(self.check_for_duplicate)
        self.currency_input.currentIndexChanged.connect(self.check_for_duplicate)
        self.counterparty_input.currentTextChanged.connect(self.on_counterparty_changed)

        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save_transaction)

        self.add_empty_row()

    def on_counterparty_changed(self, text):
        self._loc_timer.start()
        self.check_for_duplicate()

    def _reload_locations(self):
        name = self.counterparty_input.currentText().strip()
        previous = self.location_input.currentData()
        locations = self.ref_repo.get_locations_for_counterparty(name)

        self.location_input.blockSignals(True)
        self.location_input.clear()
        for loc in locations:
            self.location_input.addItem(loc.label, userData=loc.id)
        if previous:
            idx = self.location_input.findData(previous)
            if idx >= 0:
                self.location_input.setCurrentIndex(idx)
        self.location_input.blockSignals(False)

        has_locations = bool(locations)
        self.location_label.setVisible(has_locations)
        self.location_input.setVisible(has_locations)

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

    def load_transaction(self, tx_id):
        tx = TransactionRepository.get_transaction_with_items(tx_id)
        if not tx:
            QMessageBox.warning(self, "Error", "This transaction no longer exists.")
            return

        self.date_input.setDate(QDate(tx.date.year, tx.date.month, tx.date.day))
        self.receipt_number_input.setText(tx.number or "")

        if tx.counterparty:
            self.counterparty_input.setCurrentText(tx.counterparty.name)
        self._reload_locations()
        if tx.location_id:
            idx = self.location_input.findData(tx.location_id)
            if idx >= 0:
                self.location_input.setCurrentIndex(idx)

        idx = self.payment_type_input.findData(tx.payment_type_id)
        if idx >= 0:
            self.payment_type_input.setCurrentIndex(idx)
        idx = self.currency_input.findData(tx.currency_code)
        if idx >= 0:
            self.currency_input.setCurrentIndex(idx)

        self.items_table.setRowCount(0)
        for item in tx.items:
            self.add_empty_row()
            row = self.items_table.rowCount() - 1
            name = item.product.name if item.product else ""
            self.items_table.cellWidget(row, 0).setCurrentText(name)
            self.items_table.cellWidget(row, 1).setText(item.item_name_override or "")
            self.items_table.cellWidget(row, 2).setValue(float(item.amount))
            self.items_table.cellWidget(row, 3).setValue(float(item.price))
            self.items_table.cellWidget(row, 4).setValue(float(item.discount))
            self.items_table.cellWidget(row, 5).refund_cb.setChecked(item.refund)

        if self.items_table.rowCount() == 0:
            self.add_empty_row()

        self.calculate_totals()

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
            if last_product_cb is not None and not last_product_cb.currentText().strip():
                last_product_cb.setFocus()
                return

        row_idx = self.items_table.rowCount()
        self.items_table.insertRow(row_idx)

        product_cb = QComboBox()
        product_cb.setEditable(True)
        product_cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
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

        price_sb = QDoubleSpinBox()
        price_sb.setRange(0.00, 99999.99)
        price_sb.setDecimals(2)
        price_sb.valueChanged.connect(self.calculate_totals)
        self.items_table.setCellWidget(row_idx, 3, price_sb)

        disc_sb = FastTabSpinBox(self.add_empty_row)
        disc_sb.setRange(0.00, 99999.99)
        disc_sb.setDecimals(2)
        disc_sb.valueChanged.connect(self.calculate_totals)
        self.items_table.setCellWidget(row_idx, 4, disc_sb)

        refund_cb = QCheckBox()
        refund_cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        refund_cb.checkStateChanged.connect(self.calculate_totals)
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(refund_cb)
        chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk_layout.setContentsMargins(0,0,0,0)
        chk_widget.refund_cb = refund_cb
        self.items_table.setCellWidget(row_idx, 5, chk_widget)

        row_total_lbl = QLabel("0.00")
        row_total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.items_table.setCellWidget(row_idx, 6, row_total_lbl)

        del_btn = QPushButton("X")
        del_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        del_btn.setStyleSheet("color: red; font-weight: bold; max-width: 30px;")
        del_btn.clicked.connect(lambda checked, b=del_btn: self.remove_row(b))
        self.items_table.setCellWidget(row_idx, 7, del_btn)

        product_cb.setFocus()

    def remove_row(self, btn):
        for row in range(self.items_table.rowCount()):
            if self.items_table.cellWidget(row, 7) == btn:
                self.items_table.removeRow(row)
                self.calculate_totals()
                break

    def calculate_totals(self, *args):
        raw_total = Decimal(0)

        for row in range(self.items_table.rowCount()):
            amount_widget = self.items_table.cellWidget(row, 2)
            price_widget = self.items_table.cellWidget(row, 3)
            disc_widget = self.items_table.cellWidget(row, 4)
            refund_widget = self.items_table.cellWidget(row, 5)
            total_label = self.items_table.cellWidget(row, 6)

            if None not in (amount_widget, price_widget, disc_widget, total_label, refund_widget):
                row_total = line_total(
                    amount_widget.value(),
                    price_widget.value(),
                    disc_widget.value(),
                    refund_widget.refund_cb.isChecked()
                )
                total_label.setText(f"{row_total:.2f}")
                raw_total += row_total

        self.raw_total = raw_total
        self.total_label.setText(f"Total: {raw_total:.2f}")

        self.check_for_duplicate()

    def check_for_duplicate(self):
        self._dup_timer.start()

    def _run_duplicate_check(self):
        counterparty_name = self.counterparty_input.currentText().strip()

        if not counterparty_name or self.raw_total == 0:
            self.duplicate_warning_label.setVisible(False)
            return

        is_duplicate = TransactionRepository.check_potential_duplicate(
            self.date_input.date().toPyDate(),
            counterparty_name,
            self.raw_total,
            self.currency_input.currentData(),
            exclude_id=self.edit_tx_id
        )
        self.duplicate_warning_label.setVisible(is_duplicate)

    def _commit_pending_edits(self):
        # A combo popup steals the click that triggers Save; settle editors first.
        focused = self.focusWidget()
        if isinstance(focused, QComboBox) and focused.completer():
            focused.completer().popup().hide()
        for row in range(self.items_table.rowCount()):
            for col in (2, 3, 4):
                widget = self.items_table.cellWidget(row, col)
                if widget is not None:
                    widget.interpretText()

    def save_transaction(self):
        self._commit_pending_edits()
        self.calculate_totals()

        counterparty_name = self.counterparty_input.currentText().strip()
        if not counterparty_name:
            QMessageBox.warning(self, "Validation Error", "Please specify a counterparty (e.g. store name).")
            self.counterparty_input.setFocus()
            return

        items_data = []
        blank_rows = 0

        for row in range(self.items_table.rowCount()):
            product_cb = self.items_table.cellWidget(row, 0)
            override_le = self.items_table.cellWidget(row, 1)
            amount_sb = self.items_table.cellWidget(row, 2)
            price_sb = self.items_table.cellWidget(row, 3)
            disc_sb = self.items_table.cellWidget(row, 4)
            refund_widget = self.items_table.cellWidget(row, 5)

            # never test a QComboBox for truth: PyQt maps __len__ to count()
            if None in (product_cb, override_le, amount_sb, price_sb, disc_sb, refund_widget):
                continue

            product_name = product_cb.currentText().strip()
            if not product_name:
                blank_rows += 1
                continue

            items_data.append({
                "product_name": product_name,
                "override": override_le.text().strip() or None,
                "amount": amount_sb.value(),
                "price": price_sb.value(),
                "discount": disc_sb.value(),
                "refund": refund_widget.refund_cb.isChecked()
            })

        if not items_data:
            if blank_rows:
                message = (f"{blank_rows} item row(s) have no product name.\n\n"
                           "Type a product name in the first column before saving.")
            else:
                message = "Please add at least one item row."
            QMessageBox.warning(self, "Validation Error", message)
            first_row_cb = self.items_table.cellWidget(0, 0)
            if first_row_cb is not None:
                first_row_cb.setFocus()
            return

        date = self.date_input.date().toPyDate()
        receipt_no = self.receipt_number_input.text().strip() or None
        payment_type_id = self.payment_type_input.currentData()
        currency_code = self.currency_input.currentData()

        location_id = None
        if self.location_input.count() > 0 and self.location_input.isVisibleTo(self):
            location_id = self.location_input.currentData()

        final_amount = self.raw_total

        is_duplicate = TransactionRepository.check_potential_duplicate(
            date, counterparty_name, final_amount, currency_code, exclude_id=self.edit_tx_id)
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
            if self.edit_tx_id:
                TransactionRepository.update_transaction(
                    self.edit_tx_id,
                    date=date,
                    counterparty_name=counterparty_name,
                    receipt_no=receipt_no,
                    payment_type_id=payment_type_id,
                    currency_code=currency_code,
                    items_data=items_data,
                    location_id=location_id
                )
                QMessageBox.information(self, "Success", "Transaction updated successfully!")
                self.transaction_saved.emit()
            else:
                TransactionRepository.save_transaction(
                    date=date,
                    counterparty_name=counterparty_name,
                    receipt_no=receipt_no,
                    payment_type_id=payment_type_id,
                    currency_code=currency_code,
                    items_data=items_data,
                    location_id=location_id
                )
                QMessageBox.information(self, "Success", "Transaction saved successfully!")
                self.transaction_saved.emit()
                self.reset_form()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save transaction:\n{str(e)}")

    def reset_form(self):
        self.receipt_number_input.clear()
        self.items_table.setRowCount(0)
        self.date_input.setDate(QDate.currentDate())

        self.load_reference_data()
        self.apply_smart_defaults()
        self.add_empty_row()
        self.calculate_totals()

        self.counterparty_input.setFocus()