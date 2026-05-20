from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    identifier: str  # email 또는 login_id
    password: str


class RegisterTalentRequest(BaseModel):
    login_id: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=4, max_length=255)
    name: str = Field(min_length=1, max_length=100)  # 본명
    stage_name: Optional[str] = Field(default=None, max_length=100)


class RegisterAgencyRequest(BaseModel):
    login_id: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=4, max_length=255)
    name: str = Field(min_length=1, max_length=100)  # 가입자 본명
    agency_name: str = Field(min_length=1, max_length=200)
    agency_type: Literal["AGENCY", "PRODUCTION", "BRAND", "CASTING"]
    business_number: Optional[str] = Field(default=None, max_length=20)


class AccountInfo(BaseModel):
    account_id: int
    login_id: str
    email: str
    name: str
    account_type: str  # ADMIN / TALENT / AGENCY
    role_code: Optional[str] = None  # ADMIN 은 SUPER/OPERATOR/CS, TALENT/AGENCY 는 DEFAULT
    role_display_name: Optional[str] = None  # 한국어 표시명 ("최고관리자" 등)
    last_login_at: Optional[datetime] = None
    permission: dict[str, Any] = {}  # role_master.permission_json 그대로


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 초 단위
    account: AccountInfo


class MeResponse(BaseModel):
    account: AccountInfo
