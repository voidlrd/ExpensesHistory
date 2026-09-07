import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from repositories.product_repo import ProductRepository
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
        self.lowest_price_label = self._create_stat_card(stats_layout, "Lowest Price", "#4CAF50")
        self.latest_price_label = self._create_stat_card(stats_layout, "Latest Price", "#2196F3")
        self.highest_price_label = self._create_stat_card(stats_layout, "Highest Price", "#F44336")
        layout.addLayout(stats_layout)

        self.plot_widget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.plot_widget.setBackground('transparent')
        self.plot_widget.setTitle("Price History Over Time", color="white")
        self.plot_widget.setLabel('left', 'Unit Price')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setMinimumHeight(250)
        self.plot_widget.setVisible(False)
        layout.addWidget(self.plot_widget)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Store (Counterparty)", "Amount Bought", "Unit Price (after discount)"]
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

    def _create_stat_card(self, parent_layout, title_text, color):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {color}; border-radius: 8px; padding: 10px;")
        flayout = QVBoxLayout(frame)

        title = QLabel(title_text)
        title.setStyleSheet("color: white; font-size: 14px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel("-")
        value_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("")
        subtitle.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        flayout.addWidget(title)
        flayout.addWidget(value_label)
        flayout.addWidget(subtitle)

        parent_layout.addWidget(frame)
        return {"value": value_label, "sub": subtitle}

    def load_products(self):
        current_product_id = self.product_search.currentData()

        self.product_search.blockSignals(True)
        self.product_search.clear()
        self.product_search.addItem("", userData=None)

        products = self.product_repo.get_all_products()
        for p in products:
            self.product_search.addItem(p.name, userData=p.id)

        if current_product_id:
            index = self.product_search.findData(current_product_id)
            if index >= 0:
                self.product_search.setCurrentIndex(index)

        self.product_search.blockSignals(False)
        self.load_currencies()
        self.refresh_history()

    def on_product_selected(self, index):
        self.load_currencies()
        self.refresh_history()

    def on_currency_changed(self, index):
        self.refresh_history()

    def load_currencies(self):
        product_id = self.product_search.currentData()
        previous = self.currency_selector.currentData()

        self.currency_selector.blockSignals(True)
        self.currency_selector.clear()
        if product_id:
            for code in self.product_repo.get_product_currencies(product_id):
                self.currency_selector.addItem(code, userData=code)
            if previous:
                idx = self.currency_selector.findData(previous)
                if idx >= 0:
                    self.currency_selector.setCurrentIndex(idx)
        self.currency_selector.blockSignals(False)

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
    def _effective_price(item):
        amount = float(item.amount)
        if amount <= 0:
            return float(item.price)
        return float((item.amount * item.price) - item.discount) / amount

    def populate_table_and_stats(self, items):
        self.table.setRowCount(0)
        self.plot_widget.clear()

        if not items:
            self.plot_widget.setVisible(False)
            self._reset_stats()
            return

        self.plot_widget.setVisible(True)

        # items arrive newest-first
        entries = [(item, self._effective_price(item)) for item in items]

        for row_idx, (item, eff_price) in enumerate(entries):
            self.table.insertRow(row_idx)
            tx = item.transaction
            store_name = tx.counterparty.name if tx.counterparty else "Unknown"

            self.table.setItem(row_idx, 0, QTableWidgetItem(tx.date.strftime("%Y-%m-%d")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(store_name))

            amount_val = float(item.amount)
            if amount_val.is_integer():
                amount_str = str(int(amount_val))
            else:
                amount_str = f"{amount_val:.3f}".rstrip('0').rstrip('.')

            unit = item.product.unit_of_measure or ""
            amount_item = QTableWidgetItem(f"{amount_str} {unit}".strip())
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 2, amount_item)

            price_item = QTableWidgetItem(f"{eff_price:.2f} {tx.currency_code}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 3, price_item)

        lowest = min(entries, key=lambda e: e[1])
        highest = max(entries, key=lambda e: e[1])
        latest = entries[0]

        timestamps = []
        prices = []
        for item, eff_price in reversed(entries):
            dt = item.transaction.date
            timestamps.append(datetime(dt.year, dt.month, dt.day).timestamp())
            prices.append(eff_price)

        self.plot_widget.plot(
            timestamps, prices,
            pen=pg.mkPen(color='#2196F3', width=3),
            symbol='o', symbolSize=8, symbolBrush='#2196F3'
        )

        self._update_card(self.lowest_price_label, *lowest)
        self._update_card(self.latest_price_label, *latest)
        self._update_card(self.highest_price_label, *highest)

    def _update_card(self, card_dict, item, eff_price):
        tx = item.transaction
        store_name = tx.counterparty.name if tx.counterparty else "Unknown"
        date_str = tx.date.strftime("%b %Y")

        card_dict["value"].setText(f"{eff_price:.2f} {tx.currency_code}")
        card_dict["sub"].setText(f"{store_name}\n({date_str})")

    def _reset_stats(self):
        for card in [self.lowest_price_label, self.latest_price_label, self.highest_price_label]:
            card["value"].setText("-")
            card["sub"].setText("")