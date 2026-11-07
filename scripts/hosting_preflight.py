"""Read-only configuration checks. Never connects to or mutates a cloud service."""

import argparse
import json
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def check(path):
    values = dotenv_values(path)
    required = [
        "SECRET_KEY",
        "DATABASE_URL",
        "CORS_ORIGINS",
        "RATE_LIMIT_STORAGE_URI",
        "S3_ENDPOINT_URL",
        "S3_REGION",
        "S3_BUCKET",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "S3_ENCRYPTION_REVIEW_REFERENCE",
    ]
    missing = [
        name
        for name in required
        if not values.get(name)
        or any(
            marker in values[name]
            for marker in [
                "YOUR_",
                "PROJECT_REF",
                "POOLER_HOST",
                "URL_ENCODED_",
                "CHANGE_ME",
            ]
        )
    ]
    issues = ["missing_or_placeholder:" + name for name in missing]
    if not missing:
        try:
            from app.config import Settings
            from app.hosted import validate_hosted

            configured = {
                key: value for key, value in values.items() if value is not None
            }
            configured["CORS_ORIGINS"] = json.loads(configured["CORS_ORIGINS"])
            settings = Settings(_env_file=None, **configured)
            validate_hosted(settings)
            if settings.ENVIRONMENT != "production":
                issues.append("production_mode_required")
        except Exception:  # noqa: BLE001 -- configuration exceptions may contain private connection strings
            issues.append("configuration_or_verification_check_failed")
    if values.get("S3_MANAGED_ENCRYPTION_VERIFIED", "").lower() != "true":
        issues.append("managed_encryption_review_pending")
    return {
        "mode": "offline_configuration_preflight",
        "configuration_complete": not issues,
        "issues": issues,
        "cloud_connections_tested": False,
        "bucket_privacy_verified": False,
        "external_approvals_verified": False,
        "data_transferred": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, required=True)
    args = parser.parse_args()
    if not args.env.is_file():
        raise SystemExit("Private configuration file not found")
    result = check(args.env)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["configuration_complete"] else 2)


if __name__ == "__main__":
    main()
