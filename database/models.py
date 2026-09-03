import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Integer, Date, Numeric, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class PaymentType(Base):
    __tablename__ = "payment_type"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

class Currency(Base):
    __tablename__ = "currency"
    code: Mapped[str] = mapped_column(String(3), primary_key=True)

class CounterpartyCategory(Base):
    __tablename__ = "counterparty_category"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
class Counterparty(Base):
    __tablename__ = "counterparty"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    category_id: Mapped[int] = mapped_column("category", ForeignKey("counterparty_category.id"), nullable=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category: Mapped["CounterpartyCategory"] = relationship()
    locations: Mapped[List["CounterpartyLocation"]] = relationship(back_populates="counterparty")

class CounterpartyLocation(Base):
    __tablename__ = "counterparty_location"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    counterparty_id: Mapped[int] = mapped_column(ForeignKey("counterparty.id"), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(100))

    __table_args__ = (UniqueConstraint('counterparty_id', 'label', name='uq_location_counterparty'),)

    counterparty: Mapped["Counterparty"] = relationship(back_populates="locations")

class TransactionRecord(Base):
    __tablename__ = "transaction_record"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    payment_type_id: Mapped[int] = mapped_column("payment_type", ForeignKey("payment_type.id"), nullable=False)
    currency_code: Mapped[str] = mapped_column("currency", ForeignKey("currency.code"), nullable=False)
    counterparty_id: Mapped[int] = mapped_column("counterparty", ForeignKey("counterparty.id"), nullable=False)
    location_id: Mapped[Optional[int]] = mapped_column("location", ForeignKey("counterparty_location.id"))
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    discount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)

    payment_type: Mapped["PaymentType"] = relationship()
    currency: Mapped["Currency"] = relationship()
    counterparty: Mapped["Counterparty"] = relationship()
    location: Mapped[Optional['CounterpartyLocation']] = relationship()
    items: Mapped[List["Item"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")

class ItemCategory(Base):
    __tablename__ = "item_category"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

class Product(Base):
    __tablename__ = "product"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(20))
    category_id: Mapped[Optional[int]] = mapped_column("category", ForeignKey("item_category.id"))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category: Mapped[Optional["ItemCategory"]] = relationship()

class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transaction_record.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    item_name_override: Mapped[Optional[str]] = mapped_column(String(250))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    refund: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    transaction: Mapped["TransactionRecord"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

class IncomeRecord(Base):
    __tablename__ = "income_record"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    counterparty_id: Mapped[int] = mapped_column("counterparty", ForeignKey("counterparty.id"), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column("currency", ForeignKey("currency.code"), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_type_id: Mapped[int] = mapped_column("payment_type", ForeignKey("payment_type.id"), nullable=False)

    counterparty: Mapped["Counterparty"] = relationship()
    currency: Mapped["Currency"] = relationship()
    payment_type: Mapped["PaymentType"] = relationship()