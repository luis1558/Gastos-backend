from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.modules.expenses.defaults import DEFAULT_EXPENSE_CATEGORIES
from app.modules.expenses.models import ExpenseCategory
from app.modules.users.models import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed default expense categories.")
    parser.add_argument("--email", help="User email to seed categories for.")
    parser.add_argument("--user-id", help="User id to seed categories for.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.email and not args.user_id:
        raise SystemExit("Provide --email or --user-id.")

    db = SessionLocal()
    try:
        user = find_user(db, email=args.email, user_id=args.user_id)
        if user is None:
            raise SystemExit("User not found.")

        existing_slugs = {
            slug
            for slug in db.execute(
                select(ExpenseCategory.slug).where(ExpenseCategory.user_id == user.id),
            ).scalars()
        }

        created = 0
        for category in DEFAULT_EXPENSE_CATEGORIES:
            if category["slug"] in existing_slugs:
                continue
            db.add(
                ExpenseCategory(
                    user_id=user.id,
                    name=category["name"],
                    slug=category["slug"],
                    color=category["color"],
                ),
            )
            created += 1

        db.commit()
        print(f"Seed complete for {user.email}: {created} categories created.")
    finally:
        db.close()


def find_user(db, email: str | None, user_id: str | None) -> User | None:
    if user_id:
        return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    return db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()


if __name__ == "__main__":
    main()
