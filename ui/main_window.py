from PyQt6.QtWidgets import QMainWindow, QTabWidget
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
            (self.dashboard_tab, "Dashboard", self.dashboard_tab.load_currencies),
            (self.new_transaction_tab, "New Transaction", self.new_transaction_tab.load_reference_data),
            (self.new_income_tab, "New Income", self.new_income_tab.load_reference_data),
            (self.history_tab, "History", self._refresh_history),
            (self.price_tracker_tab, "Price Tracker", self.price_tracker_tab.load_products),
            (self.data_manager_tab, "Data Manager", self.data_manager_tab.load_data),
        ]

        for widget, title, _ in self.pages:
            self.tabs.addTab(widget, title)

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def _refresh_history(self):
        self.history_tab.load_reference_data()
        self.history_tab.load_data()

    def on_tab_changed(self, index):
        if 0 <= index < len(self.pages):
            self.pages[index][2]()
