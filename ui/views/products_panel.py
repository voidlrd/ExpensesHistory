import unicodedata
from decimal import Decimal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QGroupBox, QLineEdit, QComboBox,
    QCheckBox, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QInputDialog, QCompleter
)
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtCore import Qt, QItemSelectionModel
from repositories.product_repo import ProductRepository
from repositories.reference_repo import ReferenceRepository
from ui.widgets import TrimmedDoubleSpinBox, repopulate_combo
from units import UNITS, PACKAGE_UNITS, describe_package, normalize_unit

FILTER_ALL = "__all__"
FILTER_NONE = "__none__"

COLUMNS = ["Name", "Brand", "Category", "Unit", "Package", "Bought", "Last Bought", "Last Price"]
(COL_NAME, COL_BRAND, COL_CATEGORY, COL_UNIT, COL_PACKAGE,
 COL_BOUGHT, COL_LAST_BOUGHT, COL_LAST_PRICE) = range(len(COLUMNS))

HIDDEN_COLOR = QColor("#9E9E9E")
MISSING_COLOR = QColor("#FF9800")

def _fold(text):
    """Casefold and drop accents, so 'paine' matches 'Pâine'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()

class SortItem(QTableWidgetItem):
    def __init__(self, text, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, SortItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)

class ProductsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.product_repo = ProductRepository()
        self.ref_repo = ReferenceRepository()
        self.overview = []
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        left = QVBoxLayout()

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search name or brand...")
        self.search_input.setClearButtonEnabled(True)
        self.category_filter = QComboBox()
        self.brand_filter = QComboBox()
        self.unit_filter = QComboBox()
        self.unit_filter.addItem("All units", userData=FILTER_ALL)
        for unit in UNITS:
            self.unit_filter.addItem(unit, userData=unit)
        self.show_hidden = QCheckBox("Show hidden")

        filter_row.addWidget(self.search_input, 2)
        filter_row.addWidget(self.category_filter, 1)
        filter_row.addWidget(self.brand_filter, 1)
        filter_row.addWidget(self.unit_filter)
        filter_row.addWidget(self.show_hidden)
        left.addLayout(filter_row)

        self.count_label = QLabel()
        left.addWidget(self.count_label)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col in range(len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(COL_NAME, Qt.SortOrder.AscendingOrder)
        left.addWidget(self.table)

        bulk_row = QHBoxLayout()
        self.selection_label = QLabel()
        self.bulk_category = QComboBox()
        self.bulk_category.setEditable(True)
        self.bulk_category.setMinimumWidth(140)
        self.set_category_btn = QPushButton("Set Category")
        self.hide_btn = QPushButton("Hide")
        self.unhide_btn = QPushButton("Unhide")
        self.merge_btn = QPushButton("Merge...")
        self.merge_btn.setToolTip("Combine duplicates: purchases move to the product you keep")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Only for products that were never bought")

        bulk_row.addWidget(self.selection_label)
        bulk_row.addWidget(self.bulk_category)
        bulk_row.addWidget(self.set_category_btn)
        bulk_row.addStretch()
        for btn in (self.hide_btn, self.unhide_btn, self.merge_btn, self.delete_btn):
            bulk_row.addWidget(btn)
        left.addLayout(bulk_row)

        layout.addLayout(left, 3)

        self.edit_group = QGroupBox("Edit Product")
        form = QFormLayout(self.edit_group)
        self.name_input = QLineEdit()
        self.brand_input = QLineEdit()
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.setPlaceholderText("Select or type new category...")
        self.unit_input = QComboBox()
        self.unit_input.addItems(UNITS)
        self.unit_input.setToolTip("What the Amount on a receipt counts")
        self.package_size = TrimmedDoubleSpinBox()
        self.package_size.setRange(0, 99999.999)
        self.package_size.setDecimals(3)
        # a space shows the field blank at 0 (no package size); "" would disable it
        self.package_size.setSpecialValueText(" ")
        self.package_unit = QComboBox()
        self.package_unit.addItems(PACKAGE_UNITS)
        package_layout = QHBoxLayout()
        package_layout.addWidget(self.package_size)
        package_layout.addWidget(self.package_unit)
        self.usage_label = QLabel()
        self.usage_label.setWordWrap(True)
        self.usage_label.setStyleSheet("color: #9E9E9E;")
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.status_label = QLabel()

        form.addRow("Name:", self.name_input)
        form.addRow("Brand:", self.brand_input)
        form.addRow("Category:", self.category_input)
        form.addRow("Unit:", self.unit_input)
        form.addRow("Package size:", package_layout)
        form.addRow("", self.usage_label)
        form.addRow("", self.save_btn)
        form.addRow("", self.status_label)
        layout.addWidget(self.edit_group, 2)

        self.search_input.textChanged.connect(self.refresh_table)
        self.category_filter.currentIndexChanged.connect(self.refresh_table)
        self.brand_filter.currentIndexChanged.connect(self.refresh_table)
        self.unit_filter.currentIndexChanged.connect(self.refresh_table)
        self.show_hidden.toggled.connect(self.refresh_table)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.unit_input.currentTextChanged.connect(self._update_package_enabled)
        self.save_btn.clicked.connect(self.save_product)
        self.set_category_btn.clicked.connect(self.set_category_for_selected)
        self.hide_btn.clicked.connect(lambda: self.set_hidden_for_selected(True))
        self.unhide_btn.clicked.connect(lambda: self.set_hidden_for_selected(False))
        self.merge_btn.clicked.connect(self.merge_selected)
        self.delete_btn.clicked.connect(self.delete_selected)

    # ---------- data ----------

    def load_data(self):
        self.overview = self.product_repo.get_product_overview()
        categories = self.ref_repo.get_all_item_categories()
        brands = sorted({o.product.brand for o in self.overview if o.product.brand}, key=str.casefold)

        repopulate_combo(self.category_filter,
                         [("No category", FILTER_NONE)] + [(c.name, c.id) for c in categories],
                         placeholder=("All categories", FILTER_ALL), block_signals=True)
        repopulate_combo(self.brand_filter,
                         [("No brand", FILTER_NONE)] + [(b, b) for b in brands],
                         placeholder=("All brands", FILTER_ALL), block_signals=True)
        repopulate_combo(self.category_input, [(c.name, c.id) for c in categories],
                         placeholder=("", None), block_signals=True)
        bulk_text = self.bulk_category.currentText()
        repopulate_combo(self.bulk_category, [(c.name, c.id) for c in categories], block_signals=True)
        self.bulk_category.setCurrentText(bulk_text)

        completer = QCompleter(brands, self.brand_input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.brand_input.setCompleter(completer)

        self.refresh_table()

    def _entry(self, product_id):
        return next((e for e in self.overview if e.product.id == product_id), None)

    def _matches(self, entry):
        p = entry.product
        if p.hidden and not self.show_hidden.isChecked():
            return False

        search = _fold(self.search_input.text().strip())
        if search and search not in _fold(p.name) and search not in _fold(p.brand):
            return False

        category = self.category_filter.currentData()
        if category == FILTER_NONE and p.category_id is not None:
            return False
        if category not in (FILTER_ALL, FILTER_NONE, None) and p.category_id != category:
            return False

        brand = self.brand_filter.currentData()
        if brand == FILTER_NONE and p.brand:
            return False
        if brand not in (FILTER_ALL, FILTER_NONE, None) and (p.brand or "").casefold() != brand.casefold():
            return False

        unit = self.unit_filter.currentData()
        if unit not in (FILTER_ALL, None) and normalize_unit(p.unit_of_measure) != unit:
            return False
        return True

    def refresh_table(self):
        selected = set(self.selected_ids())
        visible = [e for e in self.overview if self._matches(e)]

        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row, entry in enumerate(visible):
            self.table.insertRow(row)
            p = entry.product
            unit = normalize_unit(p.unit_of_measure)
            package = describe_package(p.package_size, p.package_unit)
            cells = {
                COL_NAME: SortItem(p.name, _fold(p.name)),
                COL_BRAND: SortItem(p.brand or "", _fold(p.brand)),
                COL_CATEGORY: SortItem(p.category.name if p.category else "No category",
                                       _fold(p.category.name) if p.category else ""),
                COL_UNIT: SortItem(unit, unit),
                COL_PACKAGE: SortItem(package, (p.package_unit or "", float(p.package_size or 0))),
                COL_BOUGHT: SortItem(str(entry.purchases), entry.purchases),
                COL_LAST_BOUGHT: SortItem(str(entry.last_date) if entry.last_date else "Never",
                                          str(entry.last_date or "")),
                COL_LAST_PRICE: SortItem(
                    f"{entry.last_price:.2f} {entry.last_currency} / {unit}" if entry.last_price is not None else "",
                    entry.last_price if entry.last_price is not None else -1.0),
            }
            cells[COL_NAME].setData(Qt.ItemDataRole.UserRole, p.id)
            for col in (COL_BOUGHT, COL_LAST_PRICE):
                cells[col].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if not p.category:
                cells[COL_CATEGORY].setForeground(QBrush(MISSING_COLOR))
            if p.hidden:
                cells[COL_NAME].setText(f"\U0001F6AB {p.name}")
                for cell in cells.values():
                    cell.setForeground(QBrush(HIDDEN_COLOR))
                    cell.setToolTip("Hidden: not offered when entering receipts")
            for col, cell in cells.items():
                self.table.setItem(row, col, cell)
        self.table.setSortingEnabled(True)

        selection = self.table.selectionModel()
        for row in range(self.table.rowCount()):
            if self.table.item(row, COL_NAME).data(Qt.ItemDataRole.UserRole) in selected:
                selection.select(self.table.model().index(row, COL_NAME),
                                 QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.table.blockSignals(False)

        total = len(self.overview)
        show_hidden = self.show_hidden.isChecked()
        uncategorized = sum(1 for e in self.overview
                            if e.product.category_id is None and (show_hidden or not e.product.hidden))
        text = f"Showing {len(visible)} of {total} products"
        if uncategorized:
            text += f"  ·  {uncategorized} without a category"
        self.count_label.setText(text)
        self.on_selection_changed()

    def selected_ids(self):
        rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        return [self.table.item(row, COL_NAME).data(Qt.ItemDataRole.UserRole) for row in sorted(rows)]

    # ---------- selection & edit form ----------

    def on_selection_changed(self):
        entries = [e for e in (self._entry(i) for i in self.selected_ids()) if e is not None]
        count = len(entries)

        self.selection_label.setText(f"{count} selected:" if count else "Select products to tidy up:")
        for widget in (self.bulk_category, self.set_category_btn, self.delete_btn):
            widget.setEnabled(count >= 1)
        self.hide_btn.setEnabled(any(not e.product.hidden for e in entries))
        self.unhide_btn.setEnabled(any(e.product.hidden for e in entries))
        self.merge_btn.setEnabled(count >= 2)

        self.edit_group.setEnabled(count == 1)
        if count == 1:
            self.edit_group.setTitle("Edit Product")
            self._fill_form(entries[0])
        else:
            self.edit_group.setTitle("Edit Product" if count == 0 else f"{count} products selected")
            self.name_input.clear()
            self.brand_input.clear()
            self.category_input.setCurrentIndex(0)
            self.package_size.setValue(0)
            self.usage_label.setText("Select one product to edit it." if count == 0
                                     else "Use the buttons under the table to change them together.")

    def _fill_form(self, entry):
        p = entry.product
        self.name_input.setText(p.name)
        self.brand_input.setText(p.brand or "")
        idx = self.category_input.findData(p.category_id) if p.category_id else 0
        self.category_input.setCurrentIndex(max(idx, 0))
        self.unit_input.setCurrentText(normalize_unit(p.unit_of_measure))
        self.package_size.setValue(float(p.package_size or 0))
        self.package_unit.setCurrentText(p.package_unit or PACKAGE_UNITS[0])
        self._update_package_enabled()

        if entry.purchases:
            times = "once" if entry.purchases == 1 else f"{entry.purchases} times"
            self.usage_label.setText(
                f"Bought {times}. Last on {entry.last_date} at {entry.last_store}, "
                f"{entry.last_price:.2f} {entry.last_currency} / {normalize_unit(p.unit_of_measure)}."
            )
        else:
            self.usage_label.setText("Never bought.")

    def _update_package_enabled(self, *args):
        counted = self.unit_input.currentText() == "pcs"
        self.package_size.setEnabled(counted)
        self.package_unit.setEnabled(counted)

    def save_product(self):
        ids = self.selected_ids()
        if len(ids) != 1:
            return
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Product name cannot be empty.")
            return

        size = self.package_size.value()
        package_size = Decimal(f"{size:.3f}") if size > 0 else None
        try:
            self.product_repo.update_product(
                ids[0], name, self.brand_input.text().strip(), self.unit_input.currentText(),
                self.category_input.currentText().strip(),
                package_size, self.package_unit.currentText() if package_size else None
            )
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        self.load_data()
        self.status_label.setText(f"✓ Saved {name}")

    # ---------- bulk actions ----------

    def set_category_for_selected(self):
        ids = self.selected_ids()
        if not ids:
            return
        name = self.bulk_category.currentText().strip()
        if not name:
            reply = QMessageBox.question(
                self, "Remove Category?",
                f"No category is chosen. Remove the category from {len(ids)} product(s)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.product_repo.set_category(ids, name or None)
        self.load_data()
        self.status_label.setText(f"✓ Category set for {len(ids)} product(s)")

    def set_hidden_for_selected(self, hidden):
        ids = self.selected_ids()
        if not ids:
            return
        self.product_repo.set_hidden(ids, hidden)
        self.load_data()
        self.status_label.setText(f"✓ {'Hidden' if hidden else 'Unhidden'} {len(ids)} product(s)")

    def merge_selected(self):
        entries = [e for e in (self._entry(i) for i in self.selected_ids()) if e is not None]
        if len(entries) < 2:
            return

        labels = [f"{e.product.name}  ({e.purchases} bought)" for e in entries]
        busiest = max(range(len(entries)), key=lambda i: entries[i].purchases)
        choice, ok = QInputDialog.getItem(
            self, "Merge Products", "Keep this product. The others' purchases move into it:",
            labels, busiest, False
        )
        if not ok:
            return
        keep = entries[labels.index(choice)]
        others = [e for e in entries if e is not keep]

        units = sorted({normalize_unit(e.product.unit_of_measure) for e in entries})
        unit_warning = ""
        if len(units) > 1:
            unit_warning = (f"\n\nThese products use different units ({', '.join(units)}). "
                            f"All their purchases will count as {normalize_unit(keep.product.unit_of_measure)}.")
        reply = QMessageBox.question(
            self, "Merge Products",
            f"Merge {', '.join(e.product.name for e in others)} into {keep.product.name}?\n\n"
            f"Their purchases move to {keep.product.name} and they are deleted. "
            f"Receipts and totals don't change.{unit_warning}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            moved = self.product_repo.merge_products(keep.product.id, [e.product.id for e in others])
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        self.load_data()
        self.status_label.setText(f"✓ Merged into {keep.product.name} ({moved} purchase(s) moved)")

    def delete_selected(self):
        entries = [e for e in (self._entry(i) for i in self.selected_ids()) if e is not None]
        if not entries:
            return
        names = ", ".join(e.product.name for e in entries)
        reply = QMessageBox.question(
            self, "Delete Products",
            f"Delete {names}?\n\nOnly products that were never bought can be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.product_repo.delete_unused_products([e.product.id for e in entries])
        except ValueError as e:
            QMessageBox.warning(self, "Can't Delete", str(e))
            return
        self.load_data()
        self.status_label.setText(f"✓ Deleted {len(entries)} product(s)")
