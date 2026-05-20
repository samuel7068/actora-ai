from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from src.config import get_settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 60 * 24  # 24시간


def create_access_token(account_id: int, login_id: str) -> str:
    """JWT access token 발급. payload 에는 sub(account_id), login_id, exp 만."""
    config = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "login_id": login_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """검증 + 디코드. 실패하면 None."""
    config = get_settings()
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
