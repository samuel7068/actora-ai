"""recreate admin_master under account_master

Revision ID: a9a4c7007f6a
Revises: 5ca70ff5abba
Create Date: 2026-05-20 06:32:31.417567

기존 admin_master(평면 구조)를 통째로 drop 하고
account_master(공통 인증) + admin_master(자식, 권한만) 두 테이블로 재구성.
기존 admin_master 데이터(jkkim 1행)는 사라지므로 마이그레이션 후 재등록 필요.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a9a4c7007f6a"
down_revision: Union[str, Sequence[str], None] = "5ca70ff5abba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 기존 admin_master 통째로 제거 (데이터 손실 의도)
    op.drop_table("admin_master")

    # 2) account_master 신규 생성
    op.create_table(
        "account_master",
        sa.Column("account_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("login_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_type IN ('ADMIN', 'TALENT', 'AGENCY')",
            name="ck_account_master_account_type",
        ),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("login_id"),
        sa.UniqueConstraint("email"),
    )

    # 3) admin_master 신규 생성 (account_master 자식)
    op.create_table(
        "admin_master",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("role_code", sa.String(length=20), nullable=False),
        sa.Column(
            "permission_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role_code IN ('SUPER', 'OPERATOR', 'CS')",
            name="ck_admin_master_role_code",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account_master.account_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id"),
    )


def downgrade() -> None:
    # 새 두 테이블 제거
    op.drop_table("admin_master")
    op.drop_table("account_master")

    # 옛 admin_master 복원 (데이터 자체는 복구 불가)
    op.create_table(
        "admin_master",
        sa.Column("admin_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("login_id", sa.String(length=64), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("role_code", sa.String(length=20), nullable=False),
        sa.Column(
            "permission_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role_code IN ('SUPER', 'OPERATOR', 'CS')",
            name="ck_admin_master_role_code",
        ),
        sa.PrimaryKeyConstraint("admin_id"),
        sa.UniqueConstraint("login_id"),
        sa.UniqueConstraint("email"),
    )
