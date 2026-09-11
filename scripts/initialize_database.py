from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "geointel.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"


def initialize_database() -> None:
    """Create the Islamabad GeoIntel SQLite database from schema.sql."""

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(schema_sql)
        connection.commit()

    print("Islamabad GeoIntel database initialized successfully.")
    print(f"Database: {DATABASE_PATH}")


if __name__ == "__main__":
    initialize_database()