import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from repositories.product_repo import ProductRepository
from ui.widgets import SortItem, format_amount, make_stat_card, repopulate_combo
from units import describe_package, normalize_unit, price_per_base, unit_price_after_discount
from datetime import datetime

class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        strs = []
        for v in values:
            try:
                strs.append(datetime.fromtimestamp(v).strftime("%b %d, %Y"))
            except (ValueError, OSError):
                strs.append("")
        return strs

class PriceTrackerView(QWidget):
    def __init__(self):
        super().__init__()
        self.product_repo = ProductRepository()
        self.setup_ui()
        self.load_products()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Price Tracker")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.product_search = QComboBox()
        self.product_search.setEditable(True)
        self.product_search.setPlaceholderText("Search for a product to see its price history...")
        self.product_search.setMinimumWidth(300)
        self.product_search.currentIndexChanged.connect(self.on_product_selected)

        self.currency_selector = QComboBox()
        self.currency_selector.currentIndexChanged.connect(self.on_currency_changed)

        header_layout.addWidget(title)
        header_layout.addSpacing(20)
        header_layout.addWidget(QLabel("Product:"))
        header_layout.addWidget(self.product_search)
        header_layout.addSpacing(10)
        header_layout.addWidget(QLabel("Currency:"))
        header_layout.addWidget(self.currency_selector)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        stats_layout = QHBoxLayout()
        self.lowest_price_label = self._stat_card(stats_layout, "Lowest Price", "#4CAF50")
        self.latest_price_label = self._stat_card(stats_layout, "Latest Price", "#2196F3")
        self.highest_price_label = self._stat_card(stats_layout, "Highest Price", "#F44336")
        layout.addLayout(stats_layout)

        self.plot_widget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.plot_widget.setBackground('transparent')
        self.plot_widget.setTitle("Price History Over Time", color="white")
        self.plot_widget.setLabel('left', 'Unit Price')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setMinimumHeight(250)
        self.plot_widget.setVisible(False)
        layout.addWidget(self.plot_widget)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Store (Counterparty)", "Amount Bought", "Price (after discount)", "Per kg / l"]
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

    @staticmethod
    def _stat_card(parent_layout, title_text, color):
        value, sub = make_stat_card(parent_layout, title_text, color, value_text="-",
                                    value_size=20, padding=10, radius=8, subtitle=True)
        return {"value": value, "sub": sub}

    def load_products(self):
        repopulate_combo(
            self.product_search,
            [(p.name, p.id) for p in self.product_repo.get_all_products()],
            placeholder=("", None),
            block_signals=True
        )
        self.load_currencies()
        self.refresh_history()

    def on_product_selected(self, index):
        self.load_currencies()
        self.refresh_history()

    def on_currency_changed(self, index):
        self.refresh_history()

    def load_currencies(self):
        product_id = self.product_search.currentData()
        codes = self.product_repo.get_product_currencies(product_id) if product_id else []
        repopulate_combo(
            self.currency_selector,
            [(code, code) for code in codes],
            block_signals=True
        )

    def refresh_history(self):
        product_id = self.product_search.currentData()
        if not product_id:
            self.table.setRowCount(0)
            self.plot_widget.clear()
            self.plot_widget.setVisible(False)
            self._reset_stats()
            return

        items = self.product_repo.get_product_price_history(
            product_id, self.currency_selector.currentData()
        )
        self.populate_table_and_stats(items)

    @staticmethod
    def _comparable_price(item, eff_price):
        product = item.product
        per_base = price_per_base(eff_price, product.unit_of_measure,
                                  product.package_size, product.package_unit)
        if per_base:
            return float(per_base[0]), per_base[1]
        return eff_price, normalize_unit(product.unit_of_measure)

    def populate_table_and_stats(self, items):
        self.table.setRowCount(0)
        self.plot_widget.clear()

        if not items:
            self.plot_widget.setVisible(False)
            self._reset_stats()
            return

        self.plot_widget.setVisible(True)

        # items arrive newest-first
        entries = []
        for item in items:
            eff_price = unit_price_after_discount(item.amount, item.price, item.discount)
            entries.append((item, eff_price) + self._comparable_price(item, eff_price))

        for row_idx, (item, eff_price, price, basis) in enumerate(entries):
            self.table.insertRow(row_idx)
            tx = item.transaction
            product = item.product
            unit = normalize_unit(product.unit_of_measure)
            store_name = tx.counterparty.name if tx.counterparty else "Unknown"

            self.table.setItem(row_idx, 0, QTableWidgetItem(tx.date.strftime("%Y-%m-%d")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(store_name))

            amount_text = f"{format_amount(item.amount)} {unit}"
            package = describe_package(product.package_size, product.package_unit)
            if package:
                amount_text += f" x {package}"
            self._set_right(row_idx, 2, amount_text)
            self._set_right(row_idx, 3, f"{eff_price:.2f} {tx.currency_code} / {unit}")
            per_base = f"{price:.2f} {tx.currency_code} / {basis}" if basis in ("kg", "l") else ""
            self._set_right(row_idx, 4, per_base)

        lowest = min(entries, key=lambda e: e[2])
        highest = max(entries, key=lambda e: e[2])
        latest = entries[0]

        self.plot_widget.setLabel('left', f"Price per {entries[0][3]}")
        timestamps = []
        prices = []
        for item, _, price, _ in reversed(entries):
            dt = item.transaction.date
            timestamps.append(datetime(dt.year, dt.month, dt.day).timestamp())
            prices.append(price)

        self.plot_widget.plot(
            timestamps, prices,
            pen=pg.mkPen(color='#2196F3', width=3),
            symbol='o', symbolSize=8, symbolBrush='#2196F3'
        )

        self._update_card(self.lowest_price_label, lowest)
        self._update_card(self.latest_price_label, latest)
        self._update_card(self.highest_price_label, highest)

    def _set_right(self, row, col, text):
        self.table.setItem(row, col, SortItem(text, align_right=True))

    def _update_card(self, card_dict, entry):
        item, _, price, basis = entry
        tx = item.transaction
        store_name = tx.counterparty.name if tx.counterparty else "Unknown"

        card_dict["value"].setText(f"{price:.2f} {tx.currency_code} / {basis}")
        card_dict["sub"].setText(f"{store_name}\n({tx.date.strftime('%b %Y')})")

    def _reset_stats(self):
        for card in [self.lowest_price_label, self.latest_price_label, self.highest_price_label]:
            card["value"].setText("-")
            card["sub"].setText("")