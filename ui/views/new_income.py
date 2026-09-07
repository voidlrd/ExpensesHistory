from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox,
    QDateEdit, QPushButton, QDoubleSpinBox, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import QDate
from repositories.reference_repo import ReferenceRepository
from repositories.income_repo import IncomeRepository
from ui.widgets import repopulate_combo

class NewIncomeView(QWidget):
    def __init__(self):
        super().__init__()
        self.ref_repo = ReferenceRepository()
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
        self.counterparty_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.counterparty_input.setPlaceholderText("Type or select employer/person...")

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 9999999.99)
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
        self.save_btn = QPushButton("Save Income")
        self.save_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 5px 15px;")
        self.save_btn.clicked.connect(self.save_income)

        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def load_reference_data(self):
        repopulate_combo(
            self.currency_input,
            [(cur.code, cur.code) for cur in self.ref_repo.get_all_currencies()]
        )
        repopulate_combo(
            self.payment_type_input,
            [(pt.type, pt.id) for pt in self.ref_repo.get_all_payment_types()]
        )
        repopulate_combo(
            self.counterparty_input,
            [(cp.name, cp.id) for cp in self.ref_repo.get_all_counterparties()]
        )

    def apply_smart_defaults(self):
        last_pt, last_cur = IncomeRepository.get_last_used_defaults()
        if last_pt:
            idx = self.payment_type_input.findData(last_pt)
            if idx >= 0: self.payment_type_input.setCurrentIndex(idx)
        if last_cur:
            idx = self.currency_input.findData(last_cur)
            if idx >= 0: self.currency_input.setCurrentIndex(idx)

    def save_income(self):
        counterparty_name = self.counterparty_input.currentText().strip()
        if not counterparty_name:
            QMessageBox.warning(self, "Validation Error", "Please specify the income source.")
            return

        amount = self.amount_input.value()
        date = self.date_input.date().toPyDate()
        payment_type_id = self.payment_type_input.currentData()
        currency_code = self.currency_input.currentData()

        try:
            IncomeRepository.save_income(
                date=date,
                counterparty_name=counterparty_name,
                net_amount=amount,
                currency_code=currency_code,
                payment_type_id=payment_type_id
            )
            QMessageBox.information(self, "Success", "Income saved successfully!")
            self.reset_form()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save income:\n{str(e)}")

    def reset_form(self):
        self.amount_input.setValue(0.0)
        self.date_input.setDate(QDate.currentDate())

        self.load_reference_data()
        self.apply_smart_defaults()