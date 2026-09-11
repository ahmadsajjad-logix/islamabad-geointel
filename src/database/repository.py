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
def search_pois(
    connection: sqlite3.Connection,
    *,
    category: str | None = None,
    subcategory: str | None = None,
    sector: str | None = None,
    name: str | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    """
    Search POIs using optional normalized database filters.

    All supplied filters are combined with AND.

    Args:
        connection:
            Open SQLite connection.

        category:
            Exact normalized category match.

        subcategory:
            Exact normalized subcategory match.

        sector:
            Exact normalized sector match.

        name:
            Case-insensitive partial POI name match.

        limit:
            Maximum number of rows returned.

    Returns:
        Matching POI rows ordered by name and database ID.
    """

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    conditions: list[str] = []
    parameters: list[Any] = []

    if category is not None:
        conditions.append("category = ?")
        parameters.append(category)

    if subcategory is not None:
        conditions.append("subcategory = ?")
        parameters.append(subcategory)

    if sector is not None:
        conditions.append("sector = ?")
        parameters.append(sector)

    if name is not None:
        cleaned_name = name.strip()

        if not cleaned_name:
            raise ValueError(
                "name must contain non-whitespace characters."
            )

        conditions.append(
            "LOWER(COALESCE(name, '')) LIKE LOWER(?)"
        )
        parameters.append(f"%{cleaned_name}%")

    sql = """
        SELECT
            id,
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
        FROM pois
    """

    if conditions:
        sql += "\nWHERE " + "\n  AND ".join(conditions)

    sql += """
        ORDER BY
            CASE WHEN name IS NULL THEN 1 ELSE 0 END,
            name COLLATE NOCASE,
            id
        LIMIT ?
    """

    parameters.append(limit)

    return connection.execute(
        sql,
        parameters,
    ).fetchall()
def count_pois_by_category(
    connection: sqlite3.Connection,
    *,
    sector: str | None = None,
) -> list[sqlite3.Row]:
    """
    Count searchable POIs grouped by normalized category.

    If sector is supplied, only POIs with that stored sector
    attribution are included.
    """

    if sector is None:
        return connection.execute(
            """
            SELECT
                category,
                COUNT(*) AS poi_count
            FROM pois
            GROUP BY category
            ORDER BY poi_count DESC, category
            """
        ).fetchall()

    return connection.execute(
        """
        SELECT
            category,
            COUNT(*) AS poi_count
        FROM pois
        WHERE sector = ?
        GROUP BY category
        ORDER BY poi_count DESC, category
        """,
        (sector,),
    ).fetchall()


def count_pois_by_sector(
    connection: sqlite3.Connection,
    *,
    category: str | None = None,
) -> list[sqlite3.Row]:
    """
    Count POIs grouped by stored sector attribution.

    Only POIs with a non-NULL sector are included. Unassigned and
    ambiguous POIs remain in the database but are not falsely assigned
    to a sector for statistical purposes.

    If category is supplied, only that normalized category is counted.
    """

    if category is None:
        return connection.execute(
            """
            SELECT
                sector,
                COUNT(*) AS poi_count
            FROM pois
            WHERE sector IS NOT NULL
            GROUP BY sector
            ORDER BY poi_count DESC, sector
            """
        ).fetchall()

    return connection.execute(
        """
        SELECT
            sector,
            COUNT(*) AS poi_count
        FROM pois
        WHERE
            sector IS NOT NULL
            AND category = ?
        GROUP BY sector
        ORDER BY poi_count DESC, sector
        """,
        (category,),
    ).fetchall()
