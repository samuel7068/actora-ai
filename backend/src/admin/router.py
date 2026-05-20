"""관리자 전용 API (account_type='ADMIN' 만 접근)."""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from src.auth.deps import get_current_account

logger = logging.getLogger(__name__)

admin_router = APIRouter()

# TASK_SHARE.md 위치 — 프로젝트 루트
# 컨테이너 내부: /app/TASK_SHARE.md (backend WORKDIR=/app, 코드 COPY . . 시 포함)
# Mac dev: backend/ 기준 상위 디렉토리의 TASK_SHARE.md
_TASK_SHARE_PATHS = [
    Path("/app/TASK_SHARE.md"),
    Path(__file__).resolve().parent.parent.parent.parent / "TASK_SHARE.md",
    Path(__file__).resolve().parent.parent.parent / "TASK_SHARE.md",
]


def _read_task_share() -> str:
    for p in _TASK_SHARE_PATHS:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"TASK_SHARE.md read error at {p}: {e}")
    return "# TASK_SHARE.md 를 찾을 수 없습니다.\n\n프로젝트 루트에 파일을 생성하세요."


@admin_router.get("/task-share")
async def get_task_share(current=Depends(get_current_account)):
    """관리자 전용 개발 공유 노트. ADMIN(SUPER/OPERATOR/CS) 전체 허용."""
    account, _admin = current
    if account.account_type != "ADMIN":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")

    content = _read_task_share()
    return {"content": content}
