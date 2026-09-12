import pytest

from src.ai.query_parser import QueryPlan, parse_query


def test_hospitals_in_f6():
    plan = parse_query("hospitals in F-6")

    assert plan == QueryPlan(
        intent="search",
        category="healthcare",
        subcategory="hospital",
        sector="F-6",
        limit=100,
    )


def test_restaurants_in_f7_without_hyphen():
    plan = parse_query("restaurants in F7")

    assert plan.intent == "search"
    assert plan.category == "food_drink"
    assert plan.subcategory == "restaurant"
    assert plan.sector == "F-7"
    assert plan.requires_origin is False
    assert plan.understood is True


def test_nearest_hospital_requires_origin():
    plan = parse_query("nearest hospital")

    assert plan.intent == "nearest"
    assert plan.category == "healthcare"
    assert plan.subcategory == "hospital"
    assert plan.requires_origin is True
    assert plan.limit == 1


def test_emergency_within_two_km():
    plan = parse_query("emergency within 2 km")

    assert plan.intent == "proximity"
    assert plan.category == "emergency"
    assert plan.radius_km == pytest.approx(2.0)
    assert plan.requires_origin is True


def test_banks_near_me_within_1500_metres():
    plan = parse_query("banks near me within 1500 m")

    assert plan.intent == "proximity"
    assert plan.category == "financial"
    assert plan.subcategory == "bank"
    assert plan.radius_km == pytest.approx(1.5)
    assert plan.requires_origin is True


def test_sector_only_query():
    plan = parse_query("show places in F 5")

    assert plan.intent == "search"
    assert plan.sector == "F-5"
    assert plan.category is None
    assert plan.understood is True


def test_nearby_restaurants_without_explicit_radius():
    plan = parse_query("restaurants nearby")

    assert plan.intent == "proximity"
    assert plan.category == "food_drink"
    assert plan.requires_origin is True
    assert plan.radius_km is None


def test_unsupported_query_is_not_fabricated():
    plan = parse_query("find me the best beautiful places")

    assert plan.understood is False
    assert plan.category is None
    assert plan.sector is None
    assert plan.message is not None


def test_empty_query_rejected():
    with pytest.raises(ValueError):
        parse_query("   ")


def test_non_string_query_rejected():
    with pytest.raises(TypeError):
        parse_query(None)