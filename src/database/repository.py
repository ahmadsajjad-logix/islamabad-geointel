from datetime import datetime, timezone
import sqlite3
from typing import Any


def utc_now_iso() -> str:
    """
    Return the current UTC timestamp in ISO 8601 format.
    """

    return datetime.now(timezone.utc).isoformat()


def create_import_run(
    connection: sqlite3.Connection,
    source: str,
    area: str,
) -> int:
    """
    Create an import_runs record and return its database ID.
    """

    started_at = utc_now_iso()

    cursor = connection.execute(
        """
        INSERT INTO import_runs (
            source,
            area,
            started_at,
            status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            source,
            area,
            started_at,
            "running",
        ),
    )

    if cursor.lastrowid is None:
        raise RuntimeError("Failed to create import run.")

    return cursor.lastrowid


def complete_import_run(
    connection: sqlite3.Connection,
    import_run_id: int,
    records_received: int,
    records_inserted: int,
    records_updated: int,
) -> None:
    """
    Mark an import run as successfully completed.
    """

    connection.execute(
        """
        UPDATE import_runs
        SET
            completed_at = ?,
            records_received = ?,
            records_inserted = ?,
            records_updated = ?,
            status = ?,
            error_message = NULL
        WHERE id = ?
        """,
        (
            utc_now_iso(),
            records_received,
            records_inserted,
            records_updated,
            "completed",
            import_run_id,
        ),
    )


def fail_import_run(
    connection: sqlite3.Connection,
    import_run_id: int,
    error_message: str,
) -> None:
    """
    Mark an import run as failed.
    """

    connection.execute(
        """
        UPDATE import_runs
        SET
            completed_at = ?,
            status = ?,
            error_message = ?
        WHERE id = ?
        """,
        (
            utc_now_iso(),
            "failed",
            error_message,
            import_run_id,
        ),
    )


def poi_exists(
    connection: sqlite3.Connection,
    osm_type: str,
    osm_id: int,
) -> bool:
    """
    Return True when the OSM object already exists in the POI table.
    """

    row = connection.execute(
        """
        SELECT 1
        FROM pois
        WHERE osm_type = ?
          AND osm_id = ?
        LIMIT 1
        """,
        (
            osm_type,
            osm_id,
        ),
    ).fetchone()

    return row is not None


def upsert_poi(
    connection: sqlite3.Connection,
    poi: dict[str, Any],
) -> str:
    """
    Insert or update one normalized POI.

    Returns:
        "inserted" when a new OSM object was created.
        "updated" when an existing OSM object was refreshed.
    """

    required_fields = (
        "osm_type",
        "osm_id",
        "category",
        "latitude",
        "longitude",
        "sector_status",
        "tags_json",
        "source",
    )

    missing_fields = [
        field
        for field in required_fields
        if poi.get(field) is None
    ]

    if missing_fields:
        raise ValueError(
            "POI is missing required field(s): "
            + ", ".join(missing_fields)
        )

    exists = poi_exists(
        connection,
        poi["osm_type"],
        poi["osm_id"],
    )

    timestamp = utc_now_iso()

    connection.execute(
        """
        INSERT INTO pois (
            osm_type,
            osm_id,
            name,
            category,
            subcategory,
            latitude,
            longitude,
            sector,
            sector_status,
            address,
            tags_json,
            source,
            imported_at,
            updated_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(osm_type, osm_id)
        DO UPDATE SET
            name = excluded.name,
            category = excluded.category,
            subcategory = excluded.subcategory,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            sector = excluded.sector,
            sector_status = excluded.sector_status,
            address = excluded.address,
            tags_json = excluded.tags_json,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        (
            poi["osm_type"],
            poi["osm_id"],
            poi.get("name"),
            poi["category"],
            poi.get("subcategory"),
            poi["latitude"],
            poi["longitude"],
            poi.get("sector"),
            poi["sector_status"],
            poi.get("address"),
            poi["tags_json"],
            poi["source"],
            timestamp,
            timestamp,
        ),
    )

    return "updated" if exists else "inserted"