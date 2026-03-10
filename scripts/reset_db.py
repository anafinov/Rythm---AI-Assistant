"""Drop all tables and recreate them from scratch.

Usage:
    python scripts/reset_db.py          # asks for confirmation
    python scripts/reset_db.py --yes    # skip confirmation
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import Settings
from src.database import Base, create_engine


async def reset(database_url: str) -> None:
    engine = await create_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("All tables dropped.")
        await conn.run_sync(Base.metadata.create_all)
        print("All tables recreated.")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the Ritm database")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    settings = Settings()

    if not args.yes:
        answer = input(
            f"This will DROP all data in {settings.database_url}.\n"
            "Type 'yes' to confirm: "
        )
        if answer.strip().lower() != "yes":
            print("Aborted.")
            return

    asyncio.run(reset(settings.database_url))
    print("Done. Database is clean.")


if __name__ == "__main__":
    main()
