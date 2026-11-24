import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt(12)).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except ValueError:
        return False


def make_token(uid: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(uid), "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_user(db: Session = Depends(get_db)) -> User:
    """Return the single local workspace owner; authentication is disabled."""
    user = db.query(User).filter(User.email == "local@forestwatch.local").first()
    if user is None:
        user = User(email="local@forestwatch.local", name="Local workspace", password_hash="disabled-login")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


_hits = defaultdict(deque)


def rate_limit(name: str, limit: int, per: int = 60):
    """Per-IP sliding window limiter (in-memory; use Redis if you run several workers)."""
    def dep(request: Request):
        ip = request.client.host if request.client else "?"
        q = _hits[(name, ip)]
        now = time.time()
        while q and now - q[0] > per:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, f"Too many requests. Try again in {int(per - (now - q[0])) + 1}s.")
        q.append(now)
    return dep
