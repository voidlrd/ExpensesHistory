import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import (
    Currency, PaymentType, CounterpartyCategory, Counterparty,
    CounterpartyLocation, IncomeRecord, ItemCategory, TransactionRecord
)
from repositories.names import find_by_name

INCOME_CATEGORIES = ("Employer", "Person")
CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

@dataclass
class CounterpartyOverview:
    counterparty: Counterparty
    receipts: int = 0
    incomes: int = 0
    spent: dict = field(default_factory=dict)
    earned: dict = field(default_factory=dict)
    last_date: date | None = None
    locations: int = 0

def find_counterparty(session, name):
    return find_by_name(session.scalars(select(Counterparty)), name)

def get_or_create_counterparty_category(session, name):
    category = find_by_name(session.scalars(select(CounterpartyCategory)), name)
    if category is None:
        category = CounterpartyCategory(name=name)
        session.add(category)
        session.flush()
    return category

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

def _add_total(totals, currency, amount):
    totals[currency] = totals.get(currency, Decimal(0)) + Decimal(str(amount or 0))

class ReferenceRepository:

    @staticmethod
    def get_all_currencies():
        with get_session() as session:
            return session.scalars(select(Currency)).all()

    @staticmethod
    def get_currency_usage():
        """{code: (receipts, income records)} for every currency."""
        with get_session() as session:
            usage = {c.code: [0, 0] for c in session.scalars(select(Currency).order_by(Currency.code))}
            for code, count in session.execute(
                select(TransactionRecord.currency_code, func.count()).group_by(TransactionRecord.currency_code)
            ):
                usage.setdefault(code, [0, 0])[0] = count
            for code, count in session.execute(
                select(IncomeRecord.currency_code, func.count()).group_by(IncomeRecord.currency_code)
            ):
                usage.setdefault(code, [0, 0])[1] = count
            return {code: tuple(counts) for code, counts in usage.items()}

    @staticmethod
    def add_currency(code):
        code = (code or "").strip().upper()
        if not CURRENCY_CODE.match(code):
            raise ValueError("A currency code is three letters, like EUR, HUF or GBP.")
        with get_session() as session:
            if session.get(Currency, code) is not None:
                raise ValueError(f"{code} is already in the list.")
            session.add(Currency(code=code))
            session.commit()
        return code

    @staticmethod
    def remove_currency(code):
        with get_session() as session:
            currency = session.get(Currency, code)
            if currency is None:
                return
            receipts = session.scalar(
                select(func.count()).select_from(TransactionRecord).where(TransactionRecord.currency_code == code))
            incomes = session.scalar(
                select(func.count()).select_from(IncomeRecord).where(IncomeRecord.currency_code == code))
            if receipts or incomes:
                raise ValueError(f"{code} is used by {receipts} receipt(s) and {incomes} income record(s), "
                                 "so it can't be removed.")
            session.delete(currency)
            session.commit()

    @staticmethod
    def get_all_payment_types():
        with get_session() as session:
            return session.scalars(select(PaymentType)).all()

    @staticmethod
    def get_all_counterparty_categories():
        with get_session() as session:
            return session.scalars(select(CounterpartyCategory)).all()

    @staticmethod
    def get_or_create_counterparty_category_id(name):
        """Id of a store category, creating it when the name is new."""
        with get_session() as session:
            category = get_or_create_counterparty_category(session, name)
            session.commit()
            return category.id

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
    def get_income_sources():
        """Employers, people, and anyone who already paid you; for the income form."""
        with get_session() as session:
            paid = select(IncomeRecord.counterparty_id).distinct().scalar_subquery()
            stmt = (
                select(Counterparty)
                .join(Counterparty.category)
                .where(Counterparty.hidden == False)
                .where(or_(CounterpartyCategory.name.in_(INCOME_CATEGORIES), Counterparty.id.in_(paid)))
                .order_by(Counterparty.name)
            )
            return session.scalars(stmt).all()

    @staticmethod
    def get_counterparty_overview():
        """Every store and person with how much was spent there, earned from them, and when."""
        with get_session() as session:
            parties = session.scalars(
                select(Counterparty).options(joinedload(Counterparty.category)).order_by(Counterparty.name)
            ).all()
            overview = {cp.id: CounterpartyOverview(cp) for cp in parties}

            spent = session.execute(
                select(TransactionRecord.counterparty_id, TransactionRecord.currency_code,
                       func.count(TransactionRecord.id), func.sum(TransactionRecord.total_amount),
                       func.max(TransactionRecord.date))
                .group_by(TransactionRecord.counterparty_id, TransactionRecord.currency_code)
            ).all()
            for cp_id, currency, count, total, last_date in spent:
                entry = overview.get(cp_id)
                if entry is None:
                    continue
                entry.receipts += count
                _add_total(entry.spent, currency, total)
                entry.last_date = max(entry.last_date, last_date) if entry.last_date else last_date

            earned = session.execute(
                select(IncomeRecord.counterparty_id, IncomeRecord.currency_code,
                       func.count(IncomeRecord.id), func.sum(IncomeRecord.net_amount),
                       func.max(IncomeRecord.date))
                .group_by(IncomeRecord.counterparty_id, IncomeRecord.currency_code)
            ).all()
            for cp_id, currency, count, total, last_date in earned:
                entry = overview.get(cp_id)
                if entry is None:
                    continue
                entry.incomes += count
                _add_total(entry.earned, currency, total)
                entry.last_date = max(entry.last_date, last_date) if entry.last_date else last_date

            locations = session.execute(
                select(CounterpartyLocation.counterparty_id, func.count(CounterpartyLocation.id))
                .group_by(CounterpartyLocation.counterparty_id)
            ).all()
            for cp_id, count in locations:
                if cp_id in overview:
                    overview[cp_id].locations = count

            return list(overview.values())

    @staticmethod
    def set_hidden_status(cp_id, hidden):
        with get_session() as session:
            cp = session.get(Counterparty, cp_id)
            if cp:
                cp.hidden = hidden
                session.commit()

    @staticmethod
    def set_hidden_for(cp_ids, hidden):
        with get_session() as session:
            for cp in session.scalars(select(Counterparty).where(Counterparty.id.in_(cp_ids))):
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
    def add_location(cp_id, label):
        with get_session() as session:
            existing = session.scalars(
                select(CounterpartyLocation).where(CounterpartyLocation.counterparty_id == cp_id)
            ).all()
            if find_by_name(existing, label, attr="label"):
                raise ValueError("This location already exists for this store.")

            session.add(CounterpartyLocation(counterparty_id=cp_id, label=label))
            session.commit()

    @staticmethod
    def rename_location(loc_id, label):
        label = (label or "").strip()
        if not label:
            raise ValueError("A location needs a name.")
        with get_session() as session:
            loc = session.get(CounterpartyLocation, loc_id)
            if not loc:
                raise ValueError("This location no longer exists.")

            siblings = session.scalars(
                select(CounterpartyLocation)
                .where(CounterpartyLocation.counterparty_id == loc.counterparty_id)
                .where(CounterpartyLocation.id != loc_id)
            ).all()
            if find_by_name(siblings, label, attr="label"):
                raise ValueError("This location already exists for this store.")

            loc.label = label
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

    @staticmethod
    def merge_counterparties(keep_id, other_ids):
        """Move receipts, income and locations onto keep_id and delete the others; returns (receipts, incomes)."""
        other_ids = [i for i in other_ids if i != keep_id]
        if not other_ids:
            return 0, 0

        with get_session() as session:
            keep = session.get(Counterparty, keep_id)
            if keep is None:
                raise ValueError("The store to keep no longer exists.")
            others = session.scalars(select(Counterparty).where(Counterparty.id.in_(other_ids))).all()

            kept_locations = {
                (loc.label or "").casefold(): loc
                for loc in session.scalars(
                    select(CounterpartyLocation).where(CounterpartyLocation.counterparty_id == keep_id)
                )
            }
            for loc in session.scalars(
                select(CounterpartyLocation).where(CounterpartyLocation.counterparty_id.in_(other_ids))
            ).all():
                twin = kept_locations.get((loc.label or "").casefold())
                if twin is None:
                    loc.counterparty_id = keep_id
                    kept_locations[(loc.label or "").casefold()] = loc
                else:
                    # same branch name on both sides: point its receipts at the one we keep
                    for tx in session.scalars(
                        select(TransactionRecord).where(TransactionRecord.location_id == loc.id)
                    ):
                        tx.location_id = twin.id
                    session.flush()
                    session.delete(loc)

            receipts = 0
            for tx in session.scalars(
                select(TransactionRecord).where(TransactionRecord.counterparty_id.in_(other_ids))
            ):
                tx.counterparty_id = keep_id
                receipts += 1

            incomes = 0
            for inc in session.scalars(
                select(IncomeRecord).where(IncomeRecord.counterparty_id.in_(other_ids))
            ):
                inc.counterparty_id = keep_id
                incomes += 1

            session.flush()
            for other in others:
                session.delete(other)
            session.commit()
            return receipts, incomes

    @staticmethod
    def delete_counterparties(cp_ids):
        with get_session() as session:
            used = list(session.scalars(
                select(Counterparty.name)
                .join(TransactionRecord, TransactionRecord.counterparty_id == Counterparty.id)
                .where(Counterparty.id.in_(cp_ids)).distinct()
            )) + list(session.scalars(
                select(Counterparty.name)
                .join(IncomeRecord, IncomeRecord.counterparty_id == Counterparty.id)
                .where(Counterparty.id.in_(cp_ids)).distinct()
            ))
            if used:
                raise ValueError(
                    "These have receipts or income, so they can't be deleted: " + ", ".join(sorted(set(used)))
                    + ".\n\nMerge them into another one or hide them instead."
                )

            for cp in session.scalars(select(Counterparty).where(Counterparty.id.in_(cp_ids))):
                for loc in list(cp.locations):
                    session.delete(loc)
                session.delete(cp)
            session.commit()
