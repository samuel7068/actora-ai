from typing import Any, Optional

from pydantic import BaseModel


class StageInfo(BaseModel):
    """파이프라인 단계별 결과."""
    stage: str
    label: str
    success: bool
    elapsed_ms: int
    data: Any = None
    error: Optional[str] = None


class AnalyzeDebugResponse(BaseModel):
    """디버그용 분석 응답 — 모든 중간 산출물 포함."""
    job_id: str
    original_filename: str
    upload_size_bytes: int
    total_elapsed_ms: int
    stages: list[StageInfo]
    # 영구 저장 결과 (정규화 성공 시에만 채워짐)
    talent_media_id: Optional[int] = None
    persisted_path: Optional[str] = None
    persisted_size_bytes: Optional[int] = None
    # 단계 6 산출물 — RAG 용 scene JSON 배열
    rag_scenes: Optional[list[Any]] = None
