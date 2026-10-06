"""
Armazenamento de artefatos dos ciclos no Silo (S3 compatível).

Buckets:
  - patches   → diff de cada patch gerado
  - artifacts → relatório de avaliação e métricas do sandbox

Falhas de armazenamento nunca derrubam o ciclo.
"""
import io
import json
import os
from typing import Optional

from utils.logger import get_logger

logger = get_logger("storage")

BUCKET_PATCHES = os.getenv("MINIO_BUCKET_PATCHES", "patches")
BUCKET_ARTIFACTS = os.getenv("MINIO_BUCKET_ARTIFACTS", "artifacts")

_client = None
_buckets_ready: set = set()


def _enabled() -> bool:
    return os.getenv("STORAGE_ENABLED", "true").lower() in ("1", "true", "yes")


def _get_client():
    global _client
    if _client is None:
        from minio import Minio

        endpoint = os.getenv("MINIO_ENDPOINT", "http://silo:9000")
        secure = endpoint.startswith("https://")
        host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        _client = Minio(
            host,
            access_key=os.getenv("MINIO_ROOT_USER", ""),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", ""),
            secure=secure,
        )
    return _client


def _put(bucket: str, key: str, data: bytes, content_type: str) -> Optional[str]:
    if not _enabled():
        return None
    try:
        client = _get_client()
        if bucket not in _buckets_ready:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
            _buckets_ready.add(bucket)
        client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)
        return f"s3://{bucket}/{key}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ Silo indisponível ({bucket}/{key}): {e}")
        return None


def save_patch(cycle_id: str, diff: str) -> Optional[str]:
    return _put(BUCKET_PATCHES, f"{cycle_id}/patch.diff", (diff or "").encode("utf-8"), "text/x-diff")


def save_report(cycle_id: str, name: str, payload: dict) -> Optional[str]:
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    return _put(BUCKET_ARTIFACTS, f"{cycle_id}/{name}.json", body, "application/json")
