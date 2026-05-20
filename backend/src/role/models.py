from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base


class RoleMaster(Base):
    """account_type + role_code 조합으로 권한(permission_json) 을 정의.

    예시:
      (ADMIN, SUPER)    → 모든 메뉴 허용
      (ADMIN, OPERATOR) → 일부 메뉴
      (ADMIN, CS)       → 고객지원 메뉴
      (TALENT, DEFAULT) → 연기자 기본 메뉴
      (AGENCY, DEFAULT) → 에이전시 기본 메뉴

    permission_json 형식: {"menu": ["key1", "key2", ...]} — 메뉴 키 배열.
    프론트엔드의 코드 기반 메뉴 정의 ∩ 이 배열 = 실제 표시 메뉴.
    SUPER 처럼 모든 메뉴 허용은 ["*"] 와일드카드.
    """

    __tablename__ = "role_master"

    role_id = Column(BigInteger, primary_key=True, autoincrement=True)

    account_type = Column(String(20), nullable=False)
    role_code = Column(String(30), nullable=False)
    display_name = Column(String(100), nullable=False)

    permission_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    __table_args__ = (
        UniqueConstraint("account_type", "role_code", name="uq_role_master_type_code"),
        CheckConstraint(
            "account_type IN ('ADMIN', 'TALENT', 'AGENCY')",
            name="ck_role_master_account_type",
        ),
    )
