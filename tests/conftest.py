import json
import os
import tempfile
import time
from pathlib import Path

import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

# point the app at a throwaway database before anything imports the engine
TEST_DB = Path(tempfile.gettempdir()) / "expenses_history_tests.db"
os.environ["EXPENSES_DB"] = str(TEST_DB)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.passwords = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        if self.passwords.pop((service, username), None) is None:
            raise PasswordDeleteError(username)


@pytest.fixture(autouse=True)
def fake_keyring():
    """API keys go to a dict, never to the real Windows Credential Manager."""
    import keyring

    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture(autouse=True)
def scratch_inbox(tmp_path, monkeypatch):
    """Receipts waiting to be read go to a temp folder, never next to the app."""
    import receipt_inbox

    monkeypatch.setattr(receipt_inbox, "INBOX_DIR", tmp_path / "inbox")
    return receipt_inbox.INBOX_DIR


def wait_until(condition, timeout=5):
    """Pump Qt events until condition() holds, so background work can report back."""
    from PyQt6.QtWidgets import QApplication

    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out waiting"
        QApplication.processEvents()
        time.sleep(0.01)


def pump_events(seconds):
    from PyQt6.QtWidgets import QApplication

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)


def png_bytes(width=300, height=400):
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PyQt6.QtGui import QImage

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def filled_products(form):
    from ui.views.new_transaction import COL_PRODUCT
    return [form._cell(r, COL_PRODUCT).currentText() for r in range(form.items_table.rowCount())]


RECEIPT_REPLY = "```json\n" + json.dumps({
    "store": "Lidl", "date": "2026-09-14", "receipt_number": "999 111", "currency": "RON",
    "payment_type": None, "total": 12.49,
    "items": [
        {"name": "Banane", "amount": 1, "unit": "kg", "unit_price": 8.99, "discount": 0, "refund": False},
        {"name": "Paine", "amount": 1, "unit": "pcs", "unit_price": 3.50, "discount": 0, "refund": False},
    ],
    "notes": [],
}) + "\n```"


@pytest.fixture
def asks(monkeypatch):
    """Stands in for the providers: records each request and answers with .reply (or raises .error)."""
    from receipt_ai import Claude, Gemini

    class Asks:
        calls = []
        reply = RECEIPT_REPLY
        error = None
        gate = None

    def ask(self, model, prompt, images):
        Asks.calls.append({"provider": self.name, "model": model, "prompt": prompt, "images": images})
        if Asks.gate:
            Asks.gate.wait(5)
        if Asks.error:
            raise Asks.error
        return Asks.reply

    monkeypatch.setattr(Claude, "ask", ask)
    monkeypatch.setattr(Gemini, "ask", ask)
    return Asks


@pytest.fixture
def form(qt_env):
    from ui.views.new_transaction import NewTransactionView
    return NewTransactionView()


@pytest.fixture
def db():
    from database.engine import engine, init_db, seed_initial_data
    from database.models import Base

    Base.metadata.drop_all(bind=engine)
    init_db()
    seed_initial_data()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def payment_type_id(db):
    from repositories.reference_repo import ReferenceRepository
    return ReferenceRepository.get_all_payment_types()[0].id


def item(name, amount=1, unit="pcs", price="1.00", discount=0, refund=False, category=None,
         override=None, brand=None):
    return {
        "product_name": name,
        "brand": brand,
        "override": override,
        "amount": amount,
        "unit": unit,
        "price": price,
        "discount": discount,
        "refund": refund,
        "category": category,
    }


@pytest.fixture
def save_receipt(payment_type_id):
    from repositories.transaction_repo import TransactionRepository

    def _save(date, store, items, currency="RON", number=None, location_id=None):
        TransactionRepository.save_transaction(
            date, store, number, payment_type_id, currency, items, location_id
        )

    return _save


@pytest.fixture
def save_income(payment_type_id):
    from repositories.income_repo import IncomeRepository

    def _save(date, source, amount, currency="RON"):
        IncomeRepository.save_income(date, source, amount, currency, payment_type_id)

    return _save


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def qt_env(qapp, db, tmp_path, monkeypatch, popups):
    """Qt with a clean database, settings written to a temp folder and a scratch backup folder.

    Depends on popups so no test can open a modal dialog and hang the run.
    """
    from PyQt6.QtCore import QSettings
    from database import backup

    # keep the real remembered window state out of the tests
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "settings"))
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    return qapp


@pytest.fixture
def popups(monkeypatch):
    """Records message boxes instead of showing them; confirmations answer Yes.

    Also cancels input dialogs by default, so an unstubbed one returns instead of
    blocking. A test that needs an answer monkeypatches it again.
    """
    from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

    seen = []

    def record(kind):
        def handler(parent, title, text, *args, **kwargs):
            seen.append((kind, text))
            return QMessageBox.StandardButton.Ok
        return staticmethod(handler)

    monkeypatch.setattr(QMessageBox, "information", record("info"))
    monkeypatch.setattr(QMessageBox, "warning", record("warn"))
    monkeypatch.setattr(QMessageBox, "critical", record("critical"))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([], "")))
    return seen
