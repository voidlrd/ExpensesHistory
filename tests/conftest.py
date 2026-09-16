import os
import tempfile
from pathlib import Path

import pytest

# point the app at a throwaway database before anything imports the engine
TEST_DB = Path(tempfile.gettempdir()) / "expenses_history_tests.db"
os.environ["EXPENSES_DB"] = str(TEST_DB)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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


def item(name, amount=1, unit="pcs", price="1.00", discount=0, refund=False, category=None, override=None):
    return {
        "product_name": name,
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
    from PyQt6.QtWidgets import QInputDialog, QMessageBox

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
    return seen
