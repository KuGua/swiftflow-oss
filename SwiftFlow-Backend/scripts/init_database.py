from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from database import DATABASE_URL, IS_SQLITE, init_db_and_seed  # noqa: E402


def main() -> None:
    init_db_and_seed()
    backend_name = "SQLite" if IS_SQLITE else "PostgreSQL/Other"
    print(f"Database initialized successfully.")
    print(f"Backend: {backend_name}")
    print(f"URL: {DATABASE_URL}")


if __name__ == "__main__":
    main()
