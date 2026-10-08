import calendar
from datetime import date
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from repositories.reports_repo import ReportsRepository, month_bounds, shift_month
from repositories.reference_repo import ReferenceRepository
from ui.views.record_dialogs import LinesDialog
from ui.widgets import SortItem, make_stat_card, repopulate_combo

INCOME_COLOR = "#4CAF50"
EXPENSE_COLOR = "#F44336"
SECTION_STYLE = "font-size: 16px; font-weight: bold; margin-top: 10px; margin-bottom: 5px;"

SPANS = {"Month": 1, "3 months": 3, "6 months": 6, "Year": 12}

def _month_label(year, month):
    return f"{calendar.month_abbr[month]} {year}"

def period_label(first, last):
    return _month_label(*first) if first == last else f"{_month_label(*first)} – {_month_label(*last)}"

def period_months(span, year, month, today):
    """First and last (year, month) shown; the current year runs up to this month."""
    if span == "Year":
        return (year, 1), (year, today.month if year == today.year else 12)
    return shift_month(year, month, 1 - SPANS[span]), (year, month)

def period_dates(first, last):
    return month_bounds(*first)[0], month_bounds(*last)[1]

def change_text(current, previous, previous_label):
    if not previous:
        return f"nothing in {previous_label}" if current else ""
    change = (current - previous) / previous * 100
    arrow = "▲" if change >= 0 else "▼"
    return f"{arrow} {abs(change):.0f}% vs {previous_label}"

class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.reports_repo = ReportsRepository()
        self.ref_repo = ReferenceRepository()
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        self.title_label = QLabel("Dashboard")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")

        self.span_combo = QComboBox()
        self.span_combo.addItems(SPANS)
        self.span_combo.setToolTip("Several months end at the chosen month")

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip("Previous period")
        self.prev_btn.setFixedWidth(32)
        self.prev_btn.clicked.connect(lambda: self.step_period(-1))
        self.next_btn = QPushButton("▶")
        self.next_btn.setToolTip("Next period")
        self.next_btn.setFixedWidth(32)
        self.next_btn.clicked.connect(lambda: self.step_period(1))

        self.month_combo = QComboBox()
        for m in range(1, 13):
            self.month_combo.addItem(calendar.month_name[m], userData=m)
        self.month_combo.setCurrentIndex(date.today().month - 1)
        self.year_combo = QComboBox()

        self.currency_selector = QComboBox()
        self.currency_selector.setStyleSheet("font-size: 16px; padding: 5px;")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Show:"))
        header_layout.addWidget(self.span_combo)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.prev_btn)
        header_layout.addWidget(self.month_combo)
        header_layout.addWidget(self.year_combo)
        header_layout.addWidget(self.next_btn)
        header_layout.addSpacing(15)
        header_layout.addWidget(QLabel("Currency:"))
        header_layout.addWidget(self.currency_selector)
        layout.addLayout(header_layout)

        cards_layout = QHBoxLayout()
        self.income_label, self.income_change = make_stat_card(cards_layout, "Income", INCOME_COLOR, subtitle=True)
        self.expense_label, self.expense_change = make_stat_card(cards_layout, "Expenses", EXPENSE_COLOR, subtitle=True)
        self.balance_label, self.balance_change = make_stat_card(cards_layout, "Net Balance", "#2196F3", subtitle=True)
        layout.addLayout(cards_layout)

        trend_title = QLabel("Last 12 Months")
        trend_title.setStyleSheet(SECTION_STYLE)
        layout.addWidget(trend_title)
        self.trend_plot = pg.PlotWidget()
        self.trend_plot.setBackground("transparent")
        self.trend_plot.setMinimumHeight(170)
        self.trend_plot.setMaximumHeight(220)
        self.trend_plot.showGrid(y=True, alpha=0.2)
        self.trend_plot.setMouseEnabled(x=False, y=False)
        self.trend_plot.hideButtons()
        self.trend_legend = self.trend_plot.addLegend(offset=(10, 5))
        layout.addWidget(self.trend_plot)

        tables_title_layout = QHBoxLayout()
        for text in ("Top Expenses by Store", "Expenses by Category"):
            label = QLabel(text)
            label.setStyleSheet(SECTION_STYLE)
            tables_title_layout.addWidget(label)
        layout.addLayout(tables_title_layout)

        tables_layout = QHBoxLayout()
        self.breakdown_table = self._make_breakdown_table("Store / Counterparty")
        self.cat_breakdown_table = self._make_breakdown_table("Category")
        tables_layout.addWidget(self.breakdown_table)
        tables_layout.addWidget(self.cat_breakdown_table)
        layout.addLayout(tables_layout)

        hint = QLabel("Double-click a store or category to see what you bought.")
        hint.setStyleSheet("color: #9E9E9E;")
        layout.addWidget(hint)

        self.span_combo.currentIndexChanged.connect(self.on_span_changed)
        self.month_combo.currentIndexChanged.connect(self.load_data)
        self.year_combo.currentIndexChanged.connect(self.load_data)
        self.currency_selector.currentIndexChanged.connect(self.load_data)

    def _make_breakdown_table(self, first_header):
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels([first_header, "Total Spent", "Share"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(True)
        table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        table.itemDoubleClicked.connect(lambda item, t=table: self.open_lines(t, item.row()))
        return table

    # ---------- period ----------

    def refresh(self):
        """Reload years and currencies (they change as data is added), then the numbers."""
        self._set_years(self.year_combo.currentData() or date.today().year)
        repopulate_combo(
            self.currency_selector,
            [(cur.code, cur.code) for cur in self.ref_repo.get_all_currencies()],
            block_signals=True
        )
        self.load_data()

    def load_currencies(self):
        self.refresh()

    def _set_years(self, selected_year):
        years = sorted(set(self.reports_repo.get_available_years()) | {selected_year})
        repopulate_combo(self.year_combo, [(str(y), y) for y in years], block_signals=True)
        self.year_combo.blockSignals(True)
        self.year_combo.setCurrentIndex(self.year_combo.findData(selected_year))
        self.year_combo.blockSignals(False)

    def on_span_changed(self):
        self.month_combo.setVisible(self.span_combo.currentText() != "Year")
        self.load_data()

    def current_period(self):
        return period_months(self.span_combo.currentText(), self.year_combo.currentData(),
                             self.month_combo.currentData(), date.today())

    def step_period(self, direction):
        delta = direction * SPANS[self.span_combo.currentText()]
        year, month = shift_month(self.year_combo.currentData(), self.month_combo.currentData(), delta)
        self._set_years(year)
        self.month_combo.blockSignals(True)
        self.month_combo.setCurrentIndex(month - 1)
        self.month_combo.blockSignals(False)
        self.load_data()

    # ---------- numbers ----------

    def load_data(self):
        currency = self.currency_selector.currentData()
        year = self.year_combo.currentData()
        month = self.month_combo.currentData()

        if not currency or not year or not month:
            return

        first, last = self.current_period()
        start, end = period_dates(first, last)
        step = SPANS[self.span_combo.currentText()]
        prev_first, prev_last = shift_month(*first, -step), shift_month(*last, -step)
        self.title_label.setText(f"Dashboard - {period_label(first, last)}")

        income, expenses = self.reports_repo.get_summary(currency, start, end)
        prev_income, prev_expenses = self.reports_repo.get_summary(currency, *period_dates(prev_first, prev_last))
        prev_label = period_label(prev_first, prev_last)

        self.income_label.setText(f"{income:,.2f} {currency}")
        self.expense_label.setText(f"{expenses:,.2f} {currency}")
        self.balance_label.setText(f"{income - expenses:,.2f} {currency}")
        self.income_change.setText(change_text(income, prev_income, prev_label))
        self.expense_change.setText(change_text(expenses, prev_expenses, prev_label))
        self.balance_change.setText(f"{prev_label}: {prev_income - prev_expenses:,.2f}")

        self._draw_trend(self.reports_repo.get_monthly_totals(currency, *last), first, last)

        stores = self.reports_repo.get_store_breakdown(currency, start, end)
        self._fill_breakdown(self.breakdown_table, [(("store", i), name, total) for i, name, total in stores],
                             expenses, currency)
        categories = self.reports_repo.get_category_breakdown(currency, start, end)
        self._fill_breakdown(self.cat_breakdown_table, [(("category", i), name, total) for i, name, total in categories],
                             expenses, currency)

    def _draw_trend(self, months, first, last):
        self.trend_plot.clear()
        self.trend_legend.clear()
        xs = list(range(len(months)))

        def brushes(color):
            faded = QColor(color)
            faded.setAlpha(70)
            return [pg.mkBrush(color if first <= (m[0], m[1]) <= last else faded) for m in months]

        income_bars = pg.BarGraphItem(x=[x - 0.2 for x in xs], height=[m[2] for m in months], width=0.4,
                                      brush=INCOME_COLOR, brushes=brushes(INCOME_COLOR), pen=None)
        expense_bars = pg.BarGraphItem(x=[x + 0.2 for x in xs], height=[m[3] for m in months], width=0.4,
                                       brush=EXPENSE_COLOR, brushes=brushes(EXPENSE_COLOR), pen=None)
        self.trend_plot.addItem(income_bars)
        self.trend_plot.addItem(expense_bars)
        self.trend_legend.addItem(income_bars, "Income")
        self.trend_legend.addItem(expense_bars, "Expenses")
        self.trend_plot.getAxis("bottom").setTicks(
            [[(x, f"{calendar.month_abbr[m[1]]} {str(m[0])[2:]}") for x, m in zip(xs, months)]]
        )
        self.trend_plot.setXRange(-0.6, len(months) - 0.4, padding=0)
        self.trend_months = months

    def _fill_breakdown(self, table, rows, period_total, currency):
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for row, (key, label, total) in enumerate(rows):
            table.insertRow(row)
            name_item = QTableWidgetItem(label)
            name_item.setData(Qt.ItemDataRole.UserRole, key)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, SortItem(f"{total:,.2f} {currency}", total, align_right=True))
            share = total / period_total * 100 if period_total else 0
            table.setItem(row, 2, SortItem(f"{share:.0f}%", share, align_right=True))
        table.setSortingEnabled(True)

    # ---------- drill-down ----------

    def lines_dialog(self, table, row):
        name_item = table.item(row, 0)
        if name_item is None:
            return None
        kind, key = name_item.data(Qt.ItemDataRole.UserRole)
        currency = self.currency_selector.currentData()
        first, last = self.current_period()
        start, end = period_dates(first, last)

        if kind == "store":
            filters = {"store_id": key}
        else:
            filters = {"category_id": key, "uncategorized": key is None}

        dialog = LinesDialog(
            f"{name_item.text()} - {period_label(first, last)}",
            currency,
            lambda: self.reports_repo.get_lines(currency, start, end, **filters),
            self
        )
        dialog.receipts_changed.connect(self.load_data)
        return dialog

    def open_lines(self, table, row):
        dialog = self.lines_dialog(table, row)
        if dialog is not None:
            dialog.exec()
