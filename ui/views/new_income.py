from decimal import Decimal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QGroupBox,
    QDateEdit, QPushButton, QDoubleSpinBox, QMessageBox, QHBoxLayout,
    QLabel, QTableWidget, QHeaderView, QCompleter
)
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import QDate, Qt, QTimer
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository
from ui.widgets import SortItem, ask_yes_no, number_item, repopulate_combo, show_status

RECENT_COLUMNS = ["Date", "Source", "Net Amount", "Currency"]

class NewIncomeView(QWidget):
    def __init__(self):
        super().__init__()
        self.ref_repo = ReferenceRepository()

        self._dup_timer = QTimer(self)
        self._dup_timer.setSingleShot(True)
        self._dup_timer.setInterval(250)
        self._dup_timer.timeout.connect(self._run_duplicate_check)

        self.setup_ui()
        self.refresh()
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
        self.counterparty_input.setPlaceholderText("Type or select employer/person...")
        completer = QCompleter(self.counterparty_input.model())
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.counterparty_input.setCompleter(completer)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.00, 9999999.99)
        self.amount_input.setDecimals(2)

        self.currency_input = QComboBox()
        self.payment_type_input = QComboBox()

        form_layout.addRow("Date:", self.date_input)
        form_layout.addRow("Source (Counterparty):", self.counterparty_input)
        form_layout.addRow("Net Amount:", self.amount_input)
        form_layout.addRow("Currency:", self.currency_input)
        form_layout.addRow("Payment Type:", self.payment_type_input)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.duplicate_warning_label = QLabel()
        self.duplicate_warning_label.setStyleSheet("color: #F44336; font-weight: bold;")
        self.duplicate_warning_label.setVisible(False)

        self.save_btn = QPushButton("Save Income (Ctrl+S)")
        self.save_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 5px 15px;")
        self.save_btn.clicked.connect(self.save_income)

        btn_layout.addWidget(self.duplicate_warning_label)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        recent_group = QGroupBox("Recent Income")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_table = QTableWidget(0, len(RECENT_COLUMNS))
        self.recent_table.setHorizontalHeaderLabels(RECENT_COLUMNS)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.recent_table.verticalHeader().setVisible(False)
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.recent_table.setMaximumHeight(180)
        recent_layout.addWidget(self.recent_table)
        layout.addWidget(recent_group)

        layout.addStretch()

        self.date_input.dateChanged.connect(self._dup_timer.start)
        self.amount_input.valueChanged.connect(self._dup_timer.start)
        self.currency_input.currentIndexChanged.connect(self._dup_timer.start)
        self.counterparty_input.currentTextChanged.connect(self._dup_timer.start)

        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save_income)

    def refresh(self):
        self.load_reference_data()
        self.load_recent()

    def load_reference_data(self):
        repopulate_combo(
            self.currency_input,
            [(cur.code, cur.code) for cur in self.ref_repo.get_all_currencies()]
        )
        repopulate_combo(
            self.payment_type_input,
            [(pt.type, pt.id) for pt in self.ref_repo.get_all_payment_types()]
        )

        # only employers, people and anyone who already paid you: not every shop
        text = self.counterparty_input.currentText()
        repopulate_combo(
            self.counterparty_input,
            [(cp.name, cp.id) for cp in self.ref_repo.get_income_sources()],
            block_signals=True
        )
        self.counterparty_input.setCurrentText(text)

    def load_recent(self):
        incomes = IncomeRepository.get_recent_incomes()
        self.recent_table.setRowCount(0)
        for row, inc in enumerate(incomes):
            self.recent_table.insertRow(row)
            self.recent_table.setItem(row, 0, SortItem(str(inc.date)))
            self.recent_table.setItem(row, 1, SortItem(inc.counterparty.name if inc.counterparty else "Unknown"))
            self.recent_table.setItem(row, 2, number_item(inc.net_amount))
            self.recent_table.setItem(row, 3, SortItem(inc.currency_code))

    def apply_smart_defaults(self):
        last_pt, last_cur = IncomeRepository.get_last_used_defaults()
        if last_pt:
            idx = self.payment_type_input.findData(last_pt)
            if idx >= 0: self.payment_type_input.setCurrentIndex(idx)
        if last_cur:
            idx = self.currency_input.findData(last_cur)
            if idx >= 0: self.currency_input.setCurrentIndex(idx)

    def _run_duplicate_check(self):
        name = self.counterparty_input.currentText().strip()
        amount = self.amount_input.value()
        if not name or amount <= 0:
            self.duplicate_warning_label.setVisible(False)
            return

        is_duplicate = IncomeRepository.check_potential_duplicate(
            self.date_input.date().toPyDate(), name, amount, self.currency_input.currentData()
        )
        self.duplicate_warning_label.setText("⚠️ Already recorded on this date")
        self.duplicate_warning_label.setVisible(is_duplicate)

    def save_income(self):
        self.amount_input.interpretText()

        counterparty_name = self.counterparty_input.currentText().strip()
        if not counterparty_name:
            QMessageBox.warning(self, "Validation Error", "Please specify the income source.")
            self.counterparty_input.setFocus()
            return

        amount = self.amount_input.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation Error", "Enter how much was received.")
            self.amount_input.setFocus()
            return

        date = self.date_input.date().toPyDate()
        currency_code = self.currency_input.currentData()

        if IncomeRepository.check_potential_duplicate(date, counterparty_name, amount, currency_code):
            if not ask_yes_no(
                self, "Potential Duplicate",
                f"Income from '{counterparty_name}' for {amount:.2f} on {date} is already recorded.\n\n"
                "Save this one as well?"
            ):
                return

        try:
            IncomeRepository.save_income(
                date=date,
                counterparty_name=counterparty_name,
                net_amount=amount,
                currency_code=currency_code,
                payment_type_id=self.payment_type_input.currentData()
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save income:\n{str(e)}")
            return

        show_status(self.status_label, f"✓ Saved {amount:,.2f} {currency_code} from {counterparty_name}")
        self.reset_form()

    def reset_form(self):
        self.amount_input.setValue(0.0)
        self.date_input.setDate(QDate.currentDate())
        self.duplicate_warning_label.setVisible(False)

        self.refresh()
        self.apply_smart_defaults()
