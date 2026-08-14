from functools import lru_cache
from pathlib import Path

import boto3

from wildfirewatch.config import get_settings


@lru_cache
def get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def upload_file(local_path: str | Path, bucket: str, key: str) -> str:
    get_s3_client().upload_file(str(local_path), bucket, key)
    return f"s3://{bucket}/{key}"


def download_file(bucket: str, key: str, local_path: str | Path) -> Path:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    get_s3_client().download_file(bucket, key, str(local_path))
    return local_path


def presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
