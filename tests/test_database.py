import sqlite3
from pathlib import Path

import pytest

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
def test_search_pois_filters_and_name_matching() -> None:
    from src.database.repository import search_pois

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "database"
        / "schema.sql"
    )
    connection.executescript(
        schema_path.read_text(encoding="utf-8")
    )

    base_poi = {
        "osm_type": "node",
        "category": "healthcare",
        "subcategory": "hospital",
        "latitude": 33.72,
        "longitude": 73.06,
        "sector": "F-6",
        "sector_status": "strong_explicit",
        "address": "Islamabad",
        "tags_json": "{}",
        "source": "OpenStreetMap",
    }

    first_poi = {
        **base_poi,
        "osm_id": 1001,
        "name": "Alpha Hospital",
    }

    second_poi = {
        **base_poi,
        "osm_id": 1002,
        "name": "Beta Medical Centre",
        "subcategory": "clinic",
        "sector": "F-7",
    }

    third_poi = {
        **base_poi,
        "osm_id": 1003,
        "name": "Alpha Cafe",
        "category": "food_drink",
        "subcategory": "cafe",
    }

    upsert_poi(connection, first_poi)
    upsert_poi(connection, second_poi)
    upsert_poi(connection, third_poi)

    healthcare_rows = search_pois(
        connection,
        category="healthcare",
    )
    assert len(healthcare_rows) == 2

    f6_healthcare_rows = search_pois(
        connection,
        category="healthcare",
        sector="F-6",
    )
    assert len(f6_healthcare_rows) == 1
    assert f6_healthcare_rows[0]["name"] == "Alpha Hospital"

    clinic_rows = search_pois(
        connection,
        subcategory="clinic",
    )
    assert len(clinic_rows) == 1
    assert clinic_rows[0]["name"] == "Beta Medical Centre"

    name_rows = search_pois(
        connection,
        name="ALPHA",
    )
    assert len(name_rows) == 2

    connection.close()


def test_search_pois_rejects_invalid_limit() -> None:
    from src.database.repository import search_pois

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    with pytest.raises(
        ValueError,
        match="limit must be at least 1",
    ):
        search_pois(
            connection,
            limit=0,
        )

    connection.close()
def test_count_pois_by_category() -> None:
    from src.database.repository import count_pois_by_category

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "database"
        / "schema.sql"
    )
    connection.executescript(
        schema_path.read_text(encoding="utf-8")
    )

    pois = [
        {
            "osm_type": "node",
            "osm_id": 6001,
            "name": "Hospital One",
            "category": "healthcare",
            "subcategory": "hospital",
            "latitude": 33.72,
            "longitude": 73.06,
            "sector": "F-6",
            "sector_status": "strong_explicit",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
        {
            "osm_type": "node",
            "osm_id": 6002,
            "name": "Clinic One",
            "category": "healthcare",
            "subcategory": "clinic",
            "latitude": 33.73,
            "longitude": 73.07,
            "sector": "F-7",
            "sector_status": "strong_explicit",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
        {
            "osm_type": "node",
            "osm_id": 6003,
            "name": "Cafe One",
            "category": "food_drink",
            "subcategory": "cafe",
            "latitude": 33.74,
            "longitude": 73.08,
            "sector": "F-6",
            "sector_status": "strong_explicit",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
    ]

    for poi in pois:
        upsert_poi(connection, poi)

    rows = count_pois_by_category(connection)

    counts = {
        row["category"]: row["poi_count"]
        for row in rows
    }

    assert counts == {
        "healthcare": 2,
        "food_drink": 1,
    }

    f6_rows = count_pois_by_category(
        connection,
        sector="F-6",
    )

    f6_counts = {
        row["category"]: row["poi_count"]
        for row in f6_rows
    }

    assert f6_counts == {
        "food_drink": 1,
        "healthcare": 1,
    }

    connection.close()


def test_count_pois_by_sector_excludes_unassigned() -> None:
    from src.database.repository import count_pois_by_sector

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    schema_path = (
        Path(__file__).resolve().parents[1]
        / "database"
        / "schema.sql"
    )
    connection.executescript(
        schema_path.read_text(encoding="utf-8")
    )

    pois = [
        {
            "osm_type": "node",
            "osm_id": 7001,
            "name": "F6 Hospital",
            "category": "healthcare",
            "subcategory": "hospital",
            "latitude": 33.72,
            "longitude": 73.06,
            "sector": "F-6",
            "sector_status": "strong_explicit",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
        {
            "osm_type": "node",
            "osm_id": 7002,
            "name": "F7 Hospital",
            "category": "healthcare",
            "subcategory": "hospital",
            "latitude": 33.73,
            "longitude": 73.07,
            "sector": "F-7",
            "sector_status": "street_pilot_only",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
        {
            "osm_type": "node",
            "osm_id": 7003,
            "name": "Unassigned Hospital",
            "category": "healthcare",
            "subcategory": "hospital",
            "latitude": 33.74,
            "longitude": 73.08,
            "sector": None,
            "sector_status": "unassigned",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
    ]

    for poi in pois:
        upsert_poi(connection, poi)

    rows = count_pois_by_sector(connection)

    counts = {
        row["sector"]: row["poi_count"]
        for row in rows
    }

    assert counts == {
        "F-6": 1,
        "F-7": 1,
    }

    healthcare_rows = count_pois_by_sector(
        connection,
        category="healthcare",
    )

    healthcare_counts = {
        row["sector"]: row["poi_count"]
        for row in healthcare_rows
    }

    assert healthcare_counts == {
        "F-6": 1,
        "F-7": 1,
    }

    connection.close()