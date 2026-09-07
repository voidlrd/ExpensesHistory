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
    def get_all_counterparties(include_hidden=False):
        with get_session() as session:
            stmt = select(Counterparty).order_by(Counterparty.name)
            if not include_hidden:
                stmt = stmt.where(Counterparty.hidden == False)
            return session.scalars(stmt).all()

    @staticmethod
    def set_hidden_status(cp_id, hidden):
        with get_session() as session:
            cp = session.get(Counterparty, cp_id)
            if cp:
                cp.hidden = hidden
                session.commit()

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
    def add_location(cp_id, label):
        with get_session() as session:
            loc = CounterpartyLocation(counterparty_id=cp_id, label=label)
            session.add(loc)
            session.commit()

    @staticmethod
    def remove_location(loc_id):
        from database.models import TransactionRecord
        with get_session() as session:
            loc = session.get(CounterpartyLocation, loc_id)
            if loc:
                in_use = session.scalar(select(TransactionRecord).where(TransactionRecord.location_id == loc_id))
                if in_use:
                    raise ValueError("Cannot delete this location because it is linked to past transactions.")
                
                session.delete(loc)
                session.commit()

    @staticmethod
    def update_counterparty(cp_id, new_name, category_id):
        with get_session() as session:
            cp = session.get(Counterparty, cp_id)
            if cp:
                cp.name = new_name
                cp.category_id = category_id
                session.commit()