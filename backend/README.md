# Actora — Backend (FastAPI)

프로토타입 단계의 FastAPI 백엔드.

## 환경 셋업 (최초 1회)

Poetry가 pyenv 환경과 충돌하는 이슈가 있어 in-project `.venv`를 명시적으로 생성하는 방식 사용:

```bash
# 1. in-project venv 직접 생성 (pyenv 3.11.x 사용)
$(pyenv which python3.11) -m venv .venv

# 2. poetry-plugin-export로 lock → requirements 추출
poetry self add poetry-plugin-export   # 최초 1회
poetry export -f requirements.txt --output /tmp/req.txt --without-hashes

# 3. .venv에 직접 설치
.venv/bin/pip install -r /tmp/req.txt

# 4. 환경 파일 준비
cp .env.loc.example .env.loc  # 그리고 비밀번호 등 수정
```

## 실행

```bash
# VSCode에서 폴더 열면 .vscode/tasks.json이 자동 실행함
# 또는 수동으로:
ENVIRONMENT=loc .venv/bin/python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Alembic

```bash
ENVIRONMENT=loc .venv/bin/alembic revision --autogenerate -m "init"
ENVIRONMENT=loc .venv/bin/alembic upgrade head
```

## 디렉토리 구조

```
backend/
├── alembic/              # DB 마이그레이션
├── src/
│   ├── auth/             # 인증 (프로토타입 단계 — 비어있음)
│   ├── common/           # 공통 유틸
│   ├── config.py         # 환경설정 (pydantic-settings)
│   ├── database.py       # SQLAlchemy async 세션
│   ├── exceptions.py     # 전역 예외 핸들러
│   ├── logging_config.py # 로깅 설정
│   └── main.py           # FastAPI 진입점
├── alembic.ini
└── pyproject.toml
```
