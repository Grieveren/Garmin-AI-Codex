"""Initial setup wizard placeholder."""
from pathlib import Path

from app.database import run_migrations


def main() -> None:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    run_migrations()
    print("Database initialised at", data_dir)


if __name__ == "__main__":
    main()
