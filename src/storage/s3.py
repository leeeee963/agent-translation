"""S3-compatible object storage. Works with AWS S3, Cloudflare R2, B2, etc."""

from __future__ import annotations

from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from src.storage.base import FileStorage


class S3Storage(FileStorage):
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "us-east-1",
    ) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def upload_file(self, key: str, source_path: Path) -> None:
        self.client.upload_file(str(source_path), self.bucket, key)

    def download_to_path(self, key: str, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(target_path))

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefix(self, prefix: str) -> int:
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"
        count = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if not objs:
                continue
            self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": objs}
            )
            count += len(objs)
        return count

    def get_url(
        self, key: str, filename: str | None = None, expires_in: int = 3600
    ) -> str:
        params: dict = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self.client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )

    def is_redirect_url(self) -> bool:
        return True
