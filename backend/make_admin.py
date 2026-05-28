"""Назначает существующему юзеру роль админа.

Запуск: python make_admin.py alice@test.com
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User


def main(email: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"User with email '{email}' not found")
            return 1
        if user.is_admin:
            print(f"{email} is already admin")
            return 0
        user.is_admin = True
        db.commit()
        print(f"OK: {email} (id={user.id}) is now admin")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python make_admin.py <email>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
