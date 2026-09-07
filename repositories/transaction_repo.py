from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import TransactionRecord, Item, Counterparty, Product, CounterpartyCategory

class TransactionRepository:
    @staticmethod
    def save_transaction(date, counterparty_name, receipt_no, payment_type_id, currency_code, items_data, location_id=None):
        with get_session() as session:
            counterparty = session.scalar(
                select(Counterparty).where(func.lower(Counterparty.name) == counterparty_name.lower())
            )
            if not counterparty:
                cat = session.scalar(select(CounterpartyCategory).where(CounterpartyCategory.name == "Supermarket"))
                if not cat:
                    cat = CounterpartyCategory(name="Supermarket")
                    session.add(cat)
                    session.flush()

                counterparty = Counterparty(name=counterparty_name, category_id=cat.id)
                session.add(counterparty)
                session.flush()

            gross_amount = Decimal(0.0)
            for item in items_data:
                line_total = Decimal(str(item["amount"])) * Decimal(str(item["price"])) - Decimal(str(item["discount"]))
                if item["refund"]:
                    gross_amount -= line_total
                else:
                    gross_amount += line_total
            final_amount = gross_amount

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

            for item_data in items_data:
                product_name = item_data["product_name"]
                product = session.scalar(select(Product).where(func.lower(Product.name) == product_name.lower()))

                if not product:
                    product = Product(name=product_name)
                    session.add(product)
                    session.flush()

                new_item = Item(
                    transaction_id=transaction.id,
                    product_id=product.id,
                    item_name_override=item_data["override"],
                    amount=Decimal(str(item_data["amount"])),
                    price=Decimal(str(item_data["price"])),
                    discount=Decimal(str(item_data["discount"])),
                    refund=item_data["refund"]
                )
                session.add(new_item)

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
    def check_potential_duplicate(tx_date, counterparty_name, final_amount):
        with get_session() as session:
            final_dec = Decimal(str(final_amount))

            stmt = (
                select(TransactionRecord)
                .join(TransactionRecord.counterparty)
                .where(TransactionRecord.date == tx_date)
                .where(TransactionRecord.total_amount == final_dec)
                .where(func.lower(Counterparty.name) == counterparty_name.lower())
            )

            return session.scalar(stmt) is not None