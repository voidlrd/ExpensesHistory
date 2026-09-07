from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import Product, Item, TransactionRecord, ItemCategory

class ProductRepository:
    @staticmethod
    def get_all_products(include_hidden=False):
        with get_session() as session:
            stmt = select(Product).order_by(Product.name)
            if not include_hidden:
                stmt = stmt.where(Product.hidden == False)
            return session.scalars(stmt).all()

    @staticmethod
    def set_hidden_status(product_id, hidden):
        with get_session() as session:
            p = session.get(Product, product_id)
            if p:
                p.hidden = hidden
                session.commit()

    @staticmethod
    def get_product_price_history(product_id: int):
        with get_session() as session:
            stmt = (
                select(Item)
                .join(Item.transaction)
                .options(
                    joinedload(Item.transaction).joinedload(TransactionRecord.counterparty),
                    joinedload(Item.product)
                )
                .where(Item.product_id == product_id)
                .order_by(TransactionRecord.date.desc())
            )
            return session.scalars(stmt).all()

    @staticmethod
    def update_product(product_id, new_name, brand, unit, category_name=None):
        with get_session() as session:
            p = session.get(Product, product_id)
            if p:
                p.name = new_name
                p.brand = brand or None
                p.unit_of_measure = unit or None

                if category_name:
                    cat = session.scalar(select(ItemCategory).where(func.lower(ItemCategory.name) == category_name.lower()))
                    if not cat:
                        cat = ItemCategory(name=category_name)
                        session.add(cat)
                        session.flush()
                    p.category_id = cat.id
                else:
                    p.category_id = None

                session.commit()