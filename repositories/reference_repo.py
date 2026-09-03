from sqlalchemy import select
from database.engine import get_session
from database.models import Currency, PaymentType, CounterpartyCategory, Counterparty, CounterpartyLocation, ItemCategory

class ReferenceRepository:

    @staticmethod
    def get_all_currencies():
        with get_session() as session:
            return session.scalars(select(Currency)).all()

    @staticmethod
    def get_all_payment_types():
        with get_session() as session:
            return session.scalars(select(PaymentType)).all()

    @staticmethod
    def get_all_counterparty_categories():
        with get_session() as session:
            return session.scalars(select(CounterpartyCategory)).all()

    @staticmethod
    def get_all_item_categories():
        with get_session() as session:
            return session.scalars(select(ItemCategory).order_by(ItemCategory.name)).all()

    @staticmethod
    def get_all_counterparties():
        with get_session() as session:
            return session.scalars(select(Counterparty)).all()

    @staticmethod
    def get_locations_for_counterparty(name: str):
        with get_session() as session:
            cp = session.scalar(select(Counterparty).where(Counterparty.name == name))
            if cp:
                return session.scalars(
                    select(CounterpartyLocation).where(CounterpartyLocation.counterparty_id == cp.id)
                ).all()
            return []

    @staticmethod
    def update_counterparty(cp_id, new_name, category_id):
        with get_session() as session:
            cp = session.get(Counterparty, cp_id)
            if cp:
                cp.name = new_name
                cp.category_id = category_id
                session.commit()