"""
PenaltyEngine — штрафует за досрочный вывод средств из цели.
Штраф: 15% от выводимой суммы, если дедлайн не достигнут.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.models import Goal, GoalStatusEnum, SystemLog

PENALTY_RATE = 0.15  # 15%


def _log(db: Session, user_id: int, event: str, detail: str):
    db.add(SystemLog(user_id=user_id, level="WARN", event=event, detail=detail))
    db.commit()


def withdraw_from_goal(db: Session, user_id: int, goal_id: int, amount: float) -> dict:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if not goal:
        return {"success": False, "message": "GOAL NOT FOUND"}

    if goal.status != GoalStatusEnum.active:
        return {"success": False, "message": f"GOAL STATUS: {goal.status.upper()} — NOT ACTIVE"}

    if amount > goal.current_amount:
        return {
            "success": False,
            "message": f"INSUFFICIENT FUNDS IN GOAL: {goal.current_amount:.2f} < {amount:.2f}"
        }

    now = datetime.utcnow()
    early_withdrawal = now < goal.deadline

    penalty = 0.0
    net_amount = amount

    if early_withdrawal:
        penalty = round(amount * PENALTY_RATE, 2)
        net_amount = round(amount - penalty, 2)
        goal.penalty_applied = True
        goal.penalty_amount = round(goal.penalty_amount + penalty, 2)
        goal.status = GoalStatusEnum.violated
        _log(db, user_id, "PENALTY_APPLIED",
             f"Goal '{goal.name}': early withdrawal {amount:.2f}, "
             f"penalty {penalty:.2f} ({PENALTY_RATE*100:.0f}%), net {net_amount:.2f}")

    goal.current_amount = round(goal.current_amount - amount, 2)
    db.commit()

    return {
        "success": True,
        "goal_name": goal.name,
        "withdrawn": amount,
        "penalty": penalty,
        "penalty_rate_pct": PENALTY_RATE * 100,
        "net_received": net_amount,
        "early_withdrawal": early_withdrawal,
        "remaining_in_goal": goal.current_amount,
        "message": (
            f"PENALTY ENGINE: -{penalty:.2f} INTEGRITY VIOLATION FEE APPLIED"
            if early_withdrawal
            else "WITHDRAWAL OK — DEADLINE PASSED"
        ),
    }


def deposit_to_goal(db: Session, user_id: int, goal_id: int, amount: float) -> dict:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if not goal:
        return {"success": False, "message": "GOAL NOT FOUND"}

    if goal.status == GoalStatusEnum.completed:
        return {"success": False, "message": "GOAL ALREADY COMPLETED"}

    goal.current_amount = round(goal.current_amount + amount, 2)

    if goal.current_amount >= goal.target_amount:
        goal.status = GoalStatusEnum.completed
        db.commit()
        return {
            "success": True,
            "goal_name": goal.name,
            "deposited": amount,
            "total": goal.current_amount,
            "progress_pct": 100.0,
            "message": f"GOAL '{goal.name.upper()}' COMPLETED — TARGET REACHED",
        }

    db.commit()
    return {
        "success": True,
        "goal_name": goal.name,
        "deposited": amount,
        "total": goal.current_amount,
        "progress_pct": goal.progress_pct,
        "message": f"DEPOSIT OK — {goal.progress_pct:.1f}% OF TARGET",
    }
