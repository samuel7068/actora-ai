from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)

from src.database import Base


class AgencyMaster(Base):
    """업체(법인) 정보. 로그인 안 함. 멤버는 agency_member 를 통해 account_master 와 연결."""

    __tablename__ = "agency_master"

    agency_id = Column(BigInteger, primary_key=True, autoincrement=True)

    agency_name = Column(String(200), nullable=False)
    agency_type = Column(String(20), nullable=False)

    representative_name = Column(String(100), nullable=True)
    business_number = Column(String(20), nullable=True, unique=True)
    business_email = Column(String(254), nullable=True)
    phone_number = Column(String(30), nullable=True)
    website_url = Column(String(500), nullable=True)
    logo_image_url = Column(String(500), nullable=True)
    address = Column(String(500), nullable=True)
    introduction = Column(Text, nullable=True)

    is_verified = Column(Boolean, nullable=False, server_default=text("FALSE"))
    approval_status = Column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )
    subscription_type = Column(
        String(20), nullable=False, server_default=text("'FREE'")
    )
    ai_recommend_enabled = Column(
        Boolean, nullable=False, server_default=text("FALSE")
    )

    casting_count = Column(BigInteger, nullable=False, server_default=text("0"))
    successful_match_count = Column(
        BigInteger, nullable=False, server_default=text("0")
    )

    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )

    __table_args__ = (
        CheckConstraint(
            "agency_type IN ('AGENCY','PRODUCTION','BRAND','CASTING')",
            name="ck_agency_master_agency_type",
        ),
        CheckConstraint(
            "approval_status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_agency_master_approval_status",
        ),
        CheckConstraint(
            "subscription_type IN ('FREE','BASIC','PREMIUM')",
            name="ck_agency_master_subscription_type",
        ),
    )


class AgencyMember(Base):
    """업체 ↔ 사람(account) 의 다대일 매핑. account 한 개는 한 업체에만 속함."""

    __tablename__ = "agency_member"

    agency_member_id = Column(BigInteger, primary_key=True, autoincrement=True)

    agency_id = Column(
        BigInteger,
        ForeignKey("agency_master.agency_id", ondelete="CASCADE"),
        nullable=False,
    )
    # account_id UNIQUE — 한 사람은 한 업체에만 (회사 옮길 땐 새 account 가입)
    account_id = Column(
        BigInteger,
        ForeignKey("account_master.account_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # role_code 값 (OWNER/MANAGER/CASTING_MANAGER/VIEWER 등) 은 추후 정의 — CHECK 없이 자유
    role_code = Column(String(30), nullable=True)

    department = Column(String(100), nullable=True)
    position_name = Column(String(100), nullable=True)

    joined_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )
