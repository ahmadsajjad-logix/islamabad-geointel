from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "database" / "geointel.db"


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the Islamabad GeoIntel SQLite database.

    Rows are returned as sqlite3.Row objects so callers can access
    columns by name as well as by position.
    """

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Islamabad GeoIntel database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection