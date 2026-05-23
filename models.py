from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class ThemeEnum(str, enum.Enum):
    dark = "dark"
    light = "light"


class LangEnum(str, enum.Enum):
    ru = "ru"
    en = "en"


class TransactionTypeEnum(str, enum.Enum):
    income = "income"
    expense = "expense"


class GoalStatusEnum(str, enum.Enum):
    active = "active"
    completed = "completed"
    violated = "violated"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    theme = Column(SAEnum(ThemeEnum), default=ThemeEnum.dark, nullable=False)
    language = Column(SAEnum(LangEnum), default=LangEnum.ru, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    debts = relationship("Debt", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    benchmarks = relationship("Benchmark", back_populates="user", cascade="all, delete-orphan")
    category_limits = relationship("CategoryLimit", back_populates="user", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(SAEnum(TransactionTypeEnum), nullable=False)
    category = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="transactions")


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    creditor = Column(String(128), nullable=False)
    amount = Column(Float, nullable=False)
    amount_paid = Column(Float, default=0.0, nullable=False)
    due_date = Column(DateTime, nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="debts")

    @property
    def remaining(self) -> float:
        return round(self.amount - self.amount_paid, 2)


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0, nullable=False)
    deadline = Column(DateTime, nullable=False)
    status = Column(SAEnum(GoalStatusEnum), default=GoalStatusEnum.active, nullable=False)
    penalty_applied = Column(Boolean, default=False, nullable=False)
    penalty_amount = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="goals")

    @property
    def progress_pct(self) -> float:
        if self.target_amount == 0:
            return 0.0
        return round(min(self.current_amount / self.target_amount * 100, 100), 2)


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    metric = Column(String(64), nullable=False)
    target_value = Column(Float, nullable=False)
    current_value = Column(Float, default=0.0, nullable=False)
    period = Column(String(32), nullable=False, default="monthly")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="benchmarks")


class CategoryLimit(Base):
    __tablename__ = "category_limits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(64), nullable=False)
    monthly_limit = Column(Float, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="category_limits")


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    level = Column(String(16), nullable=False, default="INFO")
    event = Column(String(128), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
