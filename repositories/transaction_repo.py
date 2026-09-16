from decimal import ROUND_HALF_UP, Decimal
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import TransactionRecord, Item, Product
from repositories.product_repo import get_or_create_brand, get_or_create_category
from repositories.names import fold_text
from repositories.reference_repo import find_counterparty, get_or_create_counterparty
from units import normalize_unit

CENT = Decimal("0.01")

def line_total(amount, price, discount, refund):
    # receipts round every line to the cent
    total = ((Decimal(str(amount)) * Decimal(str(price))) - Decimal(str(discount))).quantize(CENT, rounding=ROUND_HALF_UP)
    return -total if refund else total

def normalize_receipt_number(number):
    return "".join((number or "").split()).casefold()

def _write_items(session, transaction, items_data):
    products = {p.name.casefold(): p for p in session.scalars(select(Product))}

    for item_data in items_data:
        product_name = item_data["product_name"]
        product = products.get(product_name.casefold())
        unit = item_data.get("unit")
        category = item_data.get("category")

        if not product:
            product = Product(
                name=product_name,
                unit_of_measure=normalize_unit(unit) if unit else None,
                category_id=get_or_create_category(session, category).id if category else None,
            )
            session.add(product)
            session.flush()
            products[product_name.casefold()] = product
        else:
            if unit and product.unit_of_measure != normalize_unit(unit):
                product.unit_of_measure = normalize_unit(unit)
                if product.unit_of_measure != "pcs":
                    product.package_size = None
                    product.package_unit = None
            if category and product.category_id is None:
                product.category_id = get_or_create_category(session, category).id

        brand = get_or_create_brand(session, product.id, item_data.get("brand"))

        session.add(Item(
            transaction_id=transaction.id,
            product_id=product.id,
            item_name_override=item_data["override"],
            brand_id=brand.id if brand else None,
            amount=Decimal(str(item_data["amount"])),
            price=Decimal(str(item_data["price"])),
            discount=Decimal(str(item_data["discount"])),
            refund=item_data["refund"]
        ))


def _total_of(items_data):
    return sum(
        (line_total(i["amount"], i["price"], i["discount"], i["refund"]) for i in items_data),
        Decimal(0)
    )


class TransactionRepository:
    @staticmethod
    def save_transaction(date, counterparty_name, receipt_no, payment_type_id, currency_code, items_data, location_id=None):
        with get_session() as session:
            counterparty = get_or_create_counterparty(session, counterparty_name, "Supermarket")

            transaction = TransactionRecord(
                number=receipt_no,
                payment_type_id=payment_type_id,
                currency_code=currency_code,
                counterparty_id=counterparty.id,
                location_id=location_id,
                date=date,
                total_amount=_total_of(items_data)
            )
            session.add(transaction)
            session.flush()

            _write_items(session, transaction, items_data)
            session.commit()

    @staticmethod
    def update_transaction(tx_id, date, counterparty_name, receipt_no, payment_type_id,
                           currency_code, items_data, location_id=None):
        with get_session() as session:
            transaction = session.get(TransactionRecord, tx_id)
            if not transaction:
                raise ValueError("This transaction no longer exists.")

            counterparty = get_or_create_counterparty(session, counterparty_name, "Supermarket")

            transaction.number = receipt_no
            transaction.payment_type_id = payment_type_id
            transaction.currency_code = currency_code
            transaction.counterparty_id = counterparty.id
            transaction.location_id = location_id
            transaction.date = date
            transaction.total_amount = _total_of(items_data)

            for item in list(transaction.items):
                session.delete(item)
            session.flush()

            _write_items(session, transaction, items_data)
            session.commit()

    @staticmethod
    def search_transactions(start_date=None, end_date=None, counterparty_id=None, currency_code=None, text=""):
        """Filtered receipts, newest first; text matches store, location, receipt ID or any product on it."""
        with get_session() as session:
            stmt = (
                select(TransactionRecord)
                .options(
                    joinedload(TransactionRecord.counterparty),
                    joinedload(TransactionRecord.payment_type),
                    joinedload(TransactionRecord.location),
                    joinedload(TransactionRecord.items).joinedload(Item.product),
                    joinedload(TransactionRecord.items).joinedload(Item.brand)
                )
                .order_by(TransactionRecord.date.desc(), TransactionRecord.id.desc())
            )
            if start_date:
                stmt = stmt.where(TransactionRecord.date >= start_date)
            if end_date:
                stmt = stmt.where(TransactionRecord.date <= end_date)
            if counterparty_id:
                stmt = stmt.where(TransactionRecord.counterparty_id == counterparty_id)
            if currency_code:
                stmt = stmt.where(TransactionRecord.currency_code == currency_code)
            transactions = session.scalars(stmt).unique().all()

        wanted = fold_text((text or "").strip())
        if not wanted:
            return transactions

        def haystack(tx):
            parts = [tx.number, tx.counterparty.name if tx.counterparty else None,
                     tx.location.label if tx.location else None]
            for item in tx.items:
                parts += [item.product.name if item.product else None, item.item_name_override,
                          item.brand.label if item.brand else None]
            return fold_text(" ".join(p for p in parts if p))

        return [tx for tx in transactions if wanted in haystack(tx)]

    @staticmethod
    def get_transaction_with_items(tx_id: int):
        with get_session() as session:
            stmt = select(TransactionRecord).options(
                joinedload(TransactionRecord.counterparty),
                joinedload(TransactionRecord.payment_type),
                joinedload(TransactionRecord.location),
                joinedload(TransactionRecord.items).joinedload(Item.product).joinedload(Product.category),
                joinedload(TransactionRecord.items).joinedload(Item.brand)
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
    def find_by_receipt_number(receipt_number, exclude_id=None):
        wanted = normalize_receipt_number(receipt_number)
        if not wanted:
            return []
        with get_session() as session:
            stmt = (
                select(TransactionRecord)
                .options(joinedload(TransactionRecord.counterparty))
                .where(TransactionRecord.number.is_not(None))
                .order_by(TransactionRecord.date)
            )
            return [t for t in session.scalars(stmt)
                    if t.id != exclude_id and normalize_receipt_number(t.number) == wanted]

    @staticmethod
    def check_potential_duplicate(tx_date, counterparty_name, final_amount, currency_code=None, exclude_id=None):
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
            if exclude_id:
                stmt = stmt.where(TransactionRecord.id != exclude_id)

            return session.scalar(stmt) is not None
