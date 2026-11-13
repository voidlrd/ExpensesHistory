import segno
from keyring.errors import KeyringError
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget
)

from app_logging import log
from app_settings import (
    ai_model, ai_provider, api_key, phone_enabled, phone_port, remove_api_key, save_api_key, set_ai_model,
    set_ai_provider, set_phone_enabled, set_phone_port
)
from receipt_ai import PROVIDERS, AIError
from ui.phone_link import PhoneLink
from ui.widgets import ask_yes_no, run_in_background, show_status

HINT_STYLE = "color: #9E9E9E;"


def qr_pixmap(text, scale=5):
    rows = list(segno.make(text, error="m").matrix_iter(border=4))
    image = QImage(len(rows[0]), len(rows), QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    for y, row in enumerate(rows):
        for x, dark in enumerate(row):
            if dark:
                image.setPixel(x, y, 0xFF000000)
    return QPixmap.fromImage(image.scaled(image.width() * scale, image.height() * scale))


class AIPanel(QWidget):
    def __init__(self, phone_link=None):
        super().__init__()
        self.phone_link = phone_link or PhoneLink(self)
        self.setup_ui()
        self.load()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        group = QGroupBox("Read receipts with AI")
        form = QFormLayout(group)

        intro = QLabel(
            "Let Claude or Gemini read receipt photos for you. You need an API key from the one you pick; "
            "each receipt costs a few cents, billed by them. The key is kept in Windows Credential Manager, "
            "not in your expenses data or its backups."
        )
        intro.setWordWrap(True)

        self.provider_input = QComboBox()
        for key, provider in PROVIDERS.items():
            self.provider_input.addItem(provider.name, userData=key)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Paste the API key here")
        self.save_key_btn = QPushButton("Save Key")
        self.remove_key_btn = QPushButton("Remove")
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_input, 1)
        key_row.addWidget(self.save_key_btn)
        key_row.addWidget(self.remove_key_btn)

        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        self.key_status.setOpenExternalLinks(True)
        self.key_status.setStyleSheet(HINT_STYLE)

        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.model_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_input.setToolTip("The first one is a good default. You can type a newer model's name.")

        key_box = QVBoxLayout()
        key_box.addLayout(key_row)
        key_box.addWidget(self.key_status)

        self.test_btn = QPushButton("Test Key")
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        test_row = QHBoxLayout()
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.status_label, 1)

        form.addRow(intro)
        form.addRow("Provider:", self.provider_input)
        form.addRow("API key:", key_box)
        form.addRow("Model:", self.model_input)
        form.addRow("", test_row)

        layout.addWidget(group)
        layout.addWidget(self._build_phone_group())
        layout.addStretch()

        self.provider_input.currentIndexChanged.connect(self.on_provider_changed)
        self.key_input.returnPressed.connect(self.save_key)
        self.save_key_btn.clicked.connect(self.save_key)
        self.remove_key_btn.clicked.connect(self.remove_key)
        self.model_input.currentTextChanged.connect(self.on_model_changed)
        self.test_btn.clicked.connect(self.test_key)

    def _build_phone_group(self):
        group = QGroupBox("Send receipts from your phone")
        layout = QVBoxLayout(group)

        intro = QLabel("Take receipt photos on your phone and send them here over your Wi-Fi. "
                       "They wait in the Inbox on New Transaction until you scan them.")
        intro.setWordWrap(True)

        self.phone_toggle = QCheckBox("Receive receipts from my phone")
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setToolTip("Change it only if another program already uses this port")
        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self.phone_toggle)
        toggle_row.addStretch()
        toggle_row.addWidget(QLabel("Port:"))
        toggle_row.addWidget(self.port_input)

        self.qr_label = QLabel()
        self.url_label = QLabel()
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.url_label.setStyleSheet("font-weight: bold;")
        hint = QLabel("Scan the code with your phone's camera and bookmark the page. The phone must be on "
                      "the same Wi-Fi. If Windows asks whether to allow access, allow it on private networks.")
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        self.new_link_btn = QPushButton("New Link")
        self.new_link_btn.setToolTip("Make a new address; the old one stops working")

        link_column = QVBoxLayout()
        link_column.addWidget(self.url_label)
        link_column.addWidget(hint)
        link_column.addWidget(self.new_link_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        link_column.addStretch()
        self.phone_details = QWidget()
        details = QHBoxLayout(self.phone_details)
        details.setContentsMargins(0, 0, 0, 0)
        details.addWidget(self.qr_label)
        details.addLayout(link_column, 1)

        self.phone_status = QLabel()
        self.phone_status.setWordWrap(True)

        layout.addWidget(intro)
        layout.addLayout(toggle_row)
        layout.addWidget(self.phone_details)
        layout.addWidget(self.phone_status)

        self.phone_toggle.toggled.connect(self.on_phone_toggled)
        self.port_input.editingFinished.connect(self.on_port_changed)
        self.new_link_btn.clicked.connect(self.renew_link)
        return group

    def provider(self):
        return self.provider_input.currentData()

    def load(self):
        self.provider_input.blockSignals(True)
        self.provider_input.setCurrentIndex(self.provider_input.findData(ai_provider()))
        self.provider_input.blockSignals(False)
        self._show_provider()
        self.port_input.setValue(phone_port())
        self._show_phone()
        if phone_enabled() and not self.phone_link.running:
            self._port_problem()

    # ---------- phone ----------

    def _show_phone(self):
        running = self.phone_link.running
        self.phone_toggle.blockSignals(True)
        self.phone_toggle.setChecked(running)
        self.phone_toggle.blockSignals(False)
        self.phone_details.setVisible(running)
        if running:
            url = self.phone_link.url()
            self.url_label.setText(url)
            self.qr_label.setPixmap(qr_pixmap(url))

    def _port_problem(self, error=None):
        reason = f" ({error.strerror or error})" if error else ""
        show_status(self.phone_status, f"Couldn't receive on port {phone_port()}{reason}. Another program may be "
                                       "using it: pick another port.", "warn", seconds=120)

    def _start_phone(self):
        try:
            self.phone_link.start()
        except OSError as e:
            log.warning("phone page couldn't start on port %s: %s", phone_port(), e)
            self._port_problem(e)
            return False
        show_status(self.phone_status, "✓ Ready. Scan the code with your phone.")
        return True

    def on_phone_toggled(self, on):
        set_phone_enabled(on)
        if on:
            self._start_phone()
        else:
            self.phone_link.stop()
            self.phone_status.clear()
        self._show_phone()

    def on_port_changed(self):
        port = self.port_input.value()
        if port == phone_port():
            return
        set_phone_port(port)
        if phone_enabled():
            self._start_phone()
        self._show_phone()

    def renew_link(self):
        if not ask_yes_no(self, "New Link", "Make a new address for the phone page? The old one stops "
                                            "working, so scan the new code on your phone."):
            return
        try:
            self.phone_link.renew_token()
        except OSError as e:
            self._port_problem(e)
        self._show_phone()

    def _show_provider(self):
        provider = self.provider()
        self.model_input.blockSignals(True)
        self.model_input.clear()
        self.model_input.addItems(PROVIDERS[provider].models)
        self.model_input.setCurrentText(ai_model(provider))
        self.model_input.blockSignals(False)
        self._show_key_status()

    def _show_key_status(self):
        provider = PROVIDERS[self.provider()]
        key = api_key(self.provider())
        if key:
            self.key_status.setText(f"A {provider.name} key ending in …{key[-4:]} is saved. "
                                    "Paste a new one to replace it.")
        else:
            self.key_status.setText(f'No {provider.name} key saved yet. '
                                    f'<a href="{provider.key_page}">Get one here</a>, then paste it above.')
        self.remove_key_btn.setEnabled(bool(key))
        self.test_btn.setEnabled(bool(key))

    def on_provider_changed(self):
        set_ai_provider(self.provider())
        self.status_label.clear()
        self._show_provider()

    def on_model_changed(self, text):
        if text.strip():
            set_ai_model(self.provider(), text)

    def save_key(self):
        key = self.key_input.text().strip()
        if not key:
            show_status(self.status_label, "Paste the key into the field first.", "info")
            return
        try:
            save_api_key(self.provider(), key)
        except KeyringError as e:
            show_status(self.status_label, f"The key couldn't be saved: {e}", "warn", seconds=30)
            return
        self.key_input.clear()
        self._show_key_status()
        self.test_key()

    def remove_key(self):
        name = PROVIDERS[self.provider()].name
        if not ask_yes_no(self, "Remove Key", f"Remove the saved {name} key from this computer?"):
            return
        remove_api_key(self.provider())
        self._show_key_status()
        show_status(self.status_label, f"✓ Removed the {name} key")

    def test_key(self):
        provider, model = self.provider(), self.model_input.currentText().strip()
        key = api_key(provider)
        if not key:
            show_status(self.status_label, "Save a key first.", "info")
            return
        self.test_btn.setEnabled(False)
        show_status(self.status_label, f"Checking the key with {model}…", "info", seconds=300)
        run_in_background(self, lambda: PROVIDERS[provider](key).check(model), self._key_works, self._key_failed)

    def _key_works(self, _):
        self.test_btn.setEnabled(True)
        show_status(self.status_label, f"✓ The key works, and {self.model_input.currentText()} is available.",
                    seconds=30)

    def _key_failed(self, error):
        self.test_btn.setEnabled(True)
        if not isinstance(error, AIError):
            log.error("key test failed", exc_info=error)
            error = f"Something went wrong: {error}"
        show_status(self.status_label, str(error), "warn", seconds=30)
