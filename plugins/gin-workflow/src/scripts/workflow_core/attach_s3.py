"""The s3 attachment store: private objects at <prefix>/<aa>/<sha256>, boto3 optional."""

from __future__ import annotations

from collections.abc import Collection

from .attach_store import StoreError, blob_path, check_path
from .models import DependencyUnavailableError

BATCH = 1000
MISSING = {"404", "NoSuchKey", "NotFound"}


def require_boto3():
    try:
        import boto3
    except ImportError as error:
        raise DependencyUnavailableError(
            "The 'boto3' package is required for attachments.store: s3. "
            "Install it with: python3 -m pip install boto3"
        ) from error
    return boto3


def _code(error: Exception) -> str:
    response = getattr(error, "response", None)
    return str(response.get("Error", {}).get("Code", "")) if isinstance(response, dict) else ""


def _describe(error: Exception) -> str:
    response = getattr(error, "response", None)
    message = response.get("Error", {}).get("Message", "") if isinstance(response, dict) else ""
    return f"{_code(error)} {message}".strip() or str(error)


class S3Store:
    name = "s3"

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
        client=None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            client = require_boto3().client("s3", endpoint_url=endpoint_url, region_name=region)
        self.client = client

    def _key(self, path: str) -> str:
        return f"{self.prefix}/{path}" if self.prefix else path

    def put(self, sha256: str, data: bytes) -> str:
        path = blob_path(sha256)
        key = self._key(path)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return path
        except Exception as error:
            if _code(error) not in MISSING:
                raise StoreError(f"cannot check s3 object {key}: {_describe(error)}") from error
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        except Exception as error:
            raise StoreError(f"cannot write s3 object {key}: {_describe(error)}") from error
        return path

    def get(self, path: str) -> bytes:
        key = self._key(check_path(path))
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as error:
            raise StoreError(f"cannot read s3 object {key}: {_describe(error)}") from error

    def paths(self) -> set[str]:
        start = f"{self.prefix}/" if self.prefix else ""
        found = set()
        try:
            pages = self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=start)
            for page in pages:
                for item in page.get("Contents", []):
                    try:
                        found.add(check_path(item["Key"][len(start):]))
                    except StoreError:
                        continue
        except Exception as error:
            raise StoreError(f"cannot list s3 bucket {self.bucket}: {_describe(error)}") from error
        return found

    def remove(self, paths: Collection[str]) -> None:
        keys = [self._key(check_path(path)) for path in paths]
        for start in range(0, len(keys), BATCH):
            objects = [{"Key": key} for key in keys[start : start + BATCH]]
            try:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects, "Quiet": True})
            except Exception as error:
                raise StoreError(f"cannot delete from s3 bucket {self.bucket}: {_describe(error)}") from error

    def push(self) -> str | None:
        return None

    def fetch(self) -> None:
        return None
