"""Real MinIO regression in a unique synthetic-only bucket; never uses the app bucket."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from dotenv import dotenv_values
import boto3
from botocore.config import Config

root = Path(__file__).resolve().parents[1]
values = dotenv_values(root / ".env")
endpoint = f"http://127.0.0.1:{int(values.get('MINIO_PORT', 59000))}"
bucket = "caregap-test-" + uuid4().hex
access, secret = values["MINIO_ROOT_USER"], values["MINIO_ROOT_PASSWORD"]
client = boto3.client(
    "s3",
    endpoint_url=endpoint,
    region_name="us-east-1",
    aws_access_key_id=access,
    aws_secret_access_key=secret,
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
client.create_bucket(Bucket=bucket)
try:
    environment = {
        **os.environ,
        "CAREGAP_S3_INTEGRATION": "1",
        "STORAGE_BACKEND": "s3",
        "S3_ENDPOINT_URL": endpoint,
        "S3_BUCKET": bucket,
        "S3_ACCESS_KEY_ID": access,
        "S3_SECRET_ACCESS_KEY": secret,
        "SECRET_KEY": "synthetic-object-test-secret-not-for-deployment",
        "ENVIRONMENT": "test",
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_s3_integration.py"],
        cwd=root / "backend",
        env=environment,
    )
finally:
    assert bucket.startswith("caregap-test-") and len(bucket) == 45
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
    client.delete_bucket(Bucket=bucket)
print("Isolated synthetic object-store bucket removed; application objects were not accessed.")
raise SystemExit(result.returncode)
