"""Seeds one demo user and three items.

Idempotent — safe to run repeatedly — via the same check-before-insert
pattern auth_service.register_user uses for duplicate emails: re-running this
against a database that already has the demo user is a no-op, not an error.

Run from backend/:
    python -m scripts.seed
"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Item, User
from app.db.session import AsyncSessionLocal

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demopassword123"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            # Plain ASCII hyphen, not an em-dash: some Windows console
            # codepages raise UnicodeEncodeError on print() for non-ASCII
            # characters rather than just rendering them wrong.
            print(f"Demo user {DEMO_EMAIL!r} already exists (id={existing.id}) - nothing to do.")
            return

        user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD))
        db.add(user)
        # flush, not commit: assigns user.id (needed for the items' owner_id
        # below) without ending the transaction, so the user and their three
        # items land in a single commit — all four rows or none of them.
        await db.flush()

        items = [
            Item(
                title="Welcome item",
                description="Your first item — try editing or deleting it.",
                owner_id=user.id,
            ),
            Item(
                title="Second item",
                description="Pagination needs at least a couple of rows to be worth testing.",
                owner_id=user.id,
            ),
            Item(
                title="Third item",
                description=None,
                owner_id=user.id,
            ),
        ]
        db.add_all(items)
        await db.commit()

        print(f"Seeded demo user {DEMO_EMAIL!r} (password: {DEMO_PASSWORD!r}) with 3 items.")


if __name__ == "__main__":
    asyncio.run(seed())
