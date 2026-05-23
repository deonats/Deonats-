from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import enum, os

# ── База данных ──────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./deonats.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Модели ───────────────────────────────────────────────────────────────────
class TransactionTypeEnum(str, enum.Enum):
    income = "income"
    expense = "expense"

class GoalStatusEnum(str, enum.Enum):
    active = "active"
    completed = "completed"
    violated = "violated"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True)
    password_hash = Column(String(256))
    failed_attempts = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    amount = Column(Float)
    type = Column(SAEnum(TransactionTypeEnum))
    category = Column(String(64))
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    name = Column(String(128))
    target_amount = Column(Float)
    current_amount = Column(Float, default=0.0)
    deadline = Column(DateTime)
    status = Column(SAEnum(GoalStatusEnum), default=GoalStatusEnum.active)
    penalty_applied = Column(Boolean, default=False)
    penalty_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Debt(Base):
    __tablename__ = "debts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    creditor = Column(String(128))
    amount = Column(Float)
    amount_paid = Column(Float, default=0.0)
    is_closed = Column(Boolean, default=False)

class CategoryLimit(Base):
    __tablename__ = "category_limits"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    category = Column(String(64))
    monthly_limit = Column(Float)
    is_blocked = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# ── Роутер ───────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/v1")

class AuthRequest(BaseModel):
    username: str
    password: str

class AddTransactionRequest(BaseModel):
    user_id: int
    amount: float = Field(..., gt=0)
    type: TransactionTypeEnum
    category: str
    description: Optional[str] = None

class GoalAddRequest(BaseModel):
    user_id: int
    name: str
    amount: float = Field(..., gt=0)
    deadline: datetime

class RepayDebtRequest(BaseModel):
    user_id: int
    debt_id: int
    amount: float = Field(..., gt=0)

@router.post("/auth/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="USER NOT FOUND")
    if user.is_locked:
        raise HTTPException(status_code=403, detail="KERNEL PANIC: ACCOUNT LOCKED")
    if user.password_hash != req.password:
        user.failed_attempts += 1
        if user.failed_attempts >= 3:
            user.is_locked = True
            db.commit()
            raise HTTPException(status_code=403, detail="KERNEL PANIC: ACCOUNT LOCKED AFTER 3 ATTEMPTS")
        db.commit()
        remaining = 3 - user.failed_attempts
        raise HTTPException(status_code=401, detail=f"WRONG PASSWORD — {remaining} ATTEMPTS LEFT")
    user.failed_attempts = 0
    db.commit()
    return {"status": "AUTH_OK", "user_id": user.id, "username": user.username}

@router.post("/transaction/add")
def add_transaction(req: AddTransactionRequest, db: Session = Depends(get_db)):
    if req.type == TransactionTypeEnum.expense:
        lim = db.query(CategoryLimit).filter(CategoryLimit.user_id == req.user_id, CategoryLimit.category == req.category).first()
        if lim:
            if lim.is_blocked:
                return {"status": "BLOCKED", "message": f"KERNEL PANIC: '{req.category.upper()}' IS BLOCKED"}
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0)
            spent = sum(t.amount for t in db.query(Transaction).filter(Transaction.user_id == req.user_id, Transaction.category == req.category, Transaction.created_at >= month_start).all())
            if spent + req.amount >= lim.monthly_limit:
                lim.is_blocked = True
                db.commit()
                return {"status": "BLOCKED", "message": f"KERNEL PANIC: '{req.category.upper()}' LIMIT EXCEEDED — LOCKED"}
    tx = Transaction(user_id=req.user_id, amount=req.amount, type=req.type, category=req.category, description=req.description)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return {"status": "OK", "transaction_id": tx.id, "message": f"TX #{tx.id} COMMITTED"}

@router.get("/status/{user_id}")
def check_status(user_id: int, db: Session = Depends(get_db)):
    limits = db.query(CategoryLimit).filter(CategoryLimit.user_id == user_id).all()
    return {"kernel_panic": any(l.is_blocked for l in limits), "categories": [{"category": l.category, "limit": l.monthly_limit, "blocked": l.is_blocked} for l in limits]}

@router.post("/goal/add")
def goal_add(req: GoalAddRequest, db: Session = Depends(get_db)):
    goal = Goal(user_id=req.user_id, name=req.name, target_amount=req.amount, deadline=req.deadline)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {"status": "GOAL_CREATED", "goal_id": goal.id, "message": f"GOAL '{goal.name.upper()}' INITIALIZED"}

@router.get("/goal/status/{user_id}")
def goal_status(user_id: int, db: Session = Depends(get_db)):
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    return {"goals": [{"id": g.id, "name": g.name, "target_amount": g.target_amount, "current_amount": g.current_amount, "status": g.status} for g in goals]}

@router.post("/debt/repay")
def repay_debt(req: RepayDebtRequest, db: Session = Depends(get_db)):
    debt = db.query(Debt).filter(Debt.id == req.debt_id, Debt.user_id == req.user_id).first()
    if not debt:
        raise HTTPException(status_code=404, detail="DEBT NOT FOUND")
    debt.amount_paid = round(debt.amount_paid + req.amount, 2)
    if debt.amount_paid >= debt.amount:
        debt.is_closed = True
        db.commit()
        return {"status": "DEBT_CLOSED", "message": "DEBT FULLY SETTLED"}
    db.commit()
    return {"status": "PARTIAL", "remaining": round(debt.amount - debt.amount_paid, 2)}
