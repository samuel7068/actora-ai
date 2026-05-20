# Actora — 서버 배포 가이드

> AWS Lightsail Ubuntu 24.04 서버 (`3.35.101.121`)에서 git pull → docker compose 로 직접 운영하는 방식.

## 구성 한눈에

```
[ Browser ]
     │  http://3.35.101.121  (포트 80)
     ▼
┌──────────────────────────┐
│ docker-compose (host)    │
│                          │
│  [Frontend Next.js]      │
│       └ /api/* rewrites  │
│              ↓           │
│  [Backend FastAPI]       │
│       ├ qdrant:6333  ─►  │  [Qdrant Vector DB]
│       └ host.docker.     │
│         internal:5432 ─► PostgreSQL (호스트 native)
└──────────────────────────┘
```

- **외부 노출 포트**: `80` (프론트), `5432` (PG — DB 관리툴용)
  - 백엔드 8000, Qdrant 6333/6334 는 외부 직접 접근 불가 (docker 내부망만)
- **DB는 호스트 native**, 컨테이너는 `host.docker.internal:5432`로 접근, 외부에서는 `3.35.101.121:5432` 로 관리툴 접속
- **마이그레이션**: 백엔드 컨테이너 시작 시 `alembic upgrade head` 자동 실행

---

## 최초 1회 셋업 (서버에서)

```bash
# 0. /app/actora 준비 (sudo 1회만)
sudo mkdir -p /app/actora
sudo chown -R ubuntu:ubuntu /app/actora

# 1. 코드 clone (Deploy Key가 ~/.ssh/config 에 이미 설정되어 있음)
cd /app/actora
git clone git@github.com:samuel7068/actora-ai.git .

# 2. 운영용 환경 파일 만들기 (예제 복사 후 시크릿 수정)
cp backend/.env.prod.example backend/.env.prod
nano backend/.env.prod
#   - SECRET_KEY: 강력한 값으로 교체
#   - DATABASE_URL: 실제 PG 비밀번호로 교체
#   - ALLOWED_DOMAINS: 운영 도메인 추가 시

# 3. 도커 컴포즈 빌드 + 기동 (백그라운드)
docker compose build
docker compose up -d

# 4. 컨테이너 상태 확인
docker compose ps
docker compose logs -f backend     # alembic 마이그레이션 + uvicorn 부팅 로그 확인
docker compose logs -f frontend
docker compose logs -f qdrant
```

브라우저: `http://3.35.101.121` → 프론트 노출 확인

---

## 코드 업데이트 배포 (반복 작업)

```bash
cd /app/actora
git pull
docker compose build         # 변경된 서비스만 새 이미지 생성
docker compose up -d         # 변경된 컨테이너만 교체 후 기동
docker compose ps
```

**한 줄 짜리 배포 alias** (편의용):
```bash
echo 'alias actora-deploy="cd /app/actora && git pull && docker compose build && docker compose up -d && docker compose ps"' >> ~/.bashrc
source ~/.bashrc
# 이후엔
actora-deploy
```

---

## 일상 운영 명령어

| 목적 | 명령 |
|---|---|
| 컨테이너 상태 | `docker compose ps` |
| 모든 로그 (라이브) | `docker compose logs -f` |
| 특정 서비스 로그 | `docker compose logs -f backend` |
| 컨테이너 재시작 | `docker compose restart backend` |
| 한 서비스만 다시 빌드 | `docker compose build backend && docker compose up -d backend` |
| 컨테이너 안에 쉘 진입 | `docker compose exec backend sh` |
| Qdrant 데이터 보존하며 전체 stop | `docker compose stop` |
| **전체 down + 볼륨 유지** | `docker compose down` |
| ⚠️ 볼륨까지 삭제 (Qdrant 데이터 소실) | `docker compose down -v` |

---

## Alembic 수동 작업

자동 마이그레이션은 컨테이너 시작 시 실행되지만, 수동으로도 가능:

```bash
# 새 마이그레이션 생성 (로컬 또는 서버에서)
docker compose exec backend alembic revision --autogenerate -m "add casting table"

# 적용
docker compose exec backend alembic upgrade head

# 한 단계 롤백
docker compose exec backend alembic downgrade -1

# 마이그레이션 이력
docker compose exec backend alembic history
```

> 새 마이그레이션 파일은 컨테이너 안에 생성되므로 호스트로 빼내려면 volume mount 추가가 깔끔합니다 (현재는 운영 우선이라 비활성). 보통은 **로컬에서 생성 후 git commit → push → 서버에서 pull**.

---

## Qdrant 헬스체크 / 상태

```bash
# 백엔드 컨테이너 안에서 Qdrant 호출
docker compose exec backend curl -s http://qdrant:6333/healthz
docker compose exec backend curl -s http://qdrant:6333/collections | jq .

# 또는 Qdrant 컨테이너 직접
docker compose exec qdrant wget -q -O - http://localhost:6333/readyz
```

Qdrant 데이터는 named volume `qdrant_data`에 영속 저장 — `docker compose down`해도 안 사라짐, `docker compose down -v`해야 삭제됨.

---

## 환경 변수 변경 시

`backend/.env.prod` 같은 env 파일을 수정한 경우:
```bash
docker compose up -d --force-recreate backend
```
빌드는 다시 안 하고 환경만 새로 주입해서 컨테이너 교체.

---

## 트러블슈팅

### 컨테이너가 자꾸 재시작될 때
```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
```
보통 alembic 실패(DB 접근 불가) 또는 환경 변수 누락이 원인.

### 백엔드가 PostgreSQL에 못 붙음
- `backend/.env.prod` 의 DATABASE_URL 비밀번호 / 호스트 확인
- 컨테이너 안에서 직접 테스트:
  ```bash
  docker compose exec backend python -c "
  import psycopg2, os
  url = os.environ['DATABASE_URL'].replace('postgresql+psycopg2', 'postgresql')
  conn = psycopg2.connect(url); print('OK')"
  ```
- 호스트 PG의 `pg_hba.conf` 가 도커 브리지 네트워크(172.x.x.x)를 허용하는지 확인

### 디스크 사용량 확인 / 정리
```bash
docker system df
docker image prune          # dangling 이미지 정리
docker system prune -a      # ⚠️ 사용 중인 컨테이너 외 전부 정리
```

### 컨테이너 메모리 사용량
```bash
docker stats --no-stream
```

---

## 보안 체크리스트 (운영 진입 전)

- [x] `backend/.env.prod` 의 `SECRET_KEY` 강력한 값(48자) ✓
- [x] `DATABASE_URL` 비밀번호 강력한 값(32자) + PG ALTER USER 적용 ✓
- [x] fail2ban 활성화 (SSH + PostgreSQL jail) ✓ — 5회/5분 실패 시 1시간 차단
- [x] PG `max_connections=20`, 백엔드 풀 `pool_size=8 + overflow=4` ✓
- [x] Lightsail Static IP 부착 (`3.35.101.121`) ✓
- [ ] **PG 5432 외부 노출은 유지** — DB 관리툴(TablePlus 등) 외부 접근용. 다만 방화벽 Source 를 `Any IPv4` → 본인 회사·집 IP 만 허용으로 좁히는 게 권장
- [ ] Qdrant API Key 설정 (`backend/.env.prod` 의 `QDRANT_API_KEY` 와 docker-compose 의 Qdrant `QDRANT__SERVICE__API_KEY` 환경변수)
- [ ] HTTPS 도입 (도메인 + Let's Encrypt). nginx 또는 Caddy 컨테이너 추가
- [ ] Lightsail snapshot 정기 백업 활성화 (Qdrant volume + PG 데이터 모두 보호)
- [ ] PG `pg_hba.conf` 의 `host all all 0.0.0.0/0 md5` 를 `scram-sha-256` 으로 변경 (md5는 구식)

## DB 외부 접속 정보 (관리툴용)

| 항목 | 값 |
|---|---|
| Host | `3.35.101.121` |
| Port | `5432` |
| Database | `actora` |
| User | `actora_user` |
| Password | `backend/.env.loc` 의 DATABASE_URL 참고 |
| SSL Mode | `prefer` 또는 `disable` (PG SSL 미설정) |

추천 클라이언트: **TablePlus** · **DBeaver** · **Postico 2** · **DataGrip** · **pgAdmin 4**
