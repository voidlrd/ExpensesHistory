from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import IncomeRecord
from repositories.reference_repo import get_or_create_counterparty

class IncomeRepository:
    @staticmethod
    def save_income(date, counterparty_name, net_amount, currency_code, payment_type_id):
        with get_session() as session:
            counterparty = get_or_create_counterparty(session, counterparty_name, "Employer")

            income = IncomeRecord(
                counterparty_id=counterparty.id,
                date=date,
                currency_code=currency_code,
                net_amount=Decimal(str(net_amount)),
                payment_type_id=payment_type_id
            )
            session.add(income)
            session.commit()

    @staticmethod
    def get_all_incomes(start_date=None, end_date=None, counterparty_id=None, currency_code=None):
        with get_session() as session:
            stmt = select(IncomeRecord).options(
                joinedload(IncomeRecord.counterparty),
                joinedload(IncomeRecord.payment_type)
            )

            if start_date:
                stmt = stmt.where(IncomeRecord.date >= start_date)
            if end_date:
                stmt = stmt.where(IncomeRecord.date <= end_date)
            if counterparty_id:
                stmt = stmt.where(IncomeRecord.counterparty_id == counterparty_id)
            if currency_code:
                stmt = stmt.where(IncomeRecord.currency_code == currency_code)

            stmt = stmt.order_by(IncomeRecord.date.desc())
            return session.scalars(stmt).unique().all()

    @staticmethod
    def get_income(income_id):
        with get_session() as session:
            stmt = select(IncomeRecord).options(
                joinedload(IncomeRecord.counterparty),
                joinedload(IncomeRecord.payment_type)
            ).where(IncomeRecord.id == income_id)
            return session.scalar(stmt)

    @staticmethod
    def update_income(income_id, date, counterparty_name, net_amount, currency_code, payment_type_id):
        with get_session() as session:
            income = session.get(IncomeRecord, income_id)
            if not income:
                raise ValueError("This income record no longer exists.")

            counterparty = get_or_create_counterparty(session, counterparty_name, "Employer")

            income.counterparty_id = counterparty.id
            income.date = date
            income.currency_code = currency_code
            income.net_amount = Decimal(str(net_amount))
            income.payment_type_id = payment_type_id
            session.commit()

    @staticmethod
    def delete_income(income_id):
        with get_session() as session:
            inc = session.get(IncomeRecord, income_id)
            if inc:
                session.delete(inc)
                session.commit()

    @staticmethod
    def get_last_used_defaults():
        with get_session() as session:
            last_inc = session.scalar(
                select(IncomeRecord).order_by(IncomeRecord.date.desc(), IncomeRecord.id.desc())
            )
            if last_inc:
                return last_inc.payment_type_id, last_inc.currency_code
            return None, None