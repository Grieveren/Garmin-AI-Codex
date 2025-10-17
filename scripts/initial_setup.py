"""Initial setup wizard placeholder."""
from pathlib import Path

from app.database import Base, engine


def main() -> None:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print("Database initialised at", data_dir)


if __name__ == "__main__":
    main()
