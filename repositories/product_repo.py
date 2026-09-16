from dataclasses import dataclass, field
from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from database.engine import get_session
from database.models import Counterparty, Item, ItemCategory, Product, ProductBrand, TransactionRecord
from repositories.names import find_by_name
from units import normalize_unit, unit_price_after_discount

@dataclass
class ProductOverview:
    product: Product
    purchases: int = 0
    last_date: date | None = None
    last_store: str | None = None
    last_price: float | None = None
    last_currency: str | None = None
    brands: list = field(default_factory=list)

def get_or_create_category(session, name):
    category = find_by_name(session.scalars(select(ItemCategory)), name)
    if category is None:
        category = ItemCategory(name=name)
        session.add(category)
        session.flush()
    return category

def get_or_create_brand(session, product_id, label):
    """The product's brand with this label, created when it is new; None for a blank label."""
    label = (label or "").strip()
    if not label:
        return None
    existing = session.scalars(select(ProductBrand).where(ProductBrand.product_id == product_id)).all()
    brand = find_by_name(existing, label, attr="label")
    if brand is None:
        brand = ProductBrand(product_id=product_id, label=label)
        session.add(brand)
        session.flush()
    return brand

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
                    entry.last_date = row.date
                    entry.last_store = row.store
                    entry.last_currency = row.currency_code
                    entry.last_price = unit_price_after_discount(row.amount, row.price, row.discount)

            for brand in session.scalars(select(ProductBrand).order_by(ProductBrand.label)):
                entry = overview.get(brand.product_id)
                if entry is not None:
                    entry.brands.append(brand.label)
            return list(overview.values())

    # ---------- brands ----------

    @staticmethod
    def get_brands(product_id):
        with get_session() as session:
            return session.scalars(
                select(ProductBrand)
                .where(ProductBrand.product_id == product_id)
                .order_by(ProductBrand.label)
            ).all()

    @staticmethod
    def add_brand(product_id, label):
        label = (label or "").strip()
        if not label:
            raise ValueError("A brand needs a name.")
        with get_session() as session:
            existing = session.scalars(
                select(ProductBrand).where(ProductBrand.product_id == product_id)
            ).all()
            if find_by_name(existing, label, attr="label"):
                raise ValueError("This product already has that brand.")

            session.add(ProductBrand(product_id=product_id, label=label))
            session.commit()

    @staticmethod
    def rename_brand(brand_id, label):
        """Renaming fixes every past purchase, because they point at this row."""
        label = (label or "").strip()
        if not label:
            raise ValueError("A brand needs a name.")
        with get_session() as session:
            brand = session.get(ProductBrand, brand_id)
            if brand is None:
                raise ValueError("This brand no longer exists.")

            siblings = session.scalars(
                select(ProductBrand)
                .where(ProductBrand.product_id == brand.product_id)
                .where(ProductBrand.id != brand_id)
            ).all()
            if find_by_name(siblings, label, attr="label"):
                raise ValueError("This product already has that brand.")

            brand.label = label
            session.commit()

    @staticmethod
    def brand_usage(brand_id):
        with get_session() as session:
            return session.scalar(select(func.count(Item.id)).where(Item.brand_id == brand_id)) or 0

    @staticmethod
    def remove_brand(brand_id, clear_from_purchases=False):
        """Delete a brand; with clear_from_purchases the lines that used it go back to no brand."""
        with get_session() as session:
            brand = session.get(ProductBrand, brand_id)
            if brand is None:
                return 0

            used = session.scalars(select(Item).where(Item.brand_id == brand_id)).all()
            if used and not clear_from_purchases:
                raise ValueError(f"This brand is on {len(used)} past purchase(s).")

            for line in used:
                line.brand_id = None
            session.flush()
            session.delete(brand)
            session.commit()
            return len(used)

    @staticmethod
    def get_brand_index():
        """{product name casefolded: {"brands": [...], "last": label or None}} for the receipt form."""
        with get_session() as session:
            names = {p.id: p.name for p in session.scalars(select(Product))}
            index = {name.casefold(): {"brands": [], "last": None} for name in names.values()}

            for brand in session.scalars(select(ProductBrand).order_by(ProductBrand.label)):
                entry = index.get(names.get(brand.product_id, "").casefold())
                if entry is not None:
                    entry["brands"].append(brand.label)

            recent = session.execute(
                select(Item.product_id, ProductBrand.label)
                .join(Item.transaction)
                .join(ProductBrand, Item.brand_id == ProductBrand.id)
                .where(Item.refund == False)
                .order_by(TransactionRecord.date.desc(), TransactionRecord.id.desc(), Item.id.desc())
            ).all()
            for product_id, label in recent:
                entry = index.get(names.get(product_id, "").casefold())
                if entry is not None and entry["last"] is None:
                    entry["last"] = label

            return index

    @staticmethod
    def set_hidden(product_ids, hidden):
        with get_session() as session:
            for p in session.scalars(select(Product).where(Product.id.in_(product_ids))):
                p.hidden = hidden
            session.commit()

    @staticmethod
    def set_category(product_ids, category_name):
        with get_session() as session:
            category_id = get_or_create_category(session, category_name).id if category_name else None
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

            kept_brands = {
                brand.label.casefold(): brand
                for brand in session.scalars(
                    select(ProductBrand).where(ProductBrand.product_id == keep_id)
                )
            }
            for brand in session.scalars(
                select(ProductBrand).where(ProductBrand.product_id.in_(other_ids))
            ).all():
                twin = kept_brands.get(brand.label.casefold())
                if twin is None:
                    brand.product_id = keep_id
                    kept_brands[brand.label.casefold()] = brand
                else:
                    # the same brand on both sides: point its purchases at the one we keep
                    for line in session.scalars(select(Item).where(Item.brand_id == brand.id)):
                        line.brand_id = twin.id
                    session.flush()
                    session.delete(brand)
            session.flush()
            for other in others:
                session.expire(other, ["brands"])

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
                    joinedload(Item.product),
                    joinedload(Item.brand)
                )
                .where(Item.product_id == product_id)
                .where(Item.refund == False)
                .order_by(TransactionRecord.date.desc())
            )
            if currency_code:
                stmt = stmt.where(TransactionRecord.currency_code == currency_code)
            return session.scalars(stmt).all()

    @staticmethod
    def update_product(product_id, new_name, unit, category_name=None,
                       package_size=None, package_unit=None):
        with get_session() as session:
            p = session.get(Product, product_id)
            if p:
                clash = find_by_name((o for o in session.scalars(select(Product)) if o.id != product_id), new_name)
                if clash:
                    raise ValueError(f"Another product is already named '{clash.name}'.")

                p.name = new_name
                p.unit_of_measure = normalize_unit(unit)
                if p.unit_of_measure == "pcs" and package_size:
                    p.package_size = package_size
                    p.package_unit = package_unit
                else:
                    p.package_size = None
                    p.package_unit = None

                p.category_id = get_or_create_category(session, category_name).id if category_name else None

                session.commit()
