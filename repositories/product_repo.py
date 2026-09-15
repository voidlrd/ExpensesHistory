from dataclasses import dataclass
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import Counterparty, Item, ItemCategory, Product, TransactionRecord
from units import normalize_unit

@dataclass
class ProductOverview:
    product: Product
    purchases: int = 0
    last_date: date | None = None
    last_store: str | None = None
    last_price: float | None = None
    last_currency: str | None = None

def _get_or_create_category(session, name):
    folded = name.casefold()
    category = next((c for c in session.scalars(select(ItemCategory)) if c.name.casefold() == folded), None)
    if category is None:
        category = ItemCategory(name=name)
        session.add(category)
        session.flush()
    return category

class ProductRepository:
    @staticmethod
    def get_all_products(include_hidden=False):
        with get_session() as session:
            stmt = select(Product).order_by(Product.name)
            if not include_hidden:
                stmt = stmt.where(Product.hidden == False)
            return session.scalars(stmt).all()

    @staticmethod
    def get_product_overview():
        with get_session() as session:
            products = session.scalars(
                select(Product).options(joinedload(Product.category)).order_by(Product.name)
            ).all()
            overview = {p.id: ProductOverview(p) for p in products}

            purchases = session.execute(
                select(Item.product_id, Item.amount, Item.price, Item.discount,
                       TransactionRecord.date, TransactionRecord.currency_code,
                       Counterparty.name.label("store"))
                .join(Item.transaction)
                .join(TransactionRecord.counterparty)
                .where(Item.refund == False)
                .order_by(TransactionRecord.date.desc(), TransactionRecord.id.desc())
            ).all()

            for row in purchases:
                entry = overview.get(row.product_id)
                if entry is None:
                    continue
                entry.purchases += 1
                if entry.last_date is None:
                    amount = float(row.amount)
                    entry.last_date = row.date
                    entry.last_store = row.store
                    entry.last_currency = row.currency_code
                    entry.last_price = (float(row.amount * row.price - row.discount) / amount
                                        if amount > 0 else float(row.price))
            return list(overview.values())

    @staticmethod
    def set_hidden(product_ids, hidden):
        with get_session() as session:
            for p in session.scalars(select(Product).where(Product.id.in_(product_ids))):
                p.hidden = hidden
            session.commit()

    @staticmethod
    def set_category(product_ids, category_name):
        with get_session() as session:
            category_id = _get_or_create_category(session, category_name).id if category_name else None
            for p in session.scalars(select(Product).where(Product.id.in_(product_ids))):
                p.category_id = category_id
            session.commit()

    @staticmethod
    def merge_products(keep_id, other_ids):
        """Move every purchase of other_ids onto keep_id and delete the others; returns lines moved."""
        other_ids = [i for i in other_ids if i != keep_id]
        with get_session() as session:
            keep = session.get(Product, keep_id)
            if keep is None:
                raise ValueError("The product to keep no longer exists.")
            others = session.scalars(select(Product).where(Product.id.in_(other_ids))).all()

            moved = 0
            for item in session.scalars(select(Item).where(Item.product_id.in_(other_ids))):
                item.product_id = keep.id
                moved += 1

            # fill in details the kept product doesn't have yet
            for other in others:
                keep.brand = keep.brand or other.brand
                keep.category_id = keep.category_id or other.category_id
                if keep.package_size is None and other.package_size and \
                        normalize_unit(keep.unit_of_measure) == normalize_unit(other.unit_of_measure) == "pcs":
                    keep.package_size = other.package_size
                    keep.package_unit = other.package_unit

            session.flush()
            for other in others:
                session.delete(other)
            session.commit()
            return moved

    @staticmethod
    def delete_unused_products(product_ids):
        with get_session() as session:
            used = session.scalars(
                select(Product.name).join(Item, Item.product_id == Product.id)
                .where(Product.id.in_(product_ids)).distinct()
            ).all()
            if used:
                raise ValueError(
                    "These products have purchases, so they can't be deleted: " + ", ".join(sorted(used))
                    + ".\n\nMerge them into another product or hide them instead."
                )
            for p in session.scalars(select(Product).where(Product.id.in_(product_ids))):
                session.delete(p)
            session.commit()

    @staticmethod
    def get_product_currencies(product_id: int):
        with get_session() as session:
            stmt = (
                select(TransactionRecord.currency_code)
                .join(Item.transaction)
                .where(Item.product_id == product_id)
                .where(Item.refund == False)
                .distinct()
                .order_by(TransactionRecord.currency_code)
            )
            return list(session.scalars(stmt))

    @staticmethod
    def get_product_price_history(product_id: int, currency_code=None):
        with get_session() as session:
            stmt = (
                select(Item)
                .join(Item.transaction)
                .options(
                    joinedload(Item.transaction).joinedload(TransactionRecord.counterparty),
                    joinedload(Item.product)
                )
                .where(Item.product_id == product_id)
                .where(Item.refund == False)
                .order_by(TransactionRecord.date.desc())
            )
            if currency_code:
                stmt = stmt.where(TransactionRecord.currency_code == currency_code)
            return session.scalars(stmt).all()

    @staticmethod
    def update_product(product_id, new_name, brand, unit, category_name=None,
                       package_size=None, package_unit=None):
        with get_session() as session:
            p = session.get(Product, product_id)
            if p:
                folded_name = new_name.casefold()
                clash = next(
                    (o for o in session.scalars(select(Product))
                     if o.id != product_id and o.name.casefold() == folded_name),
                    None
                )
                if clash:
                    raise ValueError(f"Another product is already named '{clash.name}'.")

                p.name = new_name
                p.brand = brand or None
                p.unit_of_measure = normalize_unit(unit)
                if p.unit_of_measure == "pcs" and package_size:
                    p.package_size = package_size
                    p.package_unit = package_unit
                else:
                    p.package_size = None
                    p.package_unit = None

                p.category_id = _get_or_create_category(session, category_name).id if category_name else None

                session.commit()
