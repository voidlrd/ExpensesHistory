from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QTabWidget, QMessageBox, QGroupBox, QLabel, QInputDialog,
    QTableWidget, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QItemSelectionModel, QUrl, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDesktopServices
from sqlalchemy.exc import IntegrityError
from repositories.names import fold_text
from repositories.reference_repo import ReferenceRepository
from database import backup
from ui.views.products_panel import ProductsPanel
from ui.widgets import SortItem, ask_yes_no, repopulate_combo, show_status

CP_COLUMNS = ["Name", "Category", "Receipts", "Spent", "Income", "Last Activity", "Locations"]
(CP_NAME, CP_CATEGORY, CP_RECEIPTS, CP_SPENT, CP_INCOME, CP_LAST, CP_LOCATIONS) = range(len(CP_COLUMNS))

BACKUP_COLUMNS = ["When", "Type", "Size"]

HIDDEN_COLOR = QColor("#9E9E9E")

def _totals_text(totals):
    return " · ".join(f"{totals[code]:,.2f} {code}" for code in sorted(totals))

def _biggest(totals):
    return float(max(totals.values())) if totals else 0.0

class DataManagerView(QWidget):
    database_restored = pyqtSignal()
    show_price_history = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.ref_repo = ReferenceRepository()
        self.overview = []
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tabs.addTab(self._build_counterparty_tab(), "Stores & People")

        self.products_panel = ProductsPanel()
        self.products_panel.show_price_history.connect(self.show_price_history)
        self.tabs.addTab(self.products_panel, "Products")

        self.tabs.addTab(self._build_backup_tab(), "Backups")

        main_layout.addWidget(self.tabs)

    # ---------- stores & people ----------

    def _build_counterparty_tab(self):
        tab = QWidget()
        cp_layout = QHBoxLayout(tab)
        left = QVBoxLayout()

        filter_row = QHBoxLayout()
        self.cp_search = QLineEdit()
        self.cp_search.setPlaceholderText("Search stores and people...")
        self.cp_search.setClearButtonEnabled(True)
        self.cp_search.textChanged.connect(self.refresh_cp_table)
        self.cp_category_filter = QComboBox()
        self.cp_category_filter.currentIndexChanged.connect(self.refresh_cp_table)
        filter_row.addWidget(self.cp_search, 2)
        filter_row.addWidget(self.cp_category_filter, 1)
        left.addLayout(filter_row)

        self.cp_count_label = QLabel()
        left.addWidget(self.cp_count_label)

        self.cp_table = QTableWidget(0, len(CP_COLUMNS))
        self.cp_table.setHorizontalHeaderLabels(CP_COLUMNS)
        self.cp_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cp_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.cp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cp_table.setAlternatingRowColors(True)
        self.cp_table.verticalHeader().setVisible(False)
        header = self.cp_table.horizontalHeader()
        for col in range(len(CP_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(CP_NAME, QHeaderView.ResizeMode.Stretch)
        self.cp_table.setSortingEnabled(True)
        self.cp_table.sortByColumn(CP_NAME, Qt.SortOrder.AscendingOrder)
        self.cp_table.itemSelectionChanged.connect(self.on_cp_selection_changed)
        left.addWidget(self.cp_table)

        bulk_row = QHBoxLayout()
        self.cp_selection_label = QLabel()
        self.cp_hide_btn = QPushButton("Hide")
        self.cp_hide_btn.clicked.connect(lambda: self.set_cp_hidden(True))
        self.cp_unhide_btn = QPushButton("Unhide")
        self.cp_unhide_btn.clicked.connect(lambda: self.set_cp_hidden(False))
        self.cp_merge_btn = QPushButton("Merge...")
        self.cp_merge_btn.setToolTip("Combine duplicates: receipts and income move to the one you keep")
        self.cp_merge_btn.clicked.connect(self.merge_selected_cps)
        self.cp_delete_btn = QPushButton("Delete")
        self.cp_delete_btn.setToolTip("Only for stores with no receipts or income")
        self.cp_delete_btn.clicked.connect(self.delete_selected_cps)

        bulk_row.addWidget(self.cp_selection_label)
        bulk_row.addStretch()
        for btn in (self.cp_hide_btn, self.cp_unhide_btn, self.cp_merge_btn, self.cp_delete_btn):
            bulk_row.addWidget(btn)
        left.addLayout(bulk_row)

        cp_layout.addLayout(left, 3)

        right = QVBoxLayout()
        self.cp_form_group = QGroupBox("Edit Store/Person")
        cp_form_layout = QFormLayout(self.cp_form_group)

        self.cp_name_input = QLineEdit()
        self.cp_cat_input = QComboBox()
        self.cp_usage_label = QLabel()
        self.cp_usage_label.setWordWrap(True)
        self.cp_usage_label.setStyleSheet("color: #9E9E9E;")

        self.cp_save_btn = QPushButton("Save Changes")
        self.cp_save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.cp_save_btn.clicked.connect(self.save_cp_changes)

        cp_form_layout.addRow("Name:", self.cp_name_input)
        cp_form_layout.addRow("Category:", self.cp_cat_input)
        cp_form_layout.addRow("", self.cp_usage_label)
        cp_form_layout.addRow("", self.cp_save_btn)
        right.addWidget(self.cp_form_group)

        self.loc_group = QGroupBox("Manage Locations")
        loc_layout = QVBoxLayout(self.loc_group)
        self.loc_list = QListWidget()

        loc_btn_layout = QHBoxLayout()
        self.loc_add_btn = QPushButton("Add")
        self.loc_add_btn.clicked.connect(self.add_location)
        self.loc_rename_btn = QPushButton("Rename")
        self.loc_rename_btn.clicked.connect(self.rename_location)
        self.loc_del_btn = QPushButton("Remove")
        self.loc_del_btn.clicked.connect(self.remove_location)
        for btn in (self.loc_add_btn, self.loc_rename_btn, self.loc_del_btn):
            loc_btn_layout.addWidget(btn)

        loc_layout.addWidget(self.loc_list)
        loc_layout.addLayout(loc_btn_layout)
        right.addWidget(self.loc_group)
        self.loc_group.setEnabled(False)

        self.cp_status_label = QLabel()
        self.cp_status_label.setWordWrap(True)
        right.addWidget(self.cp_status_label)
        right.addStretch()

        cp_layout.addLayout(right, 2)
        return tab

    def load_data(self):
        self.overview = self.ref_repo.get_counterparty_overview()
        categories = self.ref_repo.get_all_counterparty_categories()

        repopulate_combo(self.cp_cat_input, [(cat.name, cat.id) for cat in categories], block_signals=True)
        repopulate_combo(self.cp_category_filter, [(cat.name, cat.id) for cat in categories],
                         placeholder=("All categories", None), block_signals=True)

        self.refresh_cp_table()
        self.products_panel.load_data()

    def _entry(self, cp_id):
        return next((e for e in self.overview if e.counterparty.id == cp_id), None)

    def _cp_matches(self, entry):
        cp = entry.counterparty
        search = fold_text(self.cp_search.text().strip())
        if search and search not in fold_text(cp.name):
            return False
        category = self.cp_category_filter.currentData()
        return category is None or cp.category_id == category

    def refresh_cp_table(self):
        selected = set(self.selected_cp_ids())
        visible = [e for e in self.overview if self._cp_matches(e)]

        self.cp_table.blockSignals(True)
        self.cp_table.setSortingEnabled(False)
        self.cp_table.setRowCount(0)
        for row, entry in enumerate(visible):
            self.cp_table.insertRow(row)
            cp = entry.counterparty
            cells = {
                CP_NAME: SortItem(cp.name, fold_text(cp.name)),
                CP_CATEGORY: SortItem(cp.category.name if cp.category else ""),
                CP_RECEIPTS: SortItem(str(entry.receipts), entry.receipts, align_right=True),
                CP_SPENT: SortItem(_totals_text(entry.spent), _biggest(entry.spent), align_right=True),
                CP_INCOME: SortItem(_totals_text(entry.earned), _biggest(entry.earned), align_right=True),
                CP_LAST: SortItem(str(entry.last_date) if entry.last_date else "Never",
                                  str(entry.last_date or "")),
                CP_LOCATIONS: SortItem(str(entry.locations) if entry.locations else "",
                                       entry.locations, align_right=True),
            }
            cells[CP_NAME].setData(Qt.ItemDataRole.UserRole, cp.id)
            if cp.hidden:
                cells[CP_NAME].setText(f"\U0001F6AB {cp.name}")
                for cell in cells.values():
                    cell.setForeground(QBrush(HIDDEN_COLOR))
                    cell.setToolTip("Hidden: not offered when entering receipts")
            for col, cell in cells.items():
                self.cp_table.setItem(row, col, cell)
        self.cp_table.setSortingEnabled(True)

        selection = self.cp_table.selectionModel()
        for row in range(self.cp_table.rowCount()):
            if self.cp_table.item(row, CP_NAME).data(Qt.ItemDataRole.UserRole) in selected:
                selection.select(self.cp_table.model().index(row, CP_NAME),
                                 QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.cp_table.blockSignals(False)

        hidden = sum(1 for e in self.overview if e.counterparty.hidden)
        text = f"Showing {len(visible)} of {len(self.overview)} stores and people"
        if hidden:
            text += f"  ·  {hidden} hidden"
        self.cp_count_label.setText(text)
        self.on_cp_selection_changed()

    def selected_cp_ids(self):
        rows = {index.row() for index in self.cp_table.selectionModel().selectedRows()}
        return [self.cp_table.item(row, CP_NAME).data(Qt.ItemDataRole.UserRole) for row in sorted(rows)]

    def _selected_entries(self):
        return [e for e in (self._entry(i) for i in self.selected_cp_ids()) if e is not None]

    def on_cp_selection_changed(self):
        entries = self._selected_entries()
        count = len(entries)

        self.cp_selection_label.setText(f"{count} selected:" if count else "Select stores to tidy up:")
        self.cp_delete_btn.setEnabled(count >= 1)
        self.cp_hide_btn.setEnabled(any(not e.counterparty.hidden for e in entries))
        self.cp_unhide_btn.setEnabled(any(e.counterparty.hidden for e in entries))
        self.cp_merge_btn.setEnabled(count >= 2)

        self.cp_form_group.setEnabled(count == 1)
        self.loc_group.setEnabled(count == 1)
        if count == 1:
            self._fill_cp_form(entries[0])
        else:
            self.cp_name_input.clear()
            self.loc_list.clear()
            self.cp_usage_label.setText("Select one to edit it." if count == 0
                                        else "Use the buttons under the table to change them together.")

    def _fill_cp_form(self, entry):
        cp = entry.counterparty
        self.cp_name_input.setText(cp.name)
        idx = self.cp_cat_input.findData(cp.category_id)
        if idx >= 0:
            self.cp_cat_input.setCurrentIndex(idx)

        parts = []
        if entry.receipts:
            parts.append(f"{entry.receipts} receipt(s), {_totals_text(entry.spent)} spent")
        if entry.incomes:
            parts.append(f"{entry.incomes} income record(s), {_totals_text(entry.earned)} received")
        if entry.last_date:
            parts.append(f"last on {entry.last_date}")
        self.cp_usage_label.setText(". ".join(parts) + "." if parts else "Nothing recorded yet.")

        self.load_locations(cp)

    def save_cp_changes(self):
        entries = self._selected_entries()
        if len(entries) != 1:
            return

        cp = entries[0].counterparty
        new_name = self.cp_name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Name cannot be empty.")
            return

        try:
            self.ref_repo.update_counterparty(cp.id, new_name, self.cp_cat_input.currentData())
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        self.load_data()
        show_status(self.cp_status_label, f"✓ Saved {new_name}")

    def set_cp_hidden(self, hidden):
        ids = self.selected_cp_ids()
        if not ids:
            return
        self.ref_repo.set_hidden_for(ids, hidden)
        self.load_data()
        show_status(self.cp_status_label, f"✓ {'Hidden' if hidden else 'Unhidden'} {len(ids)}")

    def merge_selected_cps(self):
        entries = self._selected_entries()
        if len(entries) < 2:
            return

        labels = [f"{e.counterparty.name}  ({e.receipts} receipts)" for e in entries]
        busiest = max(range(len(entries)), key=lambda i: entries[i].receipts)
        choice, ok = QInputDialog.getItem(
            self, "Merge Stores", "Keep this one. The others' receipts and income move into it:",
            labels, busiest, False
        )
        if not ok:
            return
        keep = entries[labels.index(choice)]
        others = [e for e in entries if e is not keep]

        if not ask_yes_no(
            self, "Merge Stores",
            f"Merge {', '.join(e.counterparty.name for e in others)} into {keep.counterparty.name}?\n\n"
            f"Their receipts, income and locations move to {keep.counterparty.name} and they are deleted. "
            "Totals don't change."
        ):
            return

        try:
            receipts, incomes = self.ref_repo.merge_counterparties(
                keep.counterparty.id, [e.counterparty.id for e in others]
            )
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        self.load_data()
        show_status(self.cp_status_label,
                    f"✓ Merged into {keep.counterparty.name} ({receipts} receipt(s), {incomes} income record(s) moved)")

    def delete_selected_cps(self):
        entries = self._selected_entries()
        if not entries:
            return
        names = ", ".join(e.counterparty.name for e in entries)
        if not ask_yes_no(self, "Delete Stores",
                          f"Delete {names}?\n\nOnly ones with no receipts or income can be deleted."):
            return
        try:
            self.ref_repo.delete_counterparties([e.counterparty.id for e in entries])
        except ValueError as e:
            QMessageBox.warning(self, "Can't Delete", str(e))
            return
        self.load_data()
        show_status(self.cp_status_label, f"✓ Deleted {len(entries)}")

    # ---------- locations ----------

    def _selected_cp(self):
        entries = self._selected_entries()
        return entries[0].counterparty if len(entries) == 1 else None

    def load_locations(self, cp):
        self.loc_list.clear()
        for loc in self.ref_repo.get_locations_for_counterparty(cp.name):
            item = QListWidgetItem(loc.label)
            item.setData(Qt.ItemDataRole.UserRole, loc.id)
            self.loc_list.addItem(item)

    def add_location(self):
        cp = self._selected_cp()
        if cp is None:
            return

        text, ok = QInputDialog.getText(self, "New Location", "Enter location label/branch name:")
        if ok and text.strip():
            try:
                self.ref_repo.add_location(cp.id, text.strip())
                self.load_data()
            except (ValueError, IntegrityError):
                QMessageBox.warning(self, "Error", "This location already exists for this store.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add location:\n{e}")

    def rename_location(self):
        loc_item = self.loc_list.currentItem()
        cp = self._selected_cp()
        if loc_item is None or cp is None:
            return

        text, ok = QInputDialog.getText(self, "Rename Location", "New name:", text=loc_item.text())
        if not ok or not text.strip():
            return
        try:
            self.ref_repo.rename_location(loc_item.data(Qt.ItemDataRole.UserRole), text.strip())
        except (ValueError, IntegrityError) as e:
            QMessageBox.warning(self, "Error", str(e) if isinstance(e, ValueError)
                                else "This location already exists for this store.")
            return
        self.load_locations(cp)
        show_status(self.cp_status_label, f"✓ Renamed to {text.strip()}")

    def remove_location(self):
        loc_item = self.loc_list.currentItem()
        cp = self._selected_cp()
        if loc_item is None or cp is None:
            return

        try:
            self.ref_repo.remove_location(loc_item.data(Qt.ItemDataRole.UserRole))
            self.load_locations(cp)
        except ValueError as e:
            QMessageBox.warning(self, "Action Denied", str(e))

    # ---------- backups ----------

    def _build_backup_tab(self):
        tab = QWidget()
        backup_layout = QVBoxLayout(tab)

        backup_msg = QLabel(
            "<h3>Protect your data</h3>"
            "Backups are kept in the 'backups' folder next to the app. The app backs up automatically "
            f"when it starts, if anything changed since the last automatic backup, and keeps the "
            f"{backup.KEEP_AUTO} most recent ones. Backups you make yourself are never deleted."
        )
        backup_msg.setWordWrap(True)
        backup_layout.addWidget(backup_msg)

        self.backup_table = QTableWidget(0, len(BACKUP_COLUMNS))
        self.backup_table.setHorizontalHeaderLabels(BACKUP_COLUMNS)
        self.backup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backup_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.backup_table.setAlternatingRowColors(True)
        self.backup_table.verticalHeader().setVisible(False)
        header = self.backup_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        backup_layout.addWidget(self.backup_table)

        btn_row = QHBoxLayout()
        self.backup_btn = QPushButton("Create Backup Now")
        self.backup_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 6px 12px;")
        self.backup_btn.clicked.connect(self.create_backup)
        self.restore_btn = QPushButton("Restore Selected...")
        self.restore_btn.setToolTip("Replace the current data with this backup")
        self.restore_btn.clicked.connect(self.restore_selected)
        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_backup_folder)

        btn_row.addWidget(self.backup_btn)
        btn_row.addWidget(self.restore_btn)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        backup_layout.addLayout(btn_row)

        self.backup_status_label = QLabel()
        self.backup_status_label.setWordWrap(True)
        backup_layout.addWidget(self.backup_status_label)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.load_backups()
        return tab

    def _on_tab_changed(self, index):
        if self.tabs.tabText(index) == "Backups":
            self.load_backups()

    def load_backups(self):
        entries = backup.list_backups()
        self.backup_table.setRowCount(0)
        for row, (path, kind, when, size) in enumerate(entries):
            self.backup_table.insertRow(row)
            when_item = SortItem(when.strftime("%Y-%m-%d %H:%M:%S"))
            when_item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.backup_table.setItem(row, 0, when_item)
            self.backup_table.setItem(row, 1, SortItem(kind))
            self.backup_table.setItem(row, 2, SortItem(f"{size / 1_048_576:.1f} MB", size, align_right=True))

        self.restore_btn.setEnabled(bool(entries))
        if not entries:
            self.backup_status_label.setStyleSheet("color: #9E9E9E;")
            self.backup_status_label.setText("No backups yet.")

    def create_backup(self):
        try:
            path = backup.create_backup()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create backup:\n{e}")
            return
        self.load_backups()
        show_status(self.backup_status_label, f"✓ Backup created: {path.name}")

    def selected_backup(self):
        rows = {index.row() for index in self.backup_table.selectionModel().selectedRows()}
        if not rows:
            return None
        item = self.backup_table.item(min(rows), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def restore_selected(self):
        path = self.selected_backup()
        if not path:
            QMessageBox.information(self, "Restore", "Select a backup in the list first.")
            return

        if not ask_yes_no(
            self, "Restore Backup",
            f"Replace all current data with this backup?\n\n{path}\n\n"
            "Everything recorded since that backup will be gone. A copy of the current data is saved "
            "first, as a \"Before restore\" backup, so this can be undone."
        ):
            return

        try:
            safety = backup.restore_backup(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Nothing was restored:\n{e}")
            return

        self.load_data()
        self.load_backups()
        self.database_restored.emit()
        note = f" The data from before is saved as {safety.name}." if safety else ""
        show_status(self.backup_status_label, f"✓ Restored from {Path(path).name}.{note}", seconds=20)

    def open_backup_folder(self):
        backup.BACKUP_DIR.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup.BACKUP_DIR)))
