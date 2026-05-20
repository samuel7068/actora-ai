from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db
from src.account.models import AccountMaster
from src.admin.models import AdminMaster
from src.auth.security import decode_access_token


async def get_current_account(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> tuple[AccountMaster, Optional[AdminMaster]]:
    """Authorization: Bearer <token> 헤더 검증 후 (account, admin?) 반환."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="MISSING_TOKEN")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    try:
        account_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="INVALID_TOKEN_PAYLOAD")

    account = (
        await db.execute(
            select(AccountMaster).where(AccountMaster.account_id == account_id)
        )
    ).scalar_one_or_none()
    if not account or not account.is_active:
        raise HTTPException(status_code=401, detail="ACCOUNT_NOT_FOUND_OR_INACTIVE")

    admin = None
    if account.account_type == "ADMIN":
        admin = (
            await db.execute(
                select(AdminMaster).where(AdminMaster.account_id == account_id)
            )
        ).scalar_one_or_none()

    return account, admin
