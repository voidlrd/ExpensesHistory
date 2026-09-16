from PyQt6.QtWidgets import QMainWindow, QTabWidget
from PyQt6.QtCore import QSettings
from ui.views.dashboard import DashboardView
from ui.views.new_transaction import NewTransactionView
from ui.views.new_income import NewIncomeView
from ui.views.transaction_list import TransactionListView
from ui.views.price_tracker import PriceTrackerView
from ui.views.data_manager import DataManagerView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Expense Tracker")
        self.resize(1024, 768)
        self.settings = QSettings("ExpensesHistory", "ExpenseTracker")

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = DashboardView()
        self.new_transaction_tab = NewTransactionView()
        self.new_income_tab = NewIncomeView()
        self.history_tab = TransactionListView()
        self.price_tracker_tab = PriceTrackerView()
        self.data_manager_tab = DataManagerView()

        # (widget, title, refresh callback run when the tab is opened)
        self.pages = [
            (self.dashboard_tab, "Dashboard", self.dashboard_tab.refresh),
            (self.new_transaction_tab, "New Transaction", self.new_transaction_tab.load_reference_data),
            (self.new_income_tab, "New Income", self.new_income_tab.refresh),
            (self.history_tab, "History", self._refresh_history),
            (self.price_tracker_tab, "Price Tracker", self.price_tracker_tab.load_products),
            (self.data_manager_tab, "Data Manager", self.data_manager_tab.load_data),
        ]

        for widget, title, _ in self.pages:
            self.tabs.addTab(widget, title)

        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.data_manager_tab.show_price_history.connect(self.open_price_history)
        self.data_manager_tab.database_restored.connect(self.refresh_all)

        self._restore_window_state()

    def _refresh_history(self):
        self.history_tab.load_reference_data()
        self.history_tab.load_data()

    def on_tab_changed(self, index):
        if 0 <= index < len(self.pages):
            self.pages[index][2]()

    def refresh_all(self):
        for _, _, refresh in self.pages:
            refresh()

    def open_price_history(self, product_id):
        self.price_tracker_tab.select_product(product_id)
        self.tabs.setCurrentWidget(self.price_tracker_tab)

    def _restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        index = self.settings.value("tab", 0, type=int)
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("tab", self.tabs.currentIndex())
        super().closeEvent(event)
