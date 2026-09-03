from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from .models import Base, Currency, PaymentType, CounterpartyCategory

DATABASE_URL = "sqlite:///expense_tracker.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

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