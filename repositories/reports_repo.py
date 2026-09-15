import calendar
from datetime import date
from sqlalchemy import select, func, desc, case
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import TransactionRecord, IncomeRecord, Counterparty, ItemCategory, Item, Product

UNCATEGORIZED = "Uncategorized"

def month_bounds(year, month):
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last_day)

def shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1

class ReportsRepository:

    @staticmethod
    def get_available_years():
        with get_session() as session:
            min_tx = session.scalar(select(func.min(TransactionRecord.date)))
            max_tx = session.scalar(select(func.max(TransactionRecord.date)))
            min_inc = session.scalar(select(func.min(IncomeRecord.date)))
            max_inc = session.scalar(select(func.max(IncomeRecord.date)))

            dates = [d for d in [min_tx, max_tx, min_inc, max_inc] if d is not None]

            curr_year = date.today().year

            if not dates:
                return [curr_year]

            min_year = min(min(d.year for d in dates), curr_year)
            max_year = max(max(d.year for d in dates), curr_year)
            return list(range(min_year, max_year + 1))

    @staticmethod
    def get_month_summary(currency_code, year, month):
        start_date, end_date = month_bounds(year, month)

        with get_session() as session:
            expenses = session.scalar(
                select(func.sum(TransactionRecord.total_amount))
                .where(TransactionRecord.date >= start_date)
                .where(TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
            ) or 0.0

            income = session.scalar(
                select(func.sum(IncomeRecord.net_amount))
                .where(IncomeRecord.date >= start_date)
                .where(IncomeRecord.date <= end_date)
                .where(IncomeRecord.currency_code == currency_code)
            ) or 0.0

            return float(income), float(expenses)

    @staticmethod
    def get_monthly_totals(currency_code, year, month, months=12):
        """(year, month, income, expenses) for the months ending at year/month, oldest first."""
        periods = [shift_month(year, month, -offset) for offset in range(months - 1, -1, -1)]
        start_date = month_bounds(*periods[0])[0]
        end_date = month_bounds(year, month)[1]

        with get_session() as session:
            tx_month = func.strftime("%Y-%m", TransactionRecord.date)
            expenses = dict(session.execute(
                select(tx_month, func.sum(TransactionRecord.total_amount))
                .where(TransactionRecord.date >= start_date, TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
                .group_by(tx_month)
            ).all())

            income_month = func.strftime("%Y-%m", IncomeRecord.date)
            income = dict(session.execute(
                select(income_month, func.sum(IncomeRecord.net_amount))
                .where(IncomeRecord.date >= start_date, IncomeRecord.date <= end_date)
                .where(IncomeRecord.currency_code == currency_code)
                .group_by(income_month)
            ).all())

        return [(y, m, float(income.get(f"{y:04d}-{m:02d}") or 0), float(expenses.get(f"{y:04d}-{m:02d}") or 0))
                for y, m in periods]

    @staticmethod
    def get_store_breakdown(currency_code, year, month):
        """(counterparty id, name, total) for the month, biggest first."""
        start_date, end_date = month_bounds(year, month)

        with get_session() as session:
            stmt = (
                select(Counterparty.id, Counterparty.name, func.sum(TransactionRecord.total_amount).label("total"))
                .select_from(TransactionRecord)
                .join(TransactionRecord.counterparty)
                .where(TransactionRecord.date >= start_date)
                .where(TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
                .group_by(Counterparty.id, Counterparty.name)
                .order_by(desc("total"))
            )
            return [(row.id, row.name, float(row.total)) for row in session.execute(stmt)]

    @staticmethod
    def get_category_breakdown(currency_code, year, month):
        """(category id or None, name, total) for the month, biggest first."""
        start_date, end_date = month_bounds(year, month)

        with get_session() as session:
            # round each line to the cent, like the receipt and the saved totals
            line = func.round((Item.amount * Item.price) - Item.discount, 2)
            row_total = case((Item.refund == True, -line), else_=line)

            stmt = (
                select(ItemCategory.id, ItemCategory.name, func.sum(row_total).label("total"))
                .select_from(Item)
                .join(Item.transaction)
                .join(Item.product)
                .outerjoin(Product.category)
                .where(TransactionRecord.date >= start_date)
                .where(TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
                .group_by(ItemCategory.id, ItemCategory.name)
                .order_by(desc("total"))
            )
            return [(row.id, row.name or UNCATEGORIZED, float(row.total)) for row in session.execute(stmt)]

    @staticmethod
    def get_month_lines(currency_code, year, month, store_id=None, category_id=None, uncategorized=False):
        """Receipt lines of the month, optionally for one store or category, oldest first."""
        start_date, end_date = month_bounds(year, month)

        with get_session() as session:
            stmt = (
                select(Item)
                .join(Item.transaction)
                .join(Item.product)
                .options(
                    joinedload(Item.transaction).joinedload(TransactionRecord.counterparty),
                    joinedload(Item.product)
                )
                .where(TransactionRecord.date >= start_date)
                .where(TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
                .order_by(TransactionRecord.date, TransactionRecord.id, Item.id)
            )
            if store_id is not None:
                stmt = stmt.where(TransactionRecord.counterparty_id == store_id)
            if uncategorized:
                stmt = stmt.where(Product.category_id.is_(None))
            elif category_id is not None:
                stmt = stmt.where(Product.category_id == category_id)
            return session.scalars(stmt).all()
