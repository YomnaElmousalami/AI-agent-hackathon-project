from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.insurance_db import init_db


DB_PATH = REPO_ROOT / "database" / "insurance.db"
BAK_PATH = REPO_ROOT / "database" / "insurance.db.bak"


def main() -> None:
    if DB_PATH.exists():
        try:
            BAK_PATH.write_bytes(DB_PATH.read_bytes())
            print(f"Backed up: {BAK_PATH}")
        except Exception as e:
            print(f"Warning: couldn't backup DB ({e}). Proceeding.")

        DB_PATH.unlink()
        print(f"Deleted: {DB_PATH}")

    init_db(str(DB_PATH))
    print(f"Recreated schema: {DB_PATH}")


if __name__ == "__main__":
    main()
