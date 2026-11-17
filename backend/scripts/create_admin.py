"""Create initial admin user."""
import asyncio
import secrets
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import db
from utils.auth import hash_password
from models.user import UserInDB


async def create_admin():
    existing = await db.users.find_one({"username": "admin"})
    if existing:
        print("Admin user already exists. Skipping.")
        return

    first_password = secrets.token_urlsafe(12)
    admin = UserInDB(
        username="admin",
        email="admin@rhinodrishti.local",
        password_hash=hash_password(first_password),
        name="System Administrator",
        role="admin",
    )
    doc = admin.model_dump()
    await db.users.insert_one(doc)
    print(f"Admin user created successfully.")
    print(f"  Username: admin")
    print(f"  Password: {first_password}")
    print(f"  Role: admin")
    print(f"  CHANGE THIS PASSWORD IMMEDIATELY after first login.")


if __name__ == "__main__":
    asyncio.run(create_admin())
