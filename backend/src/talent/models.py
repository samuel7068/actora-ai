from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base

# enum 후보값 (CHECK 제약에 사용)
_REGION_CODES = (
    "SEOUL", "BUSAN", "INCHEON", "DAEGU", "DAEJEON", "GWANGJU", "ULSAN", "SEJONG",
    "GYEONGGI", "GANGWON", "CHUNGBUK", "CHUNGNAM", "JEONBUK", "JEONNAM",
    "GYEONGBUK", "GYEONGNAM", "JEJU",
)
_TALENT_CATEGORIES = (
    "ACTOR", "MODEL", "INFLUENCER", "VOCAL", "DANCER", "MC", "CREATOR",
)


class TalentMaster(Base):
    """account_type='TALENT' 인 account 의 추가 정보 (1:1)."""

    __tablename__ = "talent_master"

    account_id = Column(
        BigInteger,
        ForeignKey("account_master.account_id", ondelete="CASCADE"),
        primary_key=True,
    )

    stage_name = Column(String(100), nullable=True)

    # gender: MALE / FEMALE / SELF_DESCRIBED — 후자면 별도 텍스트
    gender = Column(String(20), nullable=True)
    gender_self_description = Column(String(50), nullable=True)

    birth_date = Column(Date, nullable=True)
    nationality = Column(String(50), nullable=True)
    region_code = Column(String(20), nullable=True)

    main_category = Column(String(20), nullable=True)
    sub_categories = Column(JSONB, nullable=True)  # 예: ["MODEL","MC"]

    profile_image_url = Column(String(500), nullable=True)
    introduction = Column(Text, nullable=True)

    height_cm = Column(SmallInteger, nullable=True)
    weight_kg = Column(SmallInteger, nullable=True)

    # 다중 선택 언어 / 자유 입력 특기 (둘 다 string 배열)
    languages = Column(JSONB, nullable=True)
    skills = Column(JSONB, nullable=True)

    instagram_url = Column(String(500), nullable=True)
    youtube_url = Column(String(500), nullable=True)
    tiktok_url = Column(String(500), nullable=True)

    career_level = Column(String(20), nullable=True)  # NEWBIE / PRO
    visibility_status = Column(
        String(20), nullable=False, server_default=text("'PRIVATE'")
    )
    approval_status = Column(
        String(20), nullable=False, server_default=text("'PENDING'")
    )

    profile_completion_rate = Column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    ai_match_score = Column(Numeric(5, 2), nullable=True)

    profile_view_count = Column(BigInteger, nullable=False, server_default=text("0"))
    favorite_count = Column(BigInteger, nullable=False, server_default=text("0"))
    casting_apply_count = Column(BigInteger, nullable=False, server_default=text("0"))

    last_active_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )

    __table_args__ = (
        CheckConstraint(
            "gender IS NULL OR gender IN ('MALE','FEMALE','SELF_DESCRIBED')",
            name="ck_talent_master_gender",
        ),
        CheckConstraint(
            f"main_category IS NULL OR main_category IN ({','.join(repr(c) for c in _TALENT_CATEGORIES)})",
            name="ck_talent_master_main_category",
        ),
        CheckConstraint(
            "career_level IS NULL OR career_level IN ('NEWBIE','PRO')",
            name="ck_talent_master_career_level",
        ),
        CheckConstraint(
            "visibility_status IN ('PUBLIC','PRIVATE')",
            name="ck_talent_master_visibility_status",
        ),
        CheckConstraint(
            "approval_status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_talent_master_approval_status",
        ),
        CheckConstraint(
            f"region_code IS NULL OR region_code IN ({','.join(repr(r) for r in _REGION_CODES)})",
            name="ck_talent_master_region_code",
        ),
        CheckConstraint(
            "profile_completion_rate >= 0 AND profile_completion_rate <= 100",
            name="ck_talent_master_completion_rate",
        ),
    )


class TalentMedia(Base):
    """talent 의 사진/동영상. account_id 가 talent_master 의 PK 와 동일하게 talent 식별."""

    __tablename__ = "talent_media"

    talent_media_id = Column(BigInteger, primary_key=True, autoincrement=True)

    account_id = Column(
        BigInteger,
        ForeignKey("talent_master.account_id", ondelete="CASCADE"),
        nullable=False,
    )

    media_type = Column(String(10), nullable=False)  # PHOTO / MOVIE

    # 상대 키 (예: 'talent/15/8d92f1c2.jpg') — 호스트 prefix 는 환경변수로
    media_path = Column(String(500), nullable=False)
    thumbnail_path = Column(String(500), nullable=True)

    original_file_name = Column(String(255), nullable=True)
    stored_file_name = Column(String(100), nullable=False)

    file_size = Column(BigInteger, nullable=True)  # bytes
    mime_type = Column(String(100), nullable=True)

    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)

    sort_order = Column(Integer, nullable=False, server_default=text("0"))
    is_main = Column(Boolean, nullable=False, server_default=text("FALSE"))
    is_public = Column(Boolean, nullable=False, server_default=text("TRUE"))

    view_count = Column(BigInteger, nullable=False, server_default=text("0"))

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()"),
    )

    __table_args__ = (
        CheckConstraint(
            "media_type IN ('PHOTO','MOVIE')",
            name="ck_talent_media_media_type",
        ),
        # 자주 조회되는 패턴: 특정 talent 의 미디어를 sort_order 순으로
        Index("ix_talent_media_account_id_sort_order", "account_id", "sort_order"),
        # talent 당 is_main=TRUE 인 행은 최대 1개 (partial unique)
        Index(
            "uq_talent_media_one_main_per_account",
            "account_id",
            unique=True,
            postgresql_where=text("is_main"),
        ),
    )
