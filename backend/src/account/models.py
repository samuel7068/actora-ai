from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    String,
    text,
)

from src.database import Base


class AccountMaster(Base):
    __tablename__ = "account_master"

    account_id = Column(BigInteger, primary_key=True, autoincrement=True)

    login_id = Column(String(64), nullable=False, unique=True)
    email = Column(String(254), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)

    account_type = Column(String(20), nullable=False)

    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))

    last_login_at = Column(DateTime(timezone=True), nullable=True)

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
            "account_type IN ('ADMIN', 'TALENT', 'AGENCY')",
            name="ck_account_master_account_type",
        ),
    )
