from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout
)

from receipt_inbox import list_receipts, remove_receipt
from ui.widgets import ask_yes_no

THUMBNAIL = QSize(72, 72)


def thumbnail(path):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if reader.size().isValid():
        reader.setScaledSize(reader.size().scaled(THUMBNAIL, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    return QIcon(QPixmap.fromImage(image)) if not image.isNull() else QIcon()


def describe(receipt):
    count = len(receipt.photos)
    return f"{receipt.received:%d %b %Y, %H:%M}  ·  {count} photo{'s' if count != 1 else ''}"


class InboxDialog(QDialog):
    """Receipts waiting to be read; the one picked for scanning ends up in .chosen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chosen = None
        self.setWindowTitle("Receipt Inbox")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        hint = QLabel("Receipts sent from your phone wait here. A scanned receipt leaves the inbox "
                      "once you save it.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list = QListWidget()
        self.list.setIconSize(THUMBNAIL)
        self.list.itemDoubleClicked.connect(self.scan_selected)
        self.list.currentRowChanged.connect(self._update_buttons)
        layout.addWidget(self.list)

        buttons = QHBoxLayout()
        self.scan_btn = QPushButton("Scan with AI")
        self.scan_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 4px 12px;")
        self.scan_btn.clicked.connect(self.scan_selected)
        self.open_btn = QPushButton("Open Photos")
        self.open_btn.clicked.connect(self.open_selected)
        self.discard_btn = QPushButton("Discard")
        self.discard_btn.clicked.connect(self.discard_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        for button in (self.scan_btn, self.open_btn, self.discard_btn):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.load()

    def load(self):
        self.list.clear()
        for receipt in list_receipts():
            item = QListWidgetItem(thumbnail(receipt.photos[0]), describe(receipt))
            item.setData(Qt.ItemDataRole.UserRole, receipt)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.list.addItem("The inbox is empty.")
        self._update_buttons()

    def selected(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _update_buttons(self, *args):
        has_receipt = self.selected() is not None
        for button in (self.scan_btn, self.open_btn, self.discard_btn):
            button.setEnabled(has_receipt)

    def scan_selected(self, *args):
        receipt = self.selected()
        if receipt is not None:
            self.chosen = receipt
            self.accept()

    def open_selected(self):
        receipt = self.selected()
        if receipt is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(receipt.folder)))

    def discard_selected(self):
        receipt = self.selected()
        if receipt is None or not ask_yes_no(self, "Discard Receipt",
                                             f"Delete this receipt's photos ({describe(receipt)})?"):
            return
        remove_receipt(receipt)
        self.load()
