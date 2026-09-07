import calendar
from datetime import date
from sqlalchemy import select, func, desc, case
from database.engine import get_session
from database.models import TransactionRecord, IncomeRecord, Counterparty, ItemCategory, Item, Product

class ReportsRepository:

    @staticmethod
    def _get_month_bounds(year=None, month=None):
        today = date.today()
        y = year or today.year
        m = month or today.month

        _, last_day = calendar.monthrange(y, m)
        return date(y, m, 1), date(y, m, last_day)

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

            min_year = min(d.year for d in dates)
            max_year = max(d.year for d in dates)

            min_year = min(min_year, curr_year)
            max_year = max(max_year, curr_year)

            return list(range(min_year, max_year + 1))

    @staticmethod
    def get_month_summary(currency_code, year=None, month=None):
        start_date, end_date = ReportsRepository._get_month_bounds(year, month)

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
    def get_expenses_by_counterparty(currency_code, year=None, month=None):
        start_date, end_date = ReportsRepository._get_month_bounds(year, month)

        with get_session() as session:
            stmt = (
                select(Counterparty.name, func.sum(TransactionRecord.total_amount).label("total"))
                .join(TransactionRecord.counterparty)
                .where(TransactionRecord.date >= start_date)
                .where(TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
                .group_by(Counterparty.name)
                .order_by(desc("total"))
            )
            results = session.execute(stmt).all()
            return [(row.name, float(row.total)) for row in results]

    @staticmethod
    def get_expenses_by_category(currency_code, year=None, month=None):
        start_date, end_date = ReportsRepository._get_month_bounds(year, month)

        with get_session() as session:
            row_total = case(
                (Item.refund == True, -((Item.amount * Item.price) - Item.discount)),
                else_=((Item.amount * Item.price) - Item.discount)
            )

            stmt = (
                select(ItemCategory.name, func.sum(row_total).label("total"))
                .select_from(Item)
                .join(Item.transaction)
                .join(Item.product)
                .outerjoin(Product.category)
                .where(TransactionRecord.date >= start_date)
                .where(TransactionRecord.date <= end_date)
                .where(TransactionRecord.currency_code == currency_code)
                .group_by(ItemCategory.name)
                .order_by(desc("total"))
            )
            results = session.execute(stmt).all()
            return [(row.name or "Uncategorized", float(row.total)) for row in results]