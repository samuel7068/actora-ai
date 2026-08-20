"""파일 저장소 추상화 — 로컬 디스크 / S3 호환 오브젝트 스토리지.

왜 필요한가
─────────────────────────────────────────────────────────────
개발 PC 와 운영 서버는 DB·Qdrant 를 공유하지만 파일은 각자 디스크에 있었다.
그래서 한쪽에서 등록하면 반대쪽 검색에는 나오는데 재생은 404 가 났고,
사람이 rsync 스크립트를 돌려 메꿔야 했다. 삭제는 더 까다로웠다.

파일을 **한 버킷**에 두면 그 문제가 원인부터 사라진다. 두 환경이 같은
버킷을 보므로 동기화라는 개념 자체가 없어진다.

키 규칙
─────────────────────────────────────────────────────────────
DB 의 media_path 를 그대로 오브젝트 키로 쓴다. 덕분에 전환 시 DB 를
건드리지 않는다.

    talent/{account_id}/portfolio/{account_id}_{media_id}.mp4
    talent/{account_id}/profile/{filename}          원본 (얼굴 임베딩용)
    talent/{account_id}/profile/thumb/{stem}.webp   썸네일 (화면 표시용)
    rag/{account_id}_{media_id}.txt

구현 선택
─────────────────────────────────────────────────────────────
S3_BUCKET 이 설정되어 있으면 S3Storage, 없으면 LocalStorage.
로컬 폴백을 남겨 두는 이유는 자격증명 없이도 개발·테스트가 돌아가야 하고,
버킷 장애 시 원인을 좁힐 수 있어야 하기 때문이다.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Iterator, Optional, Protocol
from urllib.parse import quote

from src.config import get_settings

logger = logging.getLogger(__name__)

# 스트리밍 청크 (업로드 검증 / 다운로드 공통)
CHUNK = 1024 * 1024  # 1 MB


class StorageError(RuntimeError):
    """저장소 조작 실패 — 호출자가 HTTP 응답으로 변환한다."""


class Storage(Protocol):
    """파일 저장소 인터페이스.

    키(key)는 항상 저장소 루트 기준 상대 경로이고 앞에 '/' 를 붙이지 않는다.
    """

    def put_file(self, local_path: Path, key: str, content_type: str = "") -> int: ...
    def put_bytes(self, data: bytes, key: str, content_type: str = "") -> int: ...
    def get_bytes(self, key: str) -> bytes: ...
    def download_to(self, key: str, local_path: Path) -> Path: ...
    def iter_chunks(self, key: str) -> Iterator[bytes]: ...
    def exists(self, key: str) -> bool: ...
    def size(self, key: str) -> int: ...
    def delete(self, key: str) -> bool: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def list_keys(self, prefix: str = "") -> list[str]: ...
    def presigned_url(
        self, key: str, *, content_type: str = "", filename: str = ""
    ) -> Optional[str]: ...


# ─────────────────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────────────────
def normalize_key(key: str) -> str:
    """키를 정규화하고 경로 탈출을 막는다.

    '..' 세그먼트는 버킷 밖(로컬 모드에서는 UPLOAD_DIR 밖)을 가리킬 수 있으므로
    저장소 진입 지점에서 한 번 차단한다.
    """
    k = (key or "").strip().strip("/")
    if not k:
        raise StorageError("EMPTY_KEY")
    parts = [p for p in k.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise StorageError(f"INVALID_KEY:{key!r}")
    return "/".join(parts)


def guess_content_type(key: str, fallback: str = "application/octet-stream") -> str:
    return mimetypes.guess_type(key)[0] or fallback


def content_disposition(filename: str, disposition: str = "inline") -> str:
    """RFC 5987 형식의 Content-Disposition 값.

    S3 는 헤더 값을 ISO-8859-1 로 표현할 수 없으면 InvalidArgument 400 을 낸다.
    영상 원본 파일명은 대부분 한글이므로("배종옥.김태우.mp4") ASCII 로만 쓰면
    재생이 통째로 깨진다. 그래서 ASCII 폴백과 UTF-8 인코딩을 함께 보낸다.
        inline; filename="_.mp4"; filename*=UTF-8''%EB%B0%B0...
    구형 클라이언트는 filename 을, 그 외에는 filename* 를 쓴다.
    """
    name = (filename or "").replace("\r", " ").replace("\n", " ").strip()
    if not name:
        return disposition
    # ASCII 폴백 — 표현 불가 문자는 '_' 로. 따옴표·역슬래시는 헤더를 깨뜨린다.
    ascii_name = "".join(
        c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in name
    ) or "file"
    quoted = quote(name, safe="")
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}"


# ─────────────────────────────────────────────────────────
# 로컬 디스크
# ─────────────────────────────────────────────────────────
class LocalStorage:
    """UPLOAD_DIR 아래 파일로 저장. S3 자격증명이 없는 환경의 폴백."""

    backend = "local"

    def __init__(self, root: str):
        self.root = Path(root)

    def path_for(self, key: str) -> Path:
        return self.root / normalize_key(key)

    def put_file(self, local_path: Path, key: str, content_type: str = "") -> int:
        dest = self.path_for(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # 같은 파일시스템이면 move, 아니면 copy — 분석 임시파일을 옮겨오는 용도
        shutil.move(str(local_path), str(dest))
        return dest.stat().st_size

    def put_bytes(self, data: bytes, key: str, content_type: str = "") -> int:
        dest = self.path_for(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return len(data)

    def get_bytes(self, key: str) -> bytes:
        path = self.path_for(key)
        if not path.exists():
            raise StorageError(f"NOT_FOUND:{key}")
        return path.read_bytes()

    def download_to(self, key: str, local_path: Path) -> Path:
        src = self.path_for(key)
        if not src.exists():
            raise StorageError(f"NOT_FOUND:{key}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, local_path)
        return local_path

    def iter_chunks(self, key: str) -> Iterator[bytes]:
        path = self.path_for(key)
        if not path.exists():
            raise StorageError(f"NOT_FOUND:{key}")
        with path.open("rb") as f:
            while chunk := f.read(CHUNK):
                yield chunk

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def size(self, key: str) -> int:
        path = self.path_for(key)
        return path.stat().st_size if path.exists() else 0

    def delete(self, key: str) -> bool:
        path = self.path_for(key)
        try:
            if path.is_dir():
                shutil.rmtree(path)
                return True
            if path.exists():
                os.remove(path)
                return True
        except OSError as e:
            logger.warning(f"로컬 파일 삭제 실패 ({key}): {e}")
        return False

    def delete_prefix(self, prefix: str) -> int:
        path = self.path_for(prefix)
        if not path.exists():
            return 0
        n = sum(1 for p in path.rglob("*") if p.is_file()) if path.is_dir() else 1
        self.delete(prefix)
        return n

    def list_keys(self, prefix: str = "") -> list[str]:
        base = self.root / normalize_key(prefix) if prefix else self.root
        if not base.exists():
            return []
        return sorted(
            str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file()
        )

    def presigned_url(
        self, key: str, *, content_type: str = "", filename: str = ""
    ) -> Optional[str]:
        # 로컬은 서명 URL 이 없다 → 호출자가 직접 stream 한다
        return None


# ─────────────────────────────────────────────────────────
# S3 호환 (AWS S3 / Lightsail 버킷 / R2)
# ─────────────────────────────────────────────────────────
class S3Storage:
    """S3 호환 오브젝트 스토리지."""

    backend = "s3"

    def __init__(
        self,
        bucket: str,
        *,
        region: str,
        endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        presign_ttl: int = 21600,
    ):
        import boto3
        from botocore.config import Config as BotoConfig

        self.bucket = bucket
        self.presign_ttl = presign_ttl
        kwargs: dict = {
            "region_name": region,
            # presigned URL 이 SigV4 로 서명되어야 Lightsail·R2 모두에서 통한다.
            #
            # addressing_style 을 반드시 고정한다. 기본값 "auto" 는 호스트를
            # {bucket}.s3.amazonaws.com (리전 없는 글로벌 엔드포인트) 로 만들면서
            # 서명은 실제 리전으로 계산해, presigned URL 이 SignatureDoesNotMatch
            # 403 을 받는다. API 호출(put/get)은 리다이렉트로 넘어가 성공하므로
            # "업로드는 되는데 재생만 안 되는" 형태로만 드러난다.
            "config": BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        # 키를 주지 않으면 boto3 가 환경변수·IAM 역할을 찾는다 (EC2/Lightsail 권장 경로)
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key
        self.client = boto3.client("s3", **kwargs)

    # ── 쓰기 ──
    def put_file(self, local_path: Path, key: str, content_type: str = "") -> int:
        k = normalize_key(key)
        size = Path(local_path).stat().st_size
        extra = {"ContentType": content_type or guess_content_type(k)}
        try:
            # upload_file 은 큰 파일을 자동으로 멀티파트 분할한다
            self.client.upload_file(str(local_path), self.bucket, k, ExtraArgs=extra)
        except Exception as e:
            raise StorageError(f"UPLOAD_FAILED:{k}: {e}") from e
        # 로컬 임시파일은 올린 뒤 정리 — put_file 은 "옮긴다" 는 의미
        try:
            os.remove(local_path)
        except OSError:
            pass
        return size

    def put_bytes(self, data: bytes, key: str, content_type: str = "") -> int:
        k = normalize_key(key)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=k,
                Body=data,
                ContentType=content_type or guess_content_type(k),
            )
        except Exception as e:
            raise StorageError(f"UPLOAD_FAILED:{k}: {e}") from e
        return len(data)

    # ── 읽기 ──
    def get_bytes(self, key: str) -> bytes:
        k = normalize_key(key)
        try:
            return self.client.get_object(Bucket=self.bucket, Key=k)["Body"].read()
        except Exception as e:
            raise StorageError(f"NOT_FOUND:{k}: {e}") from e

    def download_to(self, key: str, local_path: Path) -> Path:
        k = normalize_key(key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, k, str(local_path))
        except Exception as e:
            raise StorageError(f"NOT_FOUND:{k}: {e}") from e
        return local_path

    def iter_chunks(self, key: str) -> Iterator[bytes]:
        k = normalize_key(key)
        try:
            body: BinaryIO = self.client.get_object(Bucket=self.bucket, Key=k)["Body"]
        except Exception as e:
            raise StorageError(f"NOT_FOUND:{k}: {e}") from e
        while chunk := body.read(CHUNK):
            yield chunk

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=normalize_key(key))
            return True
        except Exception:
            return False

    def size(self, key: str) -> int:
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=normalize_key(key))
            return int(head.get("ContentLength") or 0)
        except Exception:
            return 0

    # ── 삭제 ──
    def delete(self, key: str) -> bool:
        k = normalize_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=k)
            return True
        except Exception as e:
            logger.warning(f"오브젝트 삭제 실패 ({k}): {e}")
            return False

    def delete_prefix(self, prefix: str) -> int:
        """접두사 아래 전부 삭제 (계정 탈퇴 시 talent/{id}/ 통째로)."""
        p = normalize_key(prefix).rstrip("/") + "/"
        deleted = 0
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=p):
                batch = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if not batch:
                    continue
                # delete_objects 는 한 번에 1000개까지
                for i in range(0, len(batch), 1000):
                    self.client.delete_objects(
                        Bucket=self.bucket, Delete={"Objects": batch[i : i + 1000]}
                    )
                deleted += len(batch)
        except Exception as e:
            logger.warning(f"접두사 삭제 실패 ({p}): {e}")
        return deleted

    def list_keys(self, prefix: str = "") -> list[str]:
        p = normalize_key(prefix) if prefix else ""
        keys: list[str] = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=p):
                keys.extend(o["Key"] for o in page.get("Contents", []))
        except Exception as e:
            logger.warning(f"목록 조회 실패 ({p}): {e}")
        return sorted(keys)

    # ── 서빙 ──
    def presigned_url(
        self, key: str, *, content_type: str = "", filename: str = ""
    ) -> Optional[str]:
        """브라우저가 버킷에서 직접 받아갈 임시 URL.

        백엔드는 권한 검사만 하고 이 URL 로 302 를 준다. 영상 바이트가
        백엔드를 거치지 않으므로 nginx X-Accel-Redirect 가 필요 없다.
        """
        k = normalize_key(key)
        params: dict = {"Bucket": self.bucket, "Key": k}
        if content_type:
            params["ResponseContentType"] = content_type
        if filename:
            params["ResponseContentDisposition"] = content_disposition(filename)
        try:
            return self.client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=self.presign_ttl
            )
        except Exception as e:
            logger.error(f"presigned URL 생성 실패 ({k}): {e}")
            return None


# ─────────────────────────────────────────────────────────
# 팩토리
# ─────────────────────────────────────────────────────────
@lru_cache
def get_storage() -> Storage:
    """설정에 맞는 저장소를 돌려준다 (프로세스당 1개 재사용).

    boto3 client 는 생성 비용이 크고 스레드 안전하므로 캐시한다.
    """
    config = get_settings()
    if config.S3_BUCKET:
        store = S3Storage(
            config.S3_BUCKET,
            region=config.S3_REGION,
            endpoint_url=config.S3_ENDPOINT_URL,
            access_key=config.S3_ACCESS_KEY_ID,
            secret_key=config.S3_SECRET_ACCESS_KEY,
            presign_ttl=config.S3_PRESIGN_TTL,
        )
        logger.info(
            f"파일 저장소=S3 bucket={config.S3_BUCKET} region={config.S3_REGION}"
            + (f" endpoint={config.S3_ENDPOINT_URL}" if config.S3_ENDPOINT_URL else "")
        )
        return store
    logger.warning(
        f"파일 저장소=로컬 디스크 ({config.UPLOAD_DIR}) — S3_BUCKET 미설정. "
        "개발 PC 와 운영 서버의 파일이 분리되므로 한쪽에서 올린 파일은 "
        "반대쪽에서 재생되지 않는다."
    )
    return LocalStorage(config.UPLOAD_DIR)
