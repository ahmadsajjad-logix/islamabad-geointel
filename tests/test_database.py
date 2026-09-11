import sqlite3
from pathlib import Path

from src.database.repository import (
    complete_import_run,
    create_import_run,
    poi_exists,
    upsert_poi,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


def create_test_connection() -> sqlite3.Connection:
    """Create an isolated in-memory database using production schema."""

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema_sql)

    return connection


def make_test_poi() -> dict:
    """Return one valid normalized POI for repository testing."""

    return {
        "osm_type": "node",
        "osm_id": 999999999,
        "name": "Test Hospital",
        "category": "healthcare",
        "subcategory": "hospital",
        "latitude": 33.7300,
        "longitude": 73.0700,
        "sector": "F-6",
        "sector_status": "strong_explicit",
        "address": "F-6, Islamabad",
        "tags_json": '{"amenity": "hospital"}',
        "source": "OpenStreetMap",
    }


def test_production_schema_creates_expected_tables() -> None:
    connection = create_test_connection()

    try:
        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        assert "pois" in tables
        assert "sectors" in tables
        assert "import_runs" in tables
    finally:
        connection.close()


def test_poi_insert_and_identity_lookup() -> None:
    connection = create_test_connection()

    try:
        poi = make_test_poi()

        assert poi_exists(
            connection,
            poi["osm_type"],
            poi["osm_id"],
        ) is False

        result = upsert_poi(connection, poi)

        assert result == "inserted"

        assert poi_exists(
            connection,
            poi["osm_type"],
            poi["osm_id"],
        ) is True

        count = connection.execute(
            "SELECT COUNT(*) FROM pois"
        ).fetchone()[0]

        assert count == 1
    finally:
        connection.close()


def test_poi_upsert_updates_without_duplicate() -> None:
    connection = create_test_connection()

    try:
        poi = make_test_poi()

        first_result = upsert_poi(connection, poi)

        original = connection.execute(
            """
            SELECT imported_at
            FROM pois
            WHERE osm_type = ?
              AND osm_id = ?
            """,
            (
                poi["osm_type"],
                poi["osm_id"],
            ),
        ).fetchone()

        updated_poi = dict(poi)
        updated_poi["name"] = "Updated Test Hospital"
        updated_poi["sector"] = None
        updated_poi["sector_status"] = "unassigned"

        second_result = upsert_poi(
            connection,
            updated_poi,
        )

        stored = connection.execute(
            """
            SELECT *
            FROM pois
            WHERE osm_type = ?
              AND osm_id = ?
            """,
            (
                poi["osm_type"],
                poi["osm_id"],
            ),
        ).fetchone()

        count = connection.execute(
            "SELECT COUNT(*) FROM pois"
        ).fetchone()[0]

        assert first_result == "inserted"
        assert second_result == "updated"
        assert count == 1
        assert stored["name"] == "Updated Test Hospital"
        assert stored["sector"] is None
        assert stored["sector_status"] == "unassigned"
        assert stored["imported_at"] == original["imported_at"]
    finally:
        connection.close()


def test_import_run_audit_record() -> None:
    connection = create_test_connection()

    try:
        run_id = create_import_run(
            connection,
            source="OpenStreetMap",
            area="Automated test",
        )

        initial = connection.execute(
            """
            SELECT *
            FROM import_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

        assert initial["status"] == "running"

        complete_import_run(
            connection,
            import_run_id=run_id,
            records_received=10,
            records_inserted=8,
            records_updated=2,
        )

        completed = connection.execute(
            """
            SELECT *
            FROM import_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

        assert completed["status"] == "completed"
        assert completed["records_received"] == 10
        assert completed["records_inserted"] == 8
        assert completed["records_updated"] == 2
        assert completed["completed_at"] is not None
    finally:
        connection.close()