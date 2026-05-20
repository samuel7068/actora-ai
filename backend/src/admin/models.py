from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    text,
)

from src.database import Base


class AdminMaster(Base):
    """admin 권한 그 자체는 role_master(account_type='ADMIN', role_code=...) 에서 정의.
    이 테이블은 단순히 'account 가 ADMIN 인 경우의 sub-type 매핑' 역할.
    """

    __tablename__ = "admin_master"

    account_id = Column(
        BigInteger,
        ForeignKey("account_master.account_id", ondelete="CASCADE"),
        primary_key=True,
    )

    role_code = Column(String(20), nullable=False)

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
        CheckConstraint(
            "role_code IN ('SUPER', 'OPERATOR', 'CS')",
            name="ck_admin_master_role_code",
        ),
    )
