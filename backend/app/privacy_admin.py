"""Offline erasure operator. Planning is read-only; execution requires exact confirmations."""

import argparse
import json
from pathlib import Path
from uuid import UUID
from pydantic import ValidationError
from app.database import SessionLocal
from app.services.privacy_erasure import (
    ErasureError,
    ErasurePolicy,
    build_plan,
    digest,
    execute_plan,
    private_json,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "execute"])
    parser.add_argument("--request-id", type=UUID)
    parser.add_argument("--admin-id", type=UUID)
    parser.add_argument("--policy", type=Path)
    parser.add_argument(
        "--plan", type=Path, required=True, help="Private operator plan path; never publish this file"
    )
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--confirm-user-id", type=UUID)
    parser.add_argument(
        "--maintenance-confirmed",
        action="store_true",
        help="API and worker are stopped; approved backup/provider procedure is in place",
    )
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            if args.command == "plan":
                if not all((args.request_id, args.admin_id, args.policy)):
                    parser.error("Planning requires request-id, admin-id and an approved policy file")
                policy = ErasurePolicy.model_validate_json(args.policy.read_bytes())
                plan = build_plan(db, args.request_id, args.admin_id, policy)
                private_json(args.plan, plan)
                print(
                    json.dumps(
                        dict(
                            plan=str(args.plan),
                            plan_sha256=digest(plan),
                            counts={
                                name: value["count"]
                                for name, value in plan["snapshot"].items()
                                if "count" in value
                            },
                            sources=len(plan["objects"]),
                            records_changed=False,
                            unsupported_storage=any(item["backend"] != "local" for item in plan["objects"]),
                        )
                    )
                )
            else:
                if not all(
                    (
                        args.expected_plan_sha256,
                        args.confirm_user_id,
                        args.maintenance_confirmed,
                        args.receipt,
                    )
                ):
                    parser.error(
                        "Execution requires the reviewed plan hash, confirmed user, maintenance acknowledgement and receipt path"
                    )
                if args.receipt.exists():
                    raise ErasureError("Receipt already exists; refusing to repeat a completed operation")
                plan = json.loads(args.plan.read_text(encoding="utf-8"))
                receipt = execute_plan(
                    db,
                    plan,
                    args.expected_plan_sha256,
                    str(args.confirm_user_id),
                    args.maintenance_confirmed,
                    args.plan.with_suffix(".progress.json"),
                )
                private_json(args.receipt, receipt)
                print(
                    json.dumps(
                        dict(receipt=str(args.receipt), completed=True, backup_erasure_performed=False)
                    )
                )
    except ErasureError as error:
        raise SystemExit(str(error)) from None
    except (ValidationError, OSError, ValueError):
        raise SystemExit(
            "Invalid private plan/policy file or inaccessible operator output; no error contents were printed"
        ) from None
    except Exception:
        raise SystemExit(
            "Erasure stopped. Keep the private plan/progress for operator review; no error contents were printed."
        ) from None


if __name__ == "__main__":
    main()
