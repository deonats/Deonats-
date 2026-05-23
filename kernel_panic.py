"""
KernelPanicEngine — проверяет лимиты категорий, блокирует при перерасходе,
пишет системные логи.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.models import Transaction, CategoryLimit, SystemLog, TransactionTypeEnum


KERNEL_PANIC_THRESHOLD = 1.0  # 100% лимита = паника


def _write_log(db: Session, user_id: int, level: str, event: str, detail: str):
    db.add(SystemLog(user_id=user_id, level=level, event=event, detail=detail))
    db.commit()


def _get_month_spending(db: Session, user_id: int, category: str) -> float:
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionTypeEnum.expense,
            Transaction.category == category,
            Transaction.created_at >= month_start,
        )
        .all()
    )
    return round(sum(r.amount for r in rows), 2)


def check_and_block(db: Session, user_id: int, category: str, new_amount: float) -> dict:
    """
    Вызывается перед записью новой транзакции.
    Возвращает dict с полями: allowed, panic, current_spend, limit, message
    """
    limit_obj = (
        db.query(CategoryLimit)
        .filter(CategoryLimit.user_id == user_id, CategoryLimit.category == category)
        .first()
    )

    if not limit_obj:
        return {"allowed": True, "panic": False, "message": "NO_LIMIT_SET"}

    if limit_obj.is_blocked:
        _write_log(db, user_id, "CRITICAL", "KERNEL_PANIC",
                   f"Category '{category}' is BLOCKED — transaction rejected")
        return {
            "allowed": False,
            "panic": True,
            "current_spend": _get_month_spending(db, user_id, category),
            "limit": limit_obj.monthly_limit,
            "message": f"KERNEL PANIC: CATEGORY '{category.upper()}' IS BLOCKED",
        }

    current = _get_month_spending(db, user_id, category)
    projected = current + new_amount
    usage_ratio = projected / limit_obj.monthly_limit if limit_obj.monthly_limit > 0 else 0.0

    if usage_ratio >= KERNEL_PANIC_THRESHOLD:
        limit_obj.is_blocked = True
        db.commit()
        _write_log(db, user_id, "CRITICAL", "KERNEL_PANIC",
                   f"OVER LIMIT: '{category}' {projected:.2f}/{limit_obj.monthly_limit:.2f} — BLOCKED")
        return {
            "allowed": False,
            "panic": True,
            "current_spend": current,
            "limit": limit_obj.monthly_limit,
            "message": (
                f"KERNEL PANIC: '{category.upper()}' LIMIT EXCEEDED "
                f"({projected:.2f}/{limit_obj.monthly_limit:.2f}) — CATEGORY LOCKED"
            ),
        }

    if usage_ratio >= 0.8:
        _write_log(db, user_id, "WARN", "KERNEL_WARNING",
                   f"WARNING: '{category}' at {usage_ratio*100:.0f}% of limit")

    return {
        "allowed": True,
        "panic": False,
        "current_spend": current,
        "projected_spend": projected,
        "limit": limit_obj.monthly_limit,
        "usage_pct": round(usage_ratio * 100, 1),
        "message": f"OK — {usage_ratio*100:.1f}% OF LIMIT USED",
    }


def get_system_status(db: Session, user_id: int) -> dict:
    """Возвращает сводку состояния ядра для команды check-status."""
    limits = db.query(CategoryLimit).filter(CategoryLimit.user_id == user_id).all()
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    categories = []
    for lim in limits:
        spent = _get_month_spending(db, user_id, lim.category)
        pct = round(spent / lim.monthly_limit * 100, 1) if lim.monthly_limit > 0 else 0.0
        categories.append({
            "category": lim.category,
            "spent": spent,
            "limit": lim.monthly_limit,
            "usage_pct": pct,
            "blocked": lim.is_blocked,
        })

    logs = (
        db.query(SystemLog)
        .filter(SystemLog.user_id == user_id, SystemLog.created_at >= month_start)
        .order_by(SystemLog.created_at.desc())
        .limit(20)
        .all()
    )
    log_entries = [
        {"ts": l.created_at.isoformat(), "level": l.level, "event": l.event, "detail": l.detail}
        for l in logs
    ]

    panic_count = sum(1 for c in categories if c["blocked"])
    return {
        "kernel_panic": panic_count > 0,
        "panic_count": panic_count,
        "categories": categories,
        "recent_logs": log_entries,
        "timestamp": now.isoformat(),
    }
