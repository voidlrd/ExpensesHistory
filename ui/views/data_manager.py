import os
import sqlite3
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QTabWidget, QMessageBox, QGroupBox, QLabel, QInputDialog
)
from PyQt6.QtCore import Qt
from sqlalchemy.exc import IntegrityError
from repositories.reference_repo import ReferenceRepository
from repositories.product_repo import ProductRepository
from datetime import datetime

class DataManagerView(QWidget):
    def __init__(self):
        super().__init__()
        self.ref_repo = ReferenceRepository()
        self.product_repo = ProductRepository()
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.cp_tab = QWidget()
        cp_layout = QHBoxLayout(self.cp_tab)
        self.cp_list = QListWidget()
        self.cp_list.currentItemChanged.connect(self.on_cp_selected)
        cp_layout.addWidget(self.cp_list, 1)

        cp_right_panel = QVBoxLayout()

        cp_form_group = QGroupBox("Edit Store/Person")
        cp_form_layout = QFormLayout(cp_form_group)

        self.cp_name_input = QLineEdit()
        self.cp_cat_input = QComboBox()

        cp_btn_layout = QHBoxLayout()
        self.cp_hide_btn = QPushButton("Hide/Archive")
        self.cp_hide_btn.clicked.connect(self.toggle_hide_cp)

        self.cp_save_btn = QPushButton("Save Changes")
        self.cp_save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.cp_save_btn.clicked.connect(self.save_cp_changes)

        cp_btn_layout.addWidget(self.cp_hide_btn)
        cp_btn_layout.addWidget(self.cp_save_btn)

        cp_form_layout.addRow("Name:", self.cp_name_input)
        cp_form_layout.addRow("Category:", self.cp_cat_input)
        cp_form_layout.addRow("", cp_btn_layout)
        cp_right_panel.addWidget(cp_form_group)

        self.loc_group = QGroupBox("Manage Locations")
        loc_layout = QVBoxLayout(self.loc_group)
        self.loc_list = QListWidget()

        loc_btn_layout = QHBoxLayout()
        self.loc_add_btn = QPushButton("Add Location")
        self.loc_add_btn.clicked.connect(self.add_location)
        self.loc_del_btn = QPushButton("Remove Selected")
        self.loc_del_btn.clicked.connect(self.remove_location)

        loc_btn_layout.addWidget(self.loc_add_btn)
        loc_btn_layout.addWidget(self.loc_del_btn)
        cp_right_panel.addWidget(self.loc_group)
        self.loc_group.setEnabled(False)

        cp_layout.addLayout(cp_right_panel, 1)
        self.tabs.addTab(self.cp_tab, "Stores & People")

        self.prod_tab = QWidget()
        prod_layout = QHBoxLayout(self.prod_tab)
        self.prod_list = QListWidget()
        self.prod_list.currentItemChanged.connect(self.on_prod_selected)
        prod_layout.addWidget(self.prod_list, 1)

        prod_form_group = QGroupBox("Edit Product")
        prod_form_layout = QFormLayout(prod_form_group)
        self.prod_name_input = QLineEdit()
        self.prod_brand_input = QLineEdit()
        self.prod_unit_input = QLineEdit()
        self.prod_unit_input.setPlaceholderText("e.g., kg, liters, pieces")

        self.prod_cat_input = QComboBox()
        self.prod_cat_input.setEditable(True)
        self.prod_cat_input.setPlaceholderText("Select or type new category...")

        prod_btn_layout = QHBoxLayout()
        self.prod_save_btn = QPushButton("Save Changes")
        self.prod_save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.prod_save_btn.clicked.connect(self.save_prod_changes)

        self.prod_hide_btn = QPushButton("Hide/Archive")
        self.prod_hide_btn.clicked.connect(self.toggle_hide_prod)

        prod_btn_layout.addWidget(self.prod_hide_btn)
        prod_btn_layout.addWidget(self.prod_save_btn)

        prod_form_layout.addRow("Name:", self.prod_name_input)
        prod_form_layout.addRow("Brand:", self.prod_brand_input)
        prod_form_layout.addRow("Category:", self.prod_cat_input)
        prod_form_layout.addRow("Unit of Measure:", self.prod_unit_input)
        prod_form_layout.addRow("", self.prod_save_btn)

        prod_layout.addWidget(prod_form_group, 1)
        self.tabs.addTab(self.prod_tab, "Products")

        self.backup_tab = QWidget()
        backup_layout = QVBoxLayout(self.backup_tab)
        self.backup_btn = QPushButton("Create Database Backup")
        self.backup_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-size: 14px; max-width: 250px;")
        self.backup_btn.clicked.connect(self.create_backup)

        backup_msg = QLabel(
            "<h3>Protect your data</h3>"
            "Click the button below to instantly create a safe copy of your SQLite database."
            "It will be saved in a new 'backups' folder inside your project directory."
        )
        backup_msg.setWordWrap(True)
        backup_layout.addWidget(backup_msg)
        backup_layout.addSpacing(10)
        backup_layout.addWidget(self.backup_btn)
        backup_layout.addStretch()

        self.tabs.addTab(self.backup_tab, "Backups")

        main_layout.addWidget(self.tabs)

    def create_backup(self):
        try:
            os.makedirs("backups", exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = os.path.join("backups", f"expense_tracker_{timestamp}.db")

            with sqlite3.connect("expense_tracker.db") as src, sqlite3.connect(backup_path) as dst:
                src.backup(dst)

            QMessageBox.information(self, "Success", f"Backup created successfully!\n\nLocation: {backup_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup:\n{str(e)}")

    def load_data(self):
        self.cp_cat_input.clear()
        for cat in self.ref_repo.get_all_counterparty_categories():
            self.cp_cat_input.addItem(cat.name, userData=cat.id)

        self.cp_list.clear()
        for cp in self.ref_repo.get_all_counterparties(include_hidden=True):
            display_name = f"🚫 {cp.name}" if cp.hidden else cp.name
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, cp)
            self.cp_list.addItem(item)

        self.prod_cat_input.clear()
        self.prod_cat_input.addItem("", userData=None)
        for item_cat in self.ref_repo.get_all_item_categories():
            self.prod_cat_input.addItem(item_cat.name, userData=item_cat.id)

        self.prod_list.clear()
        for p in self.product_repo.get_all_products(include_hidden=True):
            display_name = f"🚫 {p.name}" if p.hidden else p.name
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.prod_list.addItem(item)

    def on_cp_selected(self, current, previous):
        if not current:
            self.loc_group.setEnabled(False)
            return
        
        cp = current.data(Qt.ItemDataRole.UserRole)
        self.cp_name_input.setText(cp.name)
        self.cp_hide_btn.setText("Unhide" if cp.hidden else "Hide/Archive")

        idx = self.cp_cat_input.findData(cp.category_id)
        if idx >= 0:
            self.cp_cat_input.setCurrentIndex(idx)

        self.load_locations(cp)

    def save_cp_changes(self):
        item = self.cp_list.currentItem()
        if not item: return

        cp = item.data(Qt.ItemDataRole.UserRole)
        new_name = self.cp_name_input.text().strip()
        cat_id = self.cp_cat_input.currentData()

        if not new_name:
            QMessageBox.warning(self, "Error", "Name cannot be empty.")
            return

        self.ref_repo.update_counterparty(cp.id, new_name, cat_id)
        QMessageBox.information(self, "Success", "Store updated successfully.")
        self.load_data()

    def toggle_hide_cp(self):
        item = self.cp_list.currentItem()
        if not item: return

        current_row = self.cp_list.currentRow()

        cp = item.data(Qt.ItemDataRole.UserRole)
        self.ref_repo.set_hidden_status(cp.id, not cp.hidden)
        self.load_data()

        self.cp_list.setCurrentRow(current_row)

    def load_locations(self, cp):
        self.loc_group.setEnabled(True)
        self.loc_list.clear()
        locations = self.ref_repo.get_locations_for_counterparty(cp.name)
        for loc in locations:
            item = QListWidgetItem(loc.label)
            item.setData(Qt.ItemDataRole.UserRole, loc.id)
            self.loc_list.addItem(item)

    def add_location(self):
        item = self.cp_list.currentItem()
        if not item: return
        cp = item.data(Qt.ItemDataRole.UserRole)

        text, ok = QInputDialog.getText(self, "New Location", "Enter location label/branch name:")
        if ok and text.strip():
            try:
                self.ref_repo.add_location(cp.id, text.strip())
                self.load_locations(cp)
            except IntegrityError:
                QMessageBox.warning(self, "Error", "This location already exists for this store.")
            except Exception as e:
                QMessageBox.warning(self, "Error", "This location already exists or is invalid.")

    def remove_location(self):
        loc_item = self.loc_list.currentItem()
        if not loc_item: return
        loc_id = loc_item.data(Qt.ItemDataRole.UserRole)
        self.ref_repo.remove_location(loc_id)

        cp = self.cp_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self.load_locations(cp)

    def on_prod_selected(self, current, previous):
        if not current: return
        p = current.data(Qt.ItemDataRole.UserRole)
        self.prod_name_input.setText(p.name)
        self.prod_brand_input.setText(p.brand or "")
        self.prod_unit_input.setText(p.unit_of_measure or "")
        self.prod_hide_btn.setText("Unhide" if p.hidden else "Hide/Archive")

        if p.category_id:
            idx = self.prod_cat_input.findData(p.category_id)
            if idx >= 0:
                self.prod_cat_input.setCurrentIndex(idx)
        else:
            self.prod_cat_input.setCurrentIndex(0)

    def save_prod_changes(self):
        item = self.prod_list.currentItem()
        if not item: return

        p = item.data(Qt.ItemDataRole.UserRole)
        new_name = self.prod_name_input.text().strip()
        brand = self.prod_brand_input.text().strip()
        unit = self.prod_unit_input.text().strip()
        cat_name = self.prod_cat_input.currentText().strip()

        if not new_name:
            QMessageBox.warning(self, "Error", "Product name cannot be empty.")
            return

        self.product_repo.update_product(p.id, new_name, brand, unit, cat_name)
        QMessageBox.information(self, "Success", "Product updated successfully.")
        self.load_data()

    def toggle_hide_prod(self):
        item = self.prod_list.currentItem()
        if not item: return

        current_row = self.prod_list.currentRow()

        p = item.data(Qt.ItemDataRole.UserRole)
        self.product_repo.set_hidden_status(p.id, not p.hidden)
        self.load_data()

        self.prod_list.setCurrentRow(current_row)