from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout
)
from receipt_import import ScanParseError, parse_scan

class ScanPasteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan = None
        self.setWindowTitle("Paste AI Result")
        self.resize(560, 420)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Paste the AI's whole reply below and click Fill Form. "
            "Nothing is saved until you check the form and press Save."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText('{ "store": ..., "items": [ ... ] }')
        clipboard = QApplication.clipboard().text()
        if "{" in clipboard and '"items"' in clipboard:
            self.text_input.setPlainText(clipboard)
        layout.addWidget(self.text_input)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #F44336; font-weight: bold;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        fill_btn = buttons.addButton("Fill Form", QDialogButtonBox.ButtonRole.AcceptRole)
        fill_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 4px 12px;")
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def try_accept(self):
        try:
            self.scan = parse_scan(self.text_input.toPlainText())
        except ScanParseError as e:
            self.error_label.setText(str(e))
            self.error_label.setVisible(True)
            return
        self.accept()
