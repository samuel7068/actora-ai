from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


Gender = Literal["MALE", "FEMALE", "SELF_DESCRIBED"]
RegionCode = Literal[
    "SEOUL", "BUSAN", "INCHEON", "DAEGU", "DAEJEON", "GWANGJU", "ULSAN", "SEJONG",
    "GYEONGGI", "GANGWON", "CHUNGBUK", "CHUNGNAM", "JEONBUK", "JEONNAM",
    "GYEONGBUK", "GYEONGNAM", "JEJU", "OVERSEAS",
]
TalentCategory = Literal[
    "ACTOR", "MODEL", "INFLUENCER", "VOCAL", "DANCER", "MC", "CREATOR",
]
WeightRange = Literal[
    "skinny", "slim", "standard", "toned", "muscular",
    "chubby", "sturdy", "plus_size",
]
CareerLevel = Literal["NEWBIE", "PRO"]
EducationLevel = Literal["MIDDLE_SCHOOL", "HIGH_SCHOOL", "BACHELOR", "GRADUATE"]


class TalentProfileResponse(BaseModel):
    """GET /talent/profile — talent_master 전체 + 필수값 누락 여부"""

    account_id: int

    stage_name: Optional[str] = None
    gender: Optional[Gender] = None
    gender_self_description: Optional[str] = None
    birth_date: Optional[date] = None
    nationality: Optional[str] = None
    region_code: Optional[RegionCode] = None
    main_category: Optional[TalentCategory] = None
    sub_categories: Optional[list[str]] = None
    profile_image_url: Optional[str] = None
    profile_image_urls: Optional[list[str]] = None
    introduction: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    weight_range: Optional[WeightRange] = None
    body_type: Optional[list[str]] = None
    face_type: Optional[list[str]] = None
    visual_keywords: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    education_level: Optional[EducationLevel] = None
    education_major: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    career_level: Optional[CareerLevel] = None
    career_years: Optional[int] = None

    visibility_status: str
    approval_status: str
    profile_completion_rate: int
    ai_match_score: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class TalentProfileUpdateRequest(BaseModel):
    """PUT /talent/profile — 필수: gender, birth_date, nationality, main_category, height_cm, weight_kg"""

    # 필수
    gender: Gender
    birth_date: date
    nationality: str = Field(min_length=1, max_length=50)
    main_category: TalentCategory
    height_cm: int = Field(ge=50, le=250)
    weight_kg: int = Field(ge=20, le=300)

    # 옵션
    stage_name: Optional[str] = Field(default=None, max_length=100)
    gender_self_description: Optional[str] = Field(default=None, max_length=50)
    region_code: Optional[RegionCode] = None
    sub_categories: Optional[list[str]] = None
    profile_image_url: Optional[str] = Field(default=None, max_length=500)
    # 최소 1장, 최대 5장 (UI 검증). 빈 문자열은 제거됨.
    profile_image_urls: list[str] = Field(min_length=1, max_length=5)
    introduction: Optional[str] = None
    weight_range: Optional[WeightRange] = None
    body_type: Optional[list[str]] = None
    face_type: Optional[list[str]] = None
    visual_keywords: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    education_level: Optional[EducationLevel] = None
    education_major: Optional[str] = Field(default=None, max_length=100)
    instagram_url: Optional[str] = Field(default=None, max_length=500)
    youtube_url: Optional[str] = Field(default=None, max_length=500)
    tiktok_url: Optional[str] = Field(default=None, max_length=500)
    career_level: Optional[CareerLevel] = None
    career_years: Optional[int] = Field(default=None, ge=0, le=80)

    @model_validator(mode="after")
    def _normalize_profile_image_urls(self):
        # 공백 제거 + 빈 문자열 제거. 결과가 비면 ValueError.
        cleaned = [u.strip() for u in (self.profile_image_urls or []) if u and u.strip()]
        if not cleaned:
            raise ValueError("AT_LEAST_ONE_PROFILE_IMAGE_REQUIRED")
        if len(cleaned) > 5:
            raise ValueError("TOO_MANY_PROFILE_IMAGES")
        self.profile_image_urls = cleaned
        return self

    @model_validator(mode="after")
    def _check_self_described(self):
        # SELF_DESCRIBED 면 gender_self_description 필요
        if self.gender == "SELF_DESCRIBED":
            if not self.gender_self_description:
                raise ValueError("GENDER_SELF_DESCRIPTION_REQUIRED")
        else:
            # MALE/FEMALE 인데 self_description 들어왔으면 무시 (또는 비우기)
            self.gender_self_description = None
        return self

    @model_validator(mode="after")
    def _check_education_major(self):
        # 대졸/대학원졸이면 전공 필요
        if self.education_level in ("BACHELOR", "GRADUATE"):
            if not self.education_major:
                raise ValueError("EDUCATION_MAJOR_REQUIRED")
        elif self.education_level in ("MIDDLE_SCHOOL", "HIGH_SCHOOL"):
            self.education_major = None
        return self
