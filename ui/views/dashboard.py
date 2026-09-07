from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from repositories.reports_repo import ReportsRepository
from repositories.reference_repo import ReferenceRepository
from datetime import date
import calendar

class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.reports_repo = ReportsRepository()
        self.ref_repo = ReferenceRepository()
        self.setup_ui()
        self.load_currencies()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        self.title_label = QLabel(f"Dashboard")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")

        self.month_combo = QComboBox()
        for m in range(1, 13):
            self.month_combo.addItem(calendar.month_name[m], userData=m)
        self.month_combo.setCurrentIndex(date.today().month - 1)
        self.month_combo.currentIndexChanged.connect(self.load_data)

        self.year_combo = QComboBox()
        curr_year = date.today().year
        years = self.reports_repo.get_available_years()
        for y in years:
            self.year_combo.addItem(str(y), userData=y)
        self.year_combo.setCurrentText(str(curr_year))
        self.year_combo.currentIndexChanged.connect(self.load_data)

        self.currency_selector = QComboBox()
        self.currency_selector.setStyleSheet("font-size: 16px; padding: 5px;")
        self.currency_selector.currentIndexChanged.connect(self.load_data)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Month:"))
        header_layout.addWidget(self.month_combo)
        header_layout.addWidget(QLabel("Year:"))
        header_layout.addWidget(self.year_combo)
        header_layout.addSpacing(15)
        header_layout.addWidget(QLabel("Currency:"))
        header_layout.addWidget(self.currency_selector)
        layout.addLayout(header_layout)

        cards_layout = QHBoxLayout()
        self.income_label = self._create_card(cards_layout, "Income", "#4CAF50")
        self.expense_label = self._create_card(cards_layout, "Expenses", "#F44336")
        self.balance_label = self._create_card(cards_layout, "Net Balance", "#2196F3")
        layout.addLayout(cards_layout)

        tables_title_layout = QHBoxLayout()
        t1 = QLabel("Top Expenses by Store")
        t2 = QLabel("Expenses by Category")
        t1.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
        t2.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
        tables_title_layout.addWidget(t1)
        tables_title_layout.addWidget(t2)
        layout.addLayout(tables_title_layout)

        tables_layout = QHBoxLayout()

        self.breakdown_table = QTableWidget(0, 2)
        self.breakdown_table.setHorizontalHeaderLabels(["Store / Counterparty", "Total Spent"])
        self.breakdown_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.breakdown_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.cat_breakdown_table = QTableWidget(0, 2)
        self.cat_breakdown_table.setHorizontalHeaderLabels(["Category", "Total Spent"])
        self.cat_breakdown_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cat_breakdown_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        tables_layout.addWidget(self.breakdown_table)
        tables_layout.addWidget(self.cat_breakdown_table)
        layout.addLayout(tables_layout)

    def _create_card(self, parent_layout, title_text, color):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {color}; border-radius: 10px; padding: 20px;")
        flayout = QVBoxLayout(frame)

        title = QLabel(title_text)
        title.setStyleSheet("color: white; font-size: 16px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        amount = QLabel("0.00")
        amount.setStyleSheet("color: white; font-size: 28px; font-weight: bold;")
        amount.setAlignment(Qt.AlignmentFlag.AlignCenter)

        flayout.addWidget(title)
        flayout.addWidget(amount)

        parent_layout.addWidget(frame)
        return amount

    def load_currencies(self):
        self.currency_selector.blockSignals(True)
        self.currency_selector.clear()

        for cur in self.ref_repo.get_all_currencies():
            self.currency_selector.addItem(cur.code, userData=cur.code)

        self.currency_selector.blockSignals(False)
        self.load_data()

    def load_data(self):
        currency = self.currency_selector.currentData()
        year = self.year_combo.currentData()
        month = self.month_combo.currentData()

        if not currency or not year or not month:
            return

        self.title_label.setText(f"Dashboard - {calendar.month_name[month]} {year}")

        income, expenses = self.reports_repo.get_month_summary(currency, year, month)
        balance = income - expenses

        self.income_label.setText(f"{income:,.2f} {currency}")
        self.expense_label.setText(f"{expenses:,.2f} {currency}")
        self.balance_label.setText(f"{balance:,.2f} {currency}")

        store_data = self.reports_repo.get_expenses_by_counterparty(currency, year, month)
        self.breakdown_table.setRowCount(0)
        for row_idx, (store_name, total_spent) in enumerate(store_data):
            self.breakdown_table.insertRow(row_idx)
            self.breakdown_table.setItem(row_idx, 0, QTableWidgetItem(store_name))

            amount_item = QTableWidgetItem(f"{total_spent:,.2f} {currency}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.breakdown_table.setItem(row_idx, 1, amount_item)

        cat_data = self.reports_repo.get_expenses_by_category(currency, year, month)
        self.cat_breakdown_table.setRowCount(0)
        for row_idx, (cat_name, total_spent) in enumerate(cat_data):
            self.cat_breakdown_table.insertRow(row_idx)
            self.cat_breakdown_table.setItem(row_idx, 0, QTableWidgetItem(cat_name))
            amount_item = QTableWidgetItem(f"{total_spent:,.2f} {currency}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.cat_breakdown_table.setItem(row_idx, 1, amount_item)