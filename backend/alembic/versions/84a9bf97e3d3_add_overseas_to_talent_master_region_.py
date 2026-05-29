"""add OVERSEAS to talent_master region_code

Revision ID: 84a9bf97e3d3
Revises: dffcca6577c6
Create Date: 2026-05-29 15:12:02.434395

"""
from typing import Sequence, Union

from alembic import op


revision: str = "84a9bf97e3d3"
down_revision: Union[str, Sequence[str], None] = "dffcca6577c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_CODES = (
    "SEOUL", "BUSAN", "INCHEON", "DAEGU", "DAEJEON", "GWANGJU", "ULSAN", "SEJONG",
    "GYEONGGI", "GANGWON", "CHUNGBUK", "CHUNGNAM", "JEONBUK", "JEONNAM",
    "GYEONGBUK", "GYEONGNAM", "JEJU", "OVERSEAS",
)
_OLD_CODES = _NEW_CODES[:-1]  # OVERSEAS 제외


def _check_sql(codes: tuple[str, ...]) -> str:
    inner = ",".join(repr(c) for c in codes)
    return f"region_code IS NULL OR region_code IN ({inner})"


def upgrade() -> None:
    op.drop_constraint(
        "ck_talent_master_region_code", "talent_master", type_="check"
    )
    op.create_check_constraint(
        "ck_talent_master_region_code",
        "talent_master",
        _check_sql(_NEW_CODES),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_talent_master_region_code", "talent_master", type_="check"
    )
    op.create_check_constraint(
        "ck_talent_master_region_code",
        "talent_master",
        _check_sql(_OLD_CODES),
    )
