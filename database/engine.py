import sys
from pathlib import Path
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker
from .models import Base, Currency, PaymentType, CounterpartyCategory

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "expense_tracker.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def seed_initial_data():
    with SessionLocal() as session:
        if not session.scalars(select(Currency)).first():
            session.add_all([
                Currency(code="RON"),
                Currency(code="EUR"),
                Currency(code="USD")
            ])

        if not session.scalars(select(PaymentType)).first():
            session.add_all([
                PaymentType(type="Debit Card"),
                PaymentType(type="Cash"),
                PaymentType(type="Bank Transfer")
            ])

        if not session.scalars(select(CounterpartyCategory)).first():
            session.add_all([
                CounterpartyCategory(name="Supermarket"),
                CounterpartyCategory(name="Restaurant/Cafe"),
                CounterpartyCategory(name="Employer"),
                CounterpartyCategory(name="Person"),
                CounterpartyCategory(name="Online Service"),
            ])

        session.commit()


def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    return SessionLocal()
