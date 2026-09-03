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

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.new_transaction_tab, "New Transaction")
        self.tabs.addTab(self.new_income_tab, "New Income")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.price_tracker_tab, "Price Tracker")
        self.tabs.addTab(self.data_manager_tab, "Data Manager")

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if index == 0:
            self.dashboard_tab.load_currencies()
        if index == 1:
            self.new_transaction_tab.load_reference_data()
        if index == 2:
            self.new_income_tab.load_reference_data()
        if index == 3:
            self.history_tab.load_reference_data()
            self.history_tab.load_data()
        if index == 4:
            self.price_tracker_tab.load_products()
        if index == 5:
            self.data_manager_tab.load_data()