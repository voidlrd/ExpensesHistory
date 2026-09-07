from sqlalchemy import select
from database.engine import get_session
from database.models import (
    Currency, PaymentType, CounterpartyCategory, Counterparty,
    CounterpartyLocation, ItemCategory, TransactionRecord
)

def find_counterparty(session, name):
    if not name:
        return None
    folded = name.casefold()
    return next(
        (cp for cp in session.scalars(select(Counterparty)) if cp.name.casefold() == folded),
        None
    )

def get_or_create_counterparty(session, name, default_category):
    cp = find_counterparty(session, name)
    if cp:
        return cp

    cat = session.scalar(select(CounterpartyCategory).where(CounterpartyCategory.name == default_category))
    if not cat:
        cat = CounterpartyCategory(name=default_category)
        session.add(cat)
        session.flush()

    cp = Counterparty(name=name, category_id=cat.id)
    session.add(cp)
    session.flush()
    return cp

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
            cp = find_counterparty(session, name)
            if not cp:
                return []
            return session.scalars(
                select(CounterpartyLocation)
                .where(CounterpartyLocation.counterparty_id == cp.id)
                .order_by(CounterpartyLocation.label)
            ).all()

    @staticmethod
    def get_locations_for_counterparty_id(cp_id: int):
        with get_session() as session:
            return session.scalars(
                select(CounterpartyLocation)
                .where(CounterpartyLocation.counterparty_id == cp_id)
                .order_by(CounterpartyLocation.label)
            ).all()

    @staticmethod
    def add_location(cp_id, label):
        with get_session() as session:
            existing = session.scalars(
                select(CounterpartyLocation).where(CounterpartyLocation.counterparty_id == cp_id)
            ).all()
            folded = label.casefold()
            if any((loc.label or "").casefold() == folded for loc in existing):
                raise ValueError("This location already exists for this store.")

            session.add(CounterpartyLocation(counterparty_id=cp_id, label=label))
            session.commit()

    @staticmethod
    def remove_location(loc_id):
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
            if not cp:
                return

            clash = find_counterparty(session, new_name)
            if clash and clash.id != cp_id:
                raise ValueError(f"Another store or person is already named '{clash.name}'.")

            cp.name = new_name
            cp.category_id = category_id
            session.commit()
