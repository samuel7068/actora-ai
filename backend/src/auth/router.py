from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.account.models import AccountMaster
from src.admin.models import AdminMaster
from src.agency.models import AgencyMaster, AgencyMember
from src.role.models import RoleMaster
from src.talent.models import TalentMaster
from src.auth.schemas import (
    AccountInfo,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RegisterAgencyRequest,
    RegisterTalentRequest,
)
from src.auth.security import JWT_EXPIRES_MINUTES, create_access_token
from src.auth.deps import get_current_account

auth_router = APIRouter()


async def _resolve_role(
    db: AsyncSession, account_type: str, role_code: str
) -> RoleMaster | None:
    return (
        await db.execute(
            select(RoleMaster).where(
                RoleMaster.account_type == account_type,
                RoleMaster.role_code == role_code,
                RoleMaster.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _account_info(
    db: AsyncSession,
    account: AccountMaster,
    admin: AdminMaster | None,
) -> AccountInfo:
    # role_code 결정: admin 이면 admin.role_code, 아니면 DEFAULT
    role_code = admin.role_code if admin else "DEFAULT"
    role = await _resolve_role(db, account.account_type, role_code)
    return AccountInfo(
        account_id=account.account_id,
        login_id=account.login_id,
        email=account.email,
        name=account.name,
        account_type=account.account_type,
        role_code=role_code,
        role_display_name=role.display_name if role else None,
        last_login_at=account.last_login_at,
        permission=role.permission_json if role else {},
    )


@auth_router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = req.identifier.strip()
    # identifier 에 @ 있으면 email 로, 아니면 login_id 로 조회
    if "@" in identifier:
        cond = AccountMaster.email == identifier
    else:
        cond = AccountMaster.login_id == identifier

    account = (
        await db.execute(select(AccountMaster).where(cond))
    ).scalar_one_or_none()

    if not account or account.password != req.password:
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    if not account.is_active:
        raise HTTPException(status_code=403, detail="INACTIVE_ACCOUNT")

    # admin 정보 같이 가져오기
    admin = None
    if account.account_type == "ADMIN":
        admin = (
            await db.execute(
                select(AdminMaster).where(AdminMaster.account_id == account.account_id)
            )
        ).scalar_one_or_none()

    # last_login_at 갱신
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AccountMaster)
        .where(AccountMaster.account_id == account.account_id)
        .values(last_login_at=now)
    )
    await db.commit()
    account.last_login_at = now

    token = create_access_token(account.account_id, account.login_id)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRES_MINUTES * 60,
        account=await _account_info(db, account, admin),
    )


@auth_router.get("/me", response_model=MeResponse)
async def me(
    current=Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    account, admin = current
    return MeResponse(account=await _account_info(db, account, admin))


@auth_router.post("/logout")
async def logout():
    # stateless JWT — 서버는 알 수 없으므로 클라이언트가 토큰 삭제하면 됨
    return {"success": True}


# ─────────────────────────────────────────────────────────
# 회원가입
# ─────────────────────────────────────────────────────────
async def _check_dup(db: AsyncSession, login_id: str, email: str) -> None:
    existing = (
        await db.execute(
            select(AccountMaster).where(
                or_(
                    AccountMaster.login_id == login_id,
                    AccountMaster.email == email,
                )
            )
        )
    ).scalar_one_or_none()
    if existing:
        if existing.login_id == login_id:
            raise HTTPException(status_code=409, detail="DUPLICATE_LOGIN_ID")
        raise HTTPException(status_code=409, detail="DUPLICATE_EMAIL")


async def _issue_token_and_info(
    db: AsyncSession, account: AccountMaster, admin: AdminMaster | None
) -> LoginResponse:
    token = create_access_token(account.account_id, account.login_id)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRES_MINUTES * 60,
        account=await _account_info(db, account, admin),
    )


@auth_router.post("/register/talent", response_model=LoginResponse, status_code=201)
async def register_talent(
    req: RegisterTalentRequest, db: AsyncSession = Depends(get_db)
):
    await _check_dup(db, req.login_id, req.email)

    account = AccountMaster(
        login_id=req.login_id,
        email=req.email,
        password=req.password,  # 평문 (프로토타입). 운영 시 해시.
        name=req.name,
        account_type="TALENT",
    )
    db.add(account)
    try:
        await db.flush()  # account_id 발급
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE_LOGIN_ID_OR_EMAIL")

    talent = TalentMaster(
        account_id=account.account_id,
        stage_name=req.stage_name,
    )
    db.add(talent)
    await db.commit()
    await db.refresh(account)

    return await _issue_token_and_info(db, account, None)


@auth_router.post("/register/agency", response_model=LoginResponse, status_code=201)
async def register_agency(
    req: RegisterAgencyRequest, db: AsyncSession = Depends(get_db)
):
    await _check_dup(db, req.login_id, req.email)

    # 1. account_master
    account = AccountMaster(
        login_id=req.login_id,
        email=req.email,
        password=req.password,
        name=req.name,
        account_type="AGENCY",
    )
    db.add(account)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE_LOGIN_ID_OR_EMAIL")

    # 2. agency_master
    agency = AgencyMaster(
        agency_name=req.agency_name,
        agency_type=req.agency_type,
        business_number=req.business_number,
    )
    db.add(agency)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE_BUSINESS_NUMBER")

    # 3. agency_member (OWNER 자동)
    member = AgencyMember(
        agency_id=agency.agency_id,
        account_id=account.account_id,
        role_code="OWNER",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.commit()
    await db.refresh(account)

    return await _issue_token_and_info(db, account, None)
