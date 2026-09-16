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
