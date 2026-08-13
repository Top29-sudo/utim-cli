"""
One-off data repair: merge duplicate user rows created by the email case-sensitivity bug.

Run from repo root:
    DATABASE_URL=<your-db-url> python -m utim_cli.server.fix_duplicate_users

The bug (fixed in create_user/firebase_login/device_authorize) created one row per email
casing (e.g. "User@Example.com" AND "user@example.com"). This script:
  1. Groups users by lower(email) and finds groups with >1 row.
  2. Picks the KEEPER = oldest row (owns credits/history/subscription).
  3. Migrates firebase_uid / display_name / last_project_folder from duplicates.
  4. Deletes duplicate rows (all dependent tables are ON DELETE CASCADE).
"""
import sys
from sqlalchemy import func

from .db import SessionLocal, User, DeviceAuthCode, Credit, Transaction, UserSubscription


def main():
    db = SessionLocal()
    try:
        groups = (
            db.query(func.lower(User.email).label("lemail"), func.count(User.id).label("n"))
            .group_by(func.lower(User.email))
            .having(func.count(User.id) > 1)
            .all()
        )
        if not groups:
            print("No duplicate users found. Nothing to do.")
            return 0

        total_deleted = 0
        for lemail, _n in groups:
            rows = (
                db.query(User)
                .filter(func.lower(User.email) == lemail)
                .order_by(User.created_at.asc(), User.id.asc())
                .all()
            )
            keeper = rows[0]
            dups = rows[1:]
            print(f"\nGroup: {lemail}  keeper={keeper.email} (id={keeper.id}, created={keeper.created_at})")
            for d in dups:
                if d.firebase_uid and not keeper.firebase_uid:
                    keeper.firebase_uid = d.firebase_uid
                    print(f"  moved firebase_uid {d.firebase_uid}")
                if d.display_name and (not keeper.display_name or keeper.display_name.startswith("UTIM")):
                    keeper.display_name = d.display_name
                if d.last_project_folder and not keeper.last_project_folder:
                    keeper.last_project_folder = d.last_project_folder
                # Merge financial data (Credit.user_id is UNIQUE so we must fold the
                # duplicate's row into the keeper's row BEFORE deleting the user).
                d_credits = db.query(Credit).filter(Credit.user_id == d.id).first()
                k_credits = db.query(Credit).filter(Credit.user_id == keeper.id).first()
                if d_credits:
                    if k_credits:
                        k_credits.balance = (k_credits.balance or 0) + (d_credits.balance or 0)
                        k_credits.bonus_balance = (k_credits.bonus_balance or 0) + (d_credits.bonus_balance or 0)
                        k_credits.total_spent = (k_credits.total_spent or 0) + (d_credits.total_spent or 0)
                        k_credits.total_topped_up = (k_credits.total_topped_up or 0) + (d_credits.total_topped_up or 0)
                        k_credits.free_monthly_used = (k_credits.free_monthly_used or 0) + (d_credits.free_monthly_used or 0)
                        db.delete(d_credits)
                    else:
                        d_credits.user_id = keeper.id
                        d_credits.user = keeper
                # Merge subscription (keep the duplicate's sub only if keeper has none)
                d_sub = db.query(UserSubscription).filter(UserSubscription.user_id == d.id).first()
                k_sub = db.query(UserSubscription).filter(UserSubscription.user_id == keeper.id).first()
                if d_sub and not k_sub:
                    d_sub.user_id = keeper.id
                    d_sub.user = keeper
                # Re-point device codes at the keeper
                device_codes = db.query(DeviceAuthCode).filter(DeviceAuthCode.user_id == d.id).all()
                for c in device_codes:
                    c.user_id = keeper.id
                print(f"  -> deleting duplicate {d.email} (id={d.id}, api_key={d.api_key[:12]}...)")
                db.delete(d)
                total_deleted += 1

        db.commit()
        print(f"\nDone. Merged {len(groups)} groups, deleted {total_deleted} duplicate rows/accounts.")
        print("NOTE: If your CLI cached the deleted row's api_key, run firebase login again "
              "(the device-flow status endpoint returns the keeper's canonical api_key).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
