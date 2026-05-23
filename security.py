from datetime import datetime
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.models import User, SystemLog

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_FAILED_ATTEMPTS = 3


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _log(db: Session, user_id: int | None, level: str, event: str, detail: str = None):
    db.add(SystemLog(user_id=user_id, level=level, event=event, detail=detail))
    db.commit()


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()

    if not user:
        _log(db, None, "WARN", "AUTH_FAIL", f"Unknown user: {username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="KERNEL: AUTHENTICATION FAILURE — USER NOT FOUND")

    if user.is_locked:
        _log(db, user.id, "CRITICAL", "AUTH_LOCKED", f"Locked user attempted login: {username}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="KERNEL PANIC: ACCOUNT LOCKED — MAX ATTEMPTS EXCEEDED")

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.is_locked = True
            db.commit()
            _log(db, user.id, "CRITICAL", "AUTH_LOCKOUT",
                 f"Account locked after {MAX_FAILED_ATTEMPTS} failed attempts")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"KERNEL PANIC: ACCOUNT LOCKED — {MAX_FAILED_ATTEMPTS} FAILED ATTEMPTS"
            )
        db.commit()
        remaining = MAX_FAILED_ATTEMPTS - user.failed_attempts
        _log(db, user.id, "WARN", "AUTH_FAIL", f"Bad password, {remaining} attempts left")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"KERNEL: WRONG PASSWORD — {remaining} ATTEMPTS REMAINING"
        )

    user.failed_attempts = 0
    user.last_login = datetime.utcnow()
    db.commit()
    _log(db, user.id, "INFO", "AUTH_OK", f"User authenticated: {username}")
    return user


def unlock_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_locked = False
    user.failed_attempts = 0
    db.commit()
    _log(db, user.id, "INFO", "ADMIN_UNLOCK", f"Account unlocked: {username}")
    return user
