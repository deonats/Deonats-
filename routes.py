from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db_session import get_db
from models import Transaction, Debt, Goal, User
from models import TransactionTypeEnum, GoalStatusEnum
from kernel_panic import check_and_block, get_system_status
from penalty import deposit_to_goal, withdraw_from_goal
from security import authenticate

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

class RepayDebtRequest(BaseModel):
    user_id: int
    debt_id: int
    amount: float = Field(..., gt=0)

class GoalAddRequest(BaseModel):
    user_id: int
    name: str
    amount: float = Field(..., gt=0)
    deadline: datetime

class GoalDepositRequest(BaseModel):
    user_id: int
    goal_id: int
    amount: float = Field(..., gt=0)

class GoalWithdrawRequest(BaseModel):
    user_id: int
    goal_id: int
    amount: float = Field(..., gt=0)

@router.post("/auth/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    user = authenticate(db, req.username, req.password)
    return {"status": "AUTH_OK", "user_id": user.id, "username": user.username}

@router.post("/transaction/add")
def add_transaction(req: AddTransactionRequest, db: Session = Depends(get_db)):
    if req.type == TransactionTypeEnum.expense:
        kernel = check_and_block(db, req.user_id, req.category, req.amount)
        if not kernel["allowed"]:
            return {"status": "BLOCKED", "message": kernel["message"]}
    tx = Transaction(user_id=req.user_id, amount=req.amount, type=req.type, category=req.category, description=req.description)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return {"status": "OK", "transaction_id": tx.id, "message": f"TX #{tx.id} COMMITTED"}

@router.get("/status/{user_id}")
def check_status(user_id: int, db: Session = Depends(get_db)):
    return get_system_status(db, user_id)

@router.post("/debt/repay")
def repay_debt(req: RepayDebtRequest, db: Session = Depends(get_db)):
    debt = db.query(Debt).filter(Debt.id == req.debt_id, Debt.user_id == req.user_id).first()
    if not debt:
        raise HTTPException(status_code=404, detail="DEBT NOT FOUND")
    debt.amount_paid = round(debt.amount_paid + req.amount, 2)
    if debt.amount_paid >= debt.amount:
        debt.is_closed = True
        db.commit()
        return {"status": "DEBT_CLOSED", "message": f"DEBT TO '{debt.creditor.upper()}' SETTLED"}
    db.commit()
    return {"status": "PARTIAL", "remaining": debt.remaining, "message": f"REMAINING: {debt.remaining}"}

@router.post("/goal/add")
def goal_add(req: GoalAddRequest, db: Session = Depends(get_db)):
    goal = Goal(user_id=req.user_id, name=req.name, target_amount=req.amount, deadline=req.deadline)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {"status": "GOAL_CREATED", "goal_id": goal.id, "message": f"GOAL '{goal.name.upper()}' INITIALIZED"}

@router.post("/goal/deposit")
def goal_deposit(req: GoalDepositRequest, db: Session = Depends(get_db)):
    return deposit_to_goal(db, req.user_id, req.goal_id, req.amount)

@router.post("/goal/withdraw")
def goal_withdraw(req: GoalWithdrawRequest, db: Session = Depends(get_db)):
    return withdraw_from_goal(db, req.user_id, req.goal_id, req.amount)

@router.get("/goal/status/{user_id}")
def goal_status(user_id: int, db: Session = Depends(get_db)):
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    return {"goals": [{"id": g.id, "name": g.name, "target_amount": g.target_amount, "current_amount": g.current_amount, "progress_pct": g.progress_pct, "status": g.status} for g in goals]}
