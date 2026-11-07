"""Explicit private-bucket provisioning; never grants public access."""

from botocore.exceptions import ClientError
from app.config import settings
from app.services.object_storage import S3PrivateObjectStore


def main():
    store = S3PrivateObjectStore()
    try:
        store.client.head_bucket(Bucket=store.bucket)
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) not in {"404", "NoSuchBucket", "NotFound"}:
            raise SystemExit("Bucket is unavailable; no permissions were changed") from None
        arguments = {"Bucket": store.bucket}
        if settings.S3_REGION != "us-east-1":
            arguments["CreateBucketConfiguration"] = {"LocationConstraint": settings.S3_REGION}
        store.client.create_bucket(**arguments)
    print("Private bucket is available. No public ACL or anonymous policy was configured.")


if __name__ == "__main__":
    main()
