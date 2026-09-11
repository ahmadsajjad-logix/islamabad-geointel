from src.ingestion.normalizer import (
    classify_feature,
    determine_sector,
    should_include_feature,
)


def test_strong_explicit_sector_assignment() -> None:
    properties = {
        "addr:sector": "F-6",
    }

    sector, status = determine_sector(properties)

    assert sector == "F-6"
    assert status == "strong_explicit"


def test_pilot_only_street_sector_assignment() -> None:
    properties = {
        "addr:street": "Street 25, F-7",
    }

    sector, status = determine_sector(properties)

    assert sector == "F-7"
    assert status == "street_pilot_only"


def test_mixed_sector_street_is_ambiguous() -> None:
    properties = {
        "addr:street": (
            "Service Road West G5;"
            "Service Road West F5"
        ),
    }

    sector, status = determine_sector(properties)

    assert sector is None
    assert status == "ambiguous"


def test_no_sector_evidence_remains_unassigned() -> None:
    properties = {
        "name": "Example Restaurant",
        "amenity": "restaurant",
    }

    sector, status = determine_sector(properties)

    assert sector is None
    assert status == "unassigned"


def test_emergency_no_is_not_emergency_service() -> None:
    properties = {
        "name": "Example Dental Clinic",
        "amenity": "dentist",
        "emergency": "no",
    }

    category, subcategory = classify_feature(properties)

    assert category == "healthcare"
    assert subcategory == "dentist"


def test_police_is_emergency_category() -> None:
    properties = {
        "name": "Example Police Station",
        "amenity": "police",
    }

    category, subcategory = classify_feature(properties)

    assert category == "emergency"
    assert subcategory == "police"


def test_restaurant_classification() -> None:
    properties = {
        "name": "Example Restaurant",
        "amenity": "restaurant",
    }

    category, subcategory = classify_feature(properties)

    assert category == "food_drink"
    assert subcategory == "restaurant"


def test_shop_classification() -> None:
    properties = {
        "name": "Example Shoe Shop",
        "shop": "shoes",
    }

    category, subcategory = classify_feature(properties)

    assert category == "retail"
    assert subcategory == "shoes"


def test_healthcare_classification() -> None:
    properties = {
        "name": "Example Hospital",
        "amenity": "hospital",
    }

    category, subcategory = classify_feature(properties)

    assert category == "healthcare"
    assert subcategory == "hospital"


def test_named_descriptive_building_is_included() -> None:
    properties = {
        "name": "Example Government Building",
        "building": "office",
    }

    assert should_include_feature(properties) is True


def test_unnamed_generic_building_is_excluded() -> None:
    properties = {
        "building": "residential",
        "addr:street": "Example Street",
    }

    assert should_include_feature(properties) is False


def test_address_only_object_is_excluded() -> None:
    properties = {
        "addr:housenumber": "10",
        "addr:street": "Example Street",
    }

    assert should_include_feature(properties) is False