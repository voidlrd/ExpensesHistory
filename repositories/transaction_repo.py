from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import TransactionRecord, Item, Product
from repositories.reference_repo import find_counterparty, get_or_create_counterparty

def line_total(amount, price, discount, refund):
    total = (Decimal(str(amount)) * Decimal(str(price))) - Decimal(str(discount))
    return -total if refund else total

class TransactionRepository:
    @staticmethod
    def save_transaction(date, counterparty_name, receipt_no, payment_type_id, currency_code, items_data, location_id=None):
        with get_session() as session:
            counterparty = get_or_create_counterparty(session, counterparty_name, "Supermarket")

            final_amount = sum(
                (line_total(i["amount"], i["price"], i["discount"], i["refund"]) for i in items_data),
                Decimal(0)
            )

            transaction = TransactionRecord(
                number=receipt_no,
                payment_type_id=payment_type_id,
                currency_code=currency_code,
                counterparty_id=counterparty.id,
                location_id=location_id,
                date=date,
                total_amount=final_amount
            )
            session.add(transaction)
            session.flush()

            products = {p.name.casefold(): p for p in session.scalars(select(Product))}

            for item_data in items_data:
                product_name = item_data["product_name"]
                product = products.get(product_name.casefold())

                if not product:
                    product = Product(name=product_name)
                    session.add(product)
                    session.flush()
                    products[product_name.casefold()] = product

                session.add(Item(
                    transaction_id=transaction.id,
                    product_id=product.id,
                    item_name_override=item_data["override"],
                    amount=Decimal(str(item_data["amount"])),
                    price=Decimal(str(item_data["price"])),
                    discount=Decimal(str(item_data["discount"])),
                    refund=item_data["refund"]
                ))

            session.commit()

    @staticmethod
    def get_all_transactions(start_date=None, end_date=None, counterparty_id=None, currency_code=None):
        with get_session() as session:
            stmt = (
                select(TransactionRecord)
                .options(
                    joinedload(TransactionRecord.counterparty),
                    joinedload(TransactionRecord.payment_type),
                    joinedload(TransactionRecord.location)
                )
            )

            if start_date:
                stmt = stmt.where(TransactionRecord.date >= start_date)
            if end_date:
                stmt = stmt.where(TransactionRecord.date <= end_date)
            if counterparty_id:
                stmt = stmt.where(TransactionRecord.counterparty_id == counterparty_id)
            if currency_code:
                stmt = stmt.where(TransactionRecord.currency_code == currency_code)

            stmt = stmt.order_by(TransactionRecord.date.desc())
            return session.scalars(stmt).unique().all()

    @staticmethod
    def get_transaction_with_items(tx_id: int):
        with get_session() as session:
            stmt = select(TransactionRecord).options(
                joinedload(TransactionRecord.counterparty),
                joinedload(TransactionRecord.payment_type),
                joinedload(TransactionRecord.location),
                joinedload(TransactionRecord.items).joinedload(Item.product).joinedload(Product.category)
            ).where(TransactionRecord.id == tx_id)
            return session.scalar(stmt)

    @staticmethod
    def delete_transaction(tx_id):
        with get_session() as session:
            tx = session.get(TransactionRecord, tx_id)
            if tx:
                session.delete(tx)
                session.commit()

    @staticmethod
    def get_last_used_defaults():
        with get_session() as session:
            last_tx = session.scalar(
                select(TransactionRecord).order_by(TransactionRecord.date.desc(), TransactionRecord.id.desc())
            )
            if last_tx:
                return last_tx.payment_type_id, last_tx.currency_code
            return None, None

    @staticmethod
    def check_potential_duplicate(tx_date, counterparty_name, final_amount, currency_code=None):
        with get_session() as session:
            counterparty = find_counterparty(session, counterparty_name)
            if not counterparty:
                return False

            stmt = (
                select(TransactionRecord)
                .where(TransactionRecord.date == tx_date)
                .where(TransactionRecord.total_amount == Decimal(str(final_amount)))
                .where(TransactionRecord.counterparty_id == counterparty.id)
            )
            if currency_code:
                stmt = stmt.where(TransactionRecord.currency_code == currency_code)

            return session.scalar(stmt) is not None
