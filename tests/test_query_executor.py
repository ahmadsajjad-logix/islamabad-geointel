import pytest

from src.ai.query_executor import (
    DEFAULT_PROXIMITY_RADIUS_KM,
    execute_query_plan,
)
from src.ai.query_parser import parse_query
from src.database.connection import get_connection


F6_LATITUDE = 33.7286213
F6_LONGITUDE = 73.0735239


@pytest.fixture
def connection():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def test_hospitals_in_f6(connection):
    plan = parse_query("hospitals in F-6")

    results = execute_query_plan(connection, plan)

    assert len(results) == 1
    assert results[0]["name"] == "Kulsum International Hospital"
    assert results[0]["category"] == "healthcare"
    assert results[0]["subcategory"] == "hospital"
    assert results[0]["sector"] == "F-6"


def test_food_drink_in_f6(connection):
    plan = parse_query("food in F-6")

    results = execute_query_plan(connection, plan)

    assert len(results) == 10
    assert all(row["category"] == "food_drink" for row in results)
    assert all(row["sector"] == "F-6" for row in results)


def test_sector_only_f5(connection):
    plan = parse_query("show places in F-5")

    results = execute_query_plan(connection, plan)

    assert len(results) == 32
    assert all(row["sector"] == "F-5" for row in results)


def test_nearest_hospital_from_f6_reference(connection):
    plan = parse_query("nearest hospital")

    results = execute_query_plan(
        connection,
        plan,
        latitude=F6_LATITUDE,
        longitude=F6_LONGITUDE,
    )

    assert len(results) == 1
    assert results[0]["category"] == "healthcare"
    assert results[0]["subcategory"] == "hospital"
    assert results[0]["name"] == "FM Dental Clinic"
    assert results[0]["distance_km"] == pytest.approx(
        0.387,
        abs=0.002,
    )


def test_emergency_within_two_km_from_f6_reference(connection):
    plan = parse_query("emergency within 2 km")

    results = execute_query_plan(
        connection,
        plan,
        latitude=F6_LATITUDE,
        longitude=F6_LONGITUDE,
    )

    assert len(results) == 1
    assert results[0]["category"] == "emergency"
    assert results[0]["subcategory"] == "police"
    assert results[0]["name"] == "تھانہ کوہسار"
    assert results[0]["distance_km"] == pytest.approx(
        1.421,
        abs=0.002,
    )


def test_nearby_restaurants_uses_default_radius(connection):
    plan = parse_query("restaurants nearby")

    assert plan.radius_km is None
    assert DEFAULT_PROXIMITY_RADIUS_KM == 2.0

    results = execute_query_plan(
        connection,
        plan,
        latitude=F6_LATITUDE,
        longitude=F6_LONGITUDE,
    )

    assert isinstance(results, list)

    for row in results:
        assert row["category"] == "food_drink"
        assert row["subcategory"] == "restaurant"
        assert row["distance_km"] <= DEFAULT_PROXIMITY_RADIUS_KM


def test_geographic_query_without_origin_rejected(connection):
    plan = parse_query("nearest hospital")

    with pytest.raises(
        ValueError,
        match="requires a geographic origin",
    ):
        execute_query_plan(connection, plan)


def test_unsupported_query_returns_no_results(connection):
    plan = parse_query("find me the best beautiful places")

    results = execute_query_plan(connection, plan)

    assert plan.understood is False
    assert results == []