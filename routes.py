from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import (
    Transaction, Debt, Goal, User,
    TransactionTypeEnum, GoalStatusEnum
)
from app.engines.kernel_panic import check_and_block, get_system_status
from app.engines.penalty import deposit_to_goal, withdraw_from_goal
from app.services.security import authenticate

router = APIRouter(prefix="/api/v1", tags=["deonats-kernel"])


# ─── Auth schemas ────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str


# ─── Transaction schemas ─────────────────────────────────────────────────────

class AddTransactionRequest(BaseModel):
    user_id: int
    amount: float = Field(..., gt=0)
    type: TransactionTypeEnum
    category: str
    description: Optional[str] = None


# ─── Debt schemas ─────────────────────────────────────────────────────────────

class RepayDebtRequest(BaseModel):
    user_id: int
    debt_id: int
    amount: float = Field(..., gt=0)


# ─── Goal schemas ─────────────────────────────────────────────────────────────

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


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/auth/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    """CLI: login [username] [password]"""
    user = authenticate(db, req.username, req.password)
    return {
        "status": "AUTH_OK",
        "user_id": user.id,
        "username": user.username,
        "theme": user.theme,
        "language": user.language,
        "message": f"KERNEL: WELCOME BACK, {user.username.upper()}",
    }


@router.post("/transaction/add")
def add_transaction(req: AddTransactionRequest, db: Session = Depends(get_db)):
    """CLI: add [amount] [type] [category] [description?]"""
    if req.type == TransactionTypeEnum.expense:
        kernel = check_and_block(db, req.user_id, req.category, req.amount)
        if not kernel["allowed"]:
            return {
                "status": "BLOCKED",
                "kernel_panic": True,
                "message": kernel["message"],
                "category": req.category,
            }

    tx = Transaction(
        user_id=req.user_id,
        amount=req.amount,
        type=req.type,
        category=req.category,
        description=req.description,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    response = {
        "status": "OK",
        "transaction_id": tx.id,
        "amount": tx.amount,
        "type": tx.type,
        "category": tx.category,
        "created_at": tx.created_at.isoformat(),
        "message": f"TX #{tx.id} COMMITTED",
    }
    if req.type == TransactionTypeEnum.expense and "usage_pct" in kernel:
        response["kernel"] = {
            "usage_pct": kernel.get("usage_pct"),
            "limit": kernel.get("limit"),
            "message": kernel.get("message"),
        }
    return response


@router.get("/status/{user_id}")
def check_status(user_id: int, db: Session = Depends(get_db)):
    """CLI: check-status"""
    return get_system_status(db, user_id)


@router.post("/debt/repay")
def repay_debt(req: RepayDebtRequest, db: Session = Depends(get_db)):
    """CLI: repay-debt [debt_id] [amount]"""
    debt = db.query(Debt).filter(Debt.id == req.debt_id, Debt.user_id == req.user_id).first()
    if not debt:
        raise HTTPException(status_code=404, detail="DEBT RECORD NOT FOUND")
    if debt.is_closed:
        return {"status": "ALREADY_CLOSED", "message": f"DEBT #{req.debt_id} ALREADY SETTLED"}

    debt.amount_paid = round(debt.amount_paid + req.amount, 2)
    if debt.amount_paid >= debt.amount:
        debt.is_closed = True
        debt.amount_paid = debt.amount
        db.commit()
        return {
            "status": "DEBT_CLOSED",
            "debt_id": debt.id,
            "creditor": debt.creditor,
            "paid_total": debt.amount_paid,
            "message": f"DEBT TO '{debt.creditor.upper()}' FULLY SETTLED",
        }

    db.commit()
    return {
        "status": "PARTIAL_REPAYMENT",
        "debt_id": debt.id,
        "creditor": debt.creditor,
        "paid_now": req.amount,
        "paid_total": debt.amount_paid,
        "remaining": debt.remaining,
        "message": f"REPAYMENT RECORDED — {debt.remaining:.2f} REMAINING",
    }


@router.post("/goal/add")
def goal_add(req: GoalAddRequest, db: Session = Depends(get_db)):
    """CLI: goal-add [name] [amount] [deadline]"""
    goal = Goal(
        user_id=req.user_id,
        name=req.name,
        target_amount=req.amount,
        deadline=req.deadline,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {
        "status": "GOAL_CREATED",
        "goal_id": goal.id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "deadline": goal.deadline.isoformat(),
        "message": f"GOAL '{goal.name.upper()}' INITIALIZED — TARGET: {goal.target_amount:.2f}",
    }


@router.post("/goal/deposit")
def goal_deposit(req: GoalDepositRequest, db: Session = Depends(get_db)):
    return deposit_to_goal(db, req.user_id, req.goal_id, req.amount)


@router.post("/goal/withdraw")
def goal_withdraw(req: GoalWithdrawRequest, db: Session = Depends(get_db)):
    """CLI: goal-withdraw [goal_id] [amount] — triggers PenaltyEngine if early"""
    return withdraw_from_goal(db, req.user_id, req.goal_id, req.amount)


@router.get("/goal/status/{user_id}")
def goal_status(user_id: int, db: Session = Depends(get_db)):
    """CLI: goal-status"""
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    return {
        "goals": [
            {
                "id": g.id,
                "name": g.name,
                "target_amount": g.target_amount,
                "current_amount": g.current_amount,
                "progress_pct": g.progress_pct,
                "deadline": g.deadline.isoformat(),
                "status": g.status,
                "penalty_applied": g.penalty_applied,
                "penalty_amount": g.penalty_amount,
            }
            for g in goals
        ]
    }
