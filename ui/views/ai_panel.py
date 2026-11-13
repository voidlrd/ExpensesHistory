from keyring.errors import KeyringError
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
)

from app_logging import log
from app_settings import ai_model, ai_provider, api_key, remove_api_key, save_api_key, set_ai_model, set_ai_provider
from receipt_ai import PROVIDERS, AIError
from ui.widgets import ask_yes_no, run_in_background, show_status

HINT_STYLE = "color: #9E9E9E;"


class AIPanel(QWidget):
    def __init__(self):
        super().__init__()
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
        layout.addStretch()

        self.provider_input.currentIndexChanged.connect(self.on_provider_changed)
        self.key_input.returnPressed.connect(self.save_key)
        self.save_key_btn.clicked.connect(self.save_key)
        self.remove_key_btn.clicked.connect(self.remove_key)
        self.model_input.currentTextChanged.connect(self.on_model_changed)
        self.test_btn.clicked.connect(self.test_key)

    def provider(self):
        return self.provider_input.currentData()

    def load(self):
        self.provider_input.blockSignals(True)
        self.provider_input.setCurrentIndex(self.provider_input.findData(ai_provider()))
        self.provider_input.blockSignals(False)
        self._show_provider()

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
