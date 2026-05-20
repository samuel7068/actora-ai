from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MediaInfo(BaseModel):
    """업로드 결과 / 조회 응답에 사용되는 미디어 메타 정보."""

    talent_media_id: int
    account_id: int
    media_type: str  # PHOTO / MOVIE
    media_path: str  # 상대 키 (예: 'talent/15/8d92f1c2.jpg')
    thumbnail_path: Optional[str] = None
    original_file_name: Optional[str] = None
    stored_file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    sort_order: int
    is_main: bool
    is_public: bool
    view_count: int
    created_at: datetime
    # 클라이언트가 바로 조회할 수 있는 stream URL (백엔드가 채워줌)
    stream_url: str


class MediaListResponse(BaseModel):
    items: list[MediaInfo]
    total: int
