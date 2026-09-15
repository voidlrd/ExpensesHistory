from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QTabWidget, QMessageBox, QGroupBox, QLabel, QInputDialog
)
from PyQt6.QtCore import Qt
from sqlalchemy.exc import IntegrityError
from repositories.reference_repo import ReferenceRepository
from database import backup
from ui.views.products_panel import ProductsPanel

class DataManagerView(QWidget):
    def __init__(self):
        super().__init__()
        self.ref_repo = ReferenceRepository()
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

        loc_layout.addWidget(self.loc_list)
        loc_layout.addLayout(loc_btn_layout)

        cp_right_panel.addWidget(self.loc_group)
        self.loc_group.setEnabled(False)

        cp_layout.addLayout(cp_right_panel, 1)
        self.tabs.addTab(self.cp_tab, "Stores & People")

        self.products_panel = ProductsPanel()
        self.tabs.addTab(self.products_panel, "Products")

        self.backup_tab = QWidget()
        backup_layout = QVBoxLayout(self.backup_tab)
        self.backup_btn = QPushButton("Create Database Backup")
        self.backup_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-size: 14px; max-width: 250px;")
        self.backup_btn.clicked.connect(self.create_backup)

        backup_msg = QLabel(
            "<h3>Protect your data</h3>"
            "Click the button below to save a copy of your database in the 'backups' folder next to the app. "
            "Backups you make here are never deleted.<br><br>"
            f"The app also backs up automatically when it starts, if anything changed since the last "
            f"automatic backup, and keeps the {backup.KEEP_AUTO} most recent ones."
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
            backup_path = backup.create_backup()
            QMessageBox.information(self, "Success", f"Backup created successfully!\n\nLocation: {backup_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup:\n{str(e)}")

    @staticmethod
    def _selected_id(list_widget):
        item = list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole).id if item is not None else None

    @staticmethod
    def _select_by_id(list_widget, record_id):
        if record_id is None:
            return
        for row in range(list_widget.count()):
            if list_widget.item(row).data(Qt.ItemDataRole.UserRole).id == record_id:
                list_widget.setCurrentRow(row)
                return

    def load_data(self):
        cp_id = self._selected_id(self.cp_list)

        self.cp_cat_input.clear()
        for cat in self.ref_repo.get_all_counterparty_categories():
            self.cp_cat_input.addItem(cat.name, userData=cat.id)

        self.cp_list.clear()
        for cp in self.ref_repo.get_all_counterparties(include_hidden=True):
            display_name = f"🚫 {cp.name}" if cp.hidden else cp.name
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, cp)
            self.cp_list.addItem(item)

        self._select_by_id(self.cp_list, cp_id)
        self.products_panel.load_data()

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

        try:
            self.ref_repo.update_counterparty(cp.id, new_name, cat_id)
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        QMessageBox.information(self, "Success", "Store updated successfully.")
        self.load_data()

    def toggle_hide_cp(self):
        item = self.cp_list.currentItem()
        if not item: return

        cp = item.data(Qt.ItemDataRole.UserRole)
        self.ref_repo.set_hidden_status(cp.id, not cp.hidden)
        self.load_data()

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
            except (ValueError, IntegrityError):
                QMessageBox.warning(self, "Error", "This location already exists for this store.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add location:\n{e}")

    def remove_location(self):
        loc_item = self.loc_list.currentItem()
        cp_item = self.cp_list.currentItem()
        if not loc_item or not cp_item: return
        loc_id = loc_item.data(Qt.ItemDataRole.UserRole)

        try:
            self.ref_repo.remove_location(loc_id)
            self.load_locations(cp_item.data(Qt.ItemDataRole.UserRole))
        except ValueError as e:
            QMessageBox.warning(self, "Action Denied", str(e))
