import pytest

from src.geo.distance import haversine_km, haversine_m


def test_same_point_distance_is_zero() -> None:
    distance = haversine_km(
        33.7322095,
        73.0887796,
        33.7322095,
        73.0887796,
    )

    assert distance == pytest.approx(0.0)


def test_known_islamabad_distance() -> None:
    """
    Verify the distance calculation using the validated OSM reference
    coordinates for Islamabad sectors F-5 and F-6.

    This test checks the mathematical distance calculation only.
    The reference nodes are not treated as sector boundaries.
    """

    distance = haversine_km(
        33.7322095,
        73.0887796,
        33.7286213,
        73.0735239,
    )

    assert 1.4 < distance < 1.6


def test_metres_and_kilometres_are_consistent() -> None:
    distance_km = haversine_km(
        33.7322095,
        73.0887796,
        33.7204333,
        73.0561174,
    )

    distance_m = haversine_m(
        33.7322095,
        73.0887796,
        33.7204333,
        73.0561174,
    )

    assert distance_m == pytest.approx(distance_km * 1000.0)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (91.0, 73.0),
        (-91.0, 73.0),
        (33.0, 181.0),
        (33.0, -181.0),
    ],
)
def test_invalid_coordinates_are_rejected(
    latitude: float,
    longitude: float,
) -> None:
    with pytest.raises(ValueError):
        haversine_km(
            latitude,
            longitude,
            33.72,
            73.06,
        )
import sqlite3
from pathlib import Path

from src.database.repository import upsert_poi
from src.search.search_service import (
    nearest_pois,
    search_within_radius,
)


def test_search_within_radius_filters_and_sorts() -> None:
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
        "sector": None,
        "sector_status": "unassigned",
        "address": "Islamabad",
        "tags_json": "{}",
        "source": "OpenStreetMap",
    }

    near_poi = {
        **base_poi,
        "osm_id": 2001,
        "name": "Near Hospital",
        "latitude": 33.7288,
        "longitude": 73.0735,
    }

    farther_poi = {
        **base_poi,
        "osm_id": 2002,
        "name": "Farther Hospital",
        "latitude": 33.7330,
        "longitude": 73.0735,
    }

    outside_poi = {
        **base_poi,
        "osm_id": 2003,
        "name": "Outside Hospital",
        "latitude": 33.7500,
        "longitude": 73.0735,
    }

    cafe_poi = {
        **base_poi,
        "osm_id": 2004,
        "name": "Near Cafe",
        "category": "food_drink",
        "subcategory": "cafe",
        "latitude": 33.7290,
        "longitude": 73.0735,
    }

    upsert_poi(connection, near_poi)
    upsert_poi(connection, farther_poi)
    upsert_poi(connection, outside_poi)
    upsert_poi(connection, cafe_poi)

    rows = search_within_radius(
        connection,
        latitude=33.7286213,
        longitude=73.0735239,
        radius_km=1.0,
        category="healthcare",
        limit=10,
    )

    assert len(rows) == 2
    assert rows[0]["name"] == "Near Hospital"
    assert rows[1]["name"] == "Farther Hospital"
    assert rows[0]["distance_km"] < rows[1]["distance_km"]
    assert rows[0]["distance_km"] < 1.0
    assert rows[1]["distance_km"] < 1.0

    connection.close()


def test_search_within_radius_respects_limit() -> None:
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

    for osm_id, latitude in (
        (3001, 33.7287),
        (3002, 33.7288),
        (3003, 33.7289),
    ):
        upsert_poi(
            connection,
            {
                "osm_type": "node",
                "osm_id": osm_id,
                "name": f"POI {osm_id}",
                "category": "retail",
                "subcategory": "shop",
                "latitude": latitude,
                "longitude": 73.0735,
                "sector": None,
                "sector_status": "unassigned",
                "address": "Islamabad",
                "tags_json": "{}",
                "source": "OpenStreetMap",
            },
        )

    rows = search_within_radius(
        connection,
        latitude=33.7286213,
        longitude=73.0735239,
        radius_km=1.0,
        limit=2,
    )

    assert len(rows) == 2
    assert rows[0]["distance_km"] <= rows[1]["distance_km"]

    connection.close()


@pytest.mark.parametrize(
    "radius_km",
    [
        0.0,
        -1.0,
    ],
)
def test_search_within_radius_rejects_invalid_radius(
    radius_km: float,
) -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    with pytest.raises(
        ValueError,
        match="radius_km must be greater than 0",
    ):
        search_within_radius(
            connection,
            latitude=33.7286213,
            longitude=73.0735239,
            radius_km=radius_km,
        )

    connection.close()
def test_nearest_pois_returns_nearest_matches() -> None:
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

    for osm_id, name, latitude in (
        (4001, "Nearest Hospital", 33.7287),
        (4002, "Second Hospital", 33.7300),
        (4003, "Third Hospital", 33.7330),
    ):
        upsert_poi(
            connection,
            {
                "osm_type": "node",
                "osm_id": osm_id,
                "name": name,
                "category": "healthcare",
                "subcategory": "hospital",
                "latitude": latitude,
                "longitude": 73.0735,
                "sector": None,
                "sector_status": "unassigned",
                "address": "Islamabad",
                "tags_json": "{}",
                "source": "OpenStreetMap",
            },
        )

    rows = nearest_pois(
        connection,
        latitude=33.7286213,
        longitude=73.0735239,
        category="healthcare",
        subcategory="hospital",
        max_radius_km=5.0,
        limit=2,
    )

    assert len(rows) == 2
    assert rows[0]["name"] == "Nearest Hospital"
    assert rows[1]["name"] == "Second Hospital"
    assert rows[0]["distance_km"] < rows[1]["distance_km"]

    connection.close()


def test_nearest_pois_returns_empty_when_no_match_in_radius() -> None:
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

    upsert_poi(
        connection,
        {
            "osm_type": "node",
            "osm_id": 5001,
            "name": "Distant Hospital",
            "category": "healthcare",
            "subcategory": "hospital",
            "latitude": 33.8000,
            "longitude": 73.0735,
            "sector": None,
            "sector_status": "unassigned",
            "address": "Islamabad",
            "tags_json": "{}",
            "source": "OpenStreetMap",
        },
    )

    rows = nearest_pois(
        connection,
        latitude=33.7286213,
        longitude=73.0735239,
        category="healthcare",
        subcategory="hospital",
        max_radius_km=1.0,
    )

    assert rows == []

    connection.close()


def test_nearest_pois_rejects_invalid_arguments() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    with pytest.raises(
        ValueError,
        match="max_radius_km must be greater than 0",
    ):
        nearest_pois(
            connection,
            latitude=33.7286213,
            longitude=73.0735239,
            max_radius_km=0,
        )

    with pytest.raises(
        ValueError,
        match="limit must be at least 1",
    ):
        nearest_pois(
            connection,
            latitude=33.7286213,
            longitude=73.0735239,
            limit=0,
        )

    connection.close()