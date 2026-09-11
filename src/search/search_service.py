import sqlite3
from typing import Any

from src.database.repository import search_pois
from src.geo.distance import haversine_km


def search_within_radius(
    connection: sqlite3.Connection,
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    category: str | None = None,
    subcategory: str | None = None,
    sector: str | None = None,
    name: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Search for POIs within a geographic radius.

    Repository filters are applied first. Geographic distance is then
    calculated from the supplied WGS84 coordinate to each candidate POI.

    Results are ordered from nearest to farthest.

    The sector filter uses only the sector attribution already stored in
    the database. Geographic proximity is never used to infer a sector.
    """

    if radius_km <= 0:
        raise ValueError("radius_km must be greater than 0.")

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    # Validate the search origin even when the database contains no
    # candidate POIs.
    haversine_km(
        latitude,
        longitude,
        latitude,
        longitude,
    )

    candidates = search_pois(
        connection,
        category=category,
        subcategory=subcategory,
        sector=sector,
        name=name,
        limit=100000,
    )

    matches: list[dict[str, Any]] = []

    for row in candidates:
        distance_km = haversine_km(
            latitude,
            longitude,
            row["latitude"],
            row["longitude"],
        )

        if distance_km <= radius_km:
            result = dict(row)
            result["distance_km"] = distance_km
            matches.append(result)

    matches.sort(
        key=lambda item: (
            item["distance_km"],
            (item["name"] or "").casefold(),
            item["id"],
        )
    )

    return matches[:limit]
def nearest_pois(
    connection: sqlite3.Connection,
    *,
    latitude: float,
    longitude: float,
    category: str | None = None,
    subcategory: str | None = None,
    sector: str | None = None,
    name: str | None = None,
    max_radius_km: float = 10.0,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """
    Return the nearest matching POIs within a maximum search radius.

    Results are ordered from nearest to farthest.

    The maximum radius prevents a nearest-place query from silently
    returning a geographically distant result when no nearby match
    exists.

    Examples:
        Nearest hospital:
            category="healthcare",
            subcategory="hospital"

        Nearest emergency service:
            category="emergency"

        Nearest restaurant:
            category="food_drink",
            subcategory="restaurant"
    """

    if max_radius_km <= 0:
        raise ValueError(
            "max_radius_km must be greater than 0."
        )

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    return search_within_radius(
        connection,
        latitude=latitude,
        longitude=longitude,
        radius_km=max_radius_km,
        category=category,
        subcategory=subcategory,
        sector=sector,
        name=name,
        limit=limit,
    )
