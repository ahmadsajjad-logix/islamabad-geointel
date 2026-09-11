import json
import re
from typing import Any


PILOT_SECTORS = {"F-5", "F-6", "F-7"}

PILOT_SECTOR_PATTERN = re.compile(
    r"(?<![A-Z0-9])F[\s-]?(5|6|7)(?:[/\s-]?[1-4])?(?!\d)",
    re.IGNORECASE,
)

ALL_SECTOR_PATTERN = re.compile(
    r"(?<![A-Z0-9])([A-Z])[\s-]?(\d{1,2})(?:[/\s-]?([1-4]))?(?!\d)",
    re.IGNORECASE,
)

STRONG_SECTOR_KEYS = (
    "addr:sector",
    "addr:suburb",
    "addr:neighbourhood",
    "addr:place",
    "is_in:suburb",
    "is_in:neighbourhood",
    "is_in",
    "addr:full",
)

ADDRESS_KEYS = (
    "addr:housenumber",
    "addr:street",
    "addr:suburb",
    "addr:city",
    "addr:postcode",
)

CATEGORY_FAMILY_KEYS = (
    "amenity",
    "shop",
    "healthcare",
    "emergency",
    "tourism",
    "office",
    "leisure",
)


def parse_osm_identity(osm_reference: str) -> tuple[str, int]:
    """
    Convert an Overpass Turbo GeoJSON @id such as 'node/123'
    into ('node', 123).
    """

    if not osm_reference or "/" not in osm_reference:
        raise ValueError(
            f"Invalid or missing OSM reference: {osm_reference!r}"
        )

    osm_type, osm_id_text = osm_reference.split("/", 1)

    if osm_type not in {"node", "way", "relation"}:
        raise ValueError(f"Unsupported OSM type: {osm_type!r}")

    try:
        osm_id = int(osm_id_text)
    except ValueError as exc:
        raise ValueError(
            f"Invalid OSM numeric ID: {osm_id_text!r}"
        ) from exc

    return osm_type, osm_id


def extract_name(properties: dict[str, Any]) -> str | None:
    """
    Return the best available human-readable POI name.
    """

    for key in ("name", "name:en"):
        value = properties.get(key)

        if value is not None:
            text = str(value).strip()

            if text:
                return text

    return None


def extract_address(properties: dict[str, Any]) -> str | None:
    """
    Build a readable address while preserving addr:full when available.
    """

    full_address = properties.get("addr:full")

    if full_address is not None:
        text = str(full_address).strip()

        if text:
            return text

    parts = []

    for key in ADDRESS_KEYS:
        value = properties.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text and text not in parts:
            parts.append(text)

    if not parts:
        return None

    return ", ".join(parts)


def _pilot_sectors_in_value(value: Any) -> set[str]:
    """
    Extract F-5, F-6 and F-7 references from one value.
    """

    if value is None:
        return set()

    return {
        f"F-{match.group(1)}"
        for match in PILOT_SECTOR_PATTERN.finditer(str(value))
    }


def _all_base_sectors_in_value(value: Any) -> set[str]:
    """
    Extract base Islamabad-style sector references such as F-5 or G-5.
    """

    if value is None:
        return set()

    return {
        f"{match.group(1).upper()}-{match.group(2)}"
        for match in ALL_SECTOR_PATTERN.finditer(str(value))
    }


def determine_sector(
    properties: dict[str, Any],
) -> tuple[str | None, str]:
    """
    Determine pilot-sector attribution from explicit OSM tag evidence.

    Returns:
        (sector, status)

    Possible statuses:
        strong_explicit
        street_pilot_only
        ambiguous
        unassigned

    Radius-source membership and nearest reference points are deliberately
    not used because Phase 2 testing showed that they can misclassify POIs.
    """

    strong_sectors: set[str] = set()

    for key in STRONG_SECTOR_KEYS:
        strong_sectors.update(
            _pilot_sectors_in_value(properties.get(key))
        )

    if len(strong_sectors) == 1:
        return next(iter(strong_sectors)), "strong_explicit"

    if len(strong_sectors) > 1:
        return None, "ambiguous"

    street = properties.get("addr:street")

    if street:
        pilot_references = _pilot_sectors_in_value(street)

        if pilot_references:
            all_references = _all_base_sectors_in_value(street)
            other_references = all_references - PILOT_SECTORS

            if (
                len(pilot_references) == 1
                and not other_references
            ):
                return (
                    next(iter(pilot_references)),
                    "street_pilot_only",
                )

            return None, "ambiguous"

    return None, "unassigned"


def should_include_feature(properties: dict[str, Any]) -> bool:
    """
    Decide whether an acquired OSM object should enter the searchable
    POI/entity dataset.

    Include:
      - objects carrying one of the seven primary category-family tags;
      - named objects classified by building=* or landuse=*.

    Exclude:
      - unnamed address-only objects;
      - unnamed generic/residential buildings without POI evidence.

    Exclusion from the POI table does not remove the object from the
    preserved raw acquisition files.
    """

    has_category_family = any(
        properties.get(key) is not None
        for key in CATEGORY_FAMILY_KEYS
    )

    if has_category_family:
        return True

    name = extract_name(properties)

    if (
        name
        and (
            properties.get("building") is not None
            or properties.get("landuse") is not None
        )
    ):
        return True

    return False


def classify_feature(
    properties: dict[str, Any],
) -> tuple[str | None, str | None]:
    """
    Map OSM tags to the Islamabad GeoIntel category taxonomy.

    Precedence is explicit so that an object carrying multiple OSM
    category-family tags produces one normalized category/subcategory.
    """

    amenity = properties.get("amenity")
    shop = properties.get("shop")
    healthcare = properties.get("healthcare")
    emergency = properties.get("emergency")
    tourism = properties.get("tourism")
    office = properties.get("office")
    leisure = properties.get("leisure")

    # Public-safety / emergency facilities.
    if amenity in {
        "police",
        "fire_station",
        "ambulance_station",
    }:
        return "emergency", str(amenity)

    # A negative emergency tag is not an emergency facility.
    if emergency and emergency != "no":
        return "emergency", str(emergency)

    # Healthcare takes precedence over duplicate amenity tagging.
    if healthcare:
        return "healthcare", str(healthcare)

    if amenity in {
        "hospital",
        "clinic",
        "doctors",
        "dentist",
        "pharmacy",
        "veterinary",
    }:
        return "healthcare", str(amenity)

    if amenity in {
        "restaurant",
        "cafe",
        "fast_food",
        "food_court",
        "ice_cream",
    }:
        return "food_drink", str(amenity)

    if amenity in {
        "bank",
        "atm",
        "bureau_de_change",
    }:
        return "financial", str(amenity)

    if amenity in {
        "school",
        "college",
        "university",
        "library",
    }:
        return "education", str(amenity)

    if amenity == "place_of_worship":
        return "religion", str(amenity)

    if amenity in {
        "fuel",
        "bus_station",
        "taxi",
        "car_rental",
        "bicycle_rental",
        "parking",
    }:
        return "transport", str(amenity)

    if shop:
        return "retail", str(shop)

    if tourism in {
        "hotel",
        "guest_house",
        "hostel",
    }:
        return "accommodation", str(tourism)

    if office in {
        "government",
        "diplomatic",
    }:
        return "government", str(office)

    if office:
        return "professional_services", str(office)

    if leisure:
        return "recreation", str(leisure)

    if tourism:
        return "recreation", str(tourism)

    if amenity in {
        "post_office",
        "courthouse",
        "townhall",
    }:
        return "public_service", str(amenity)

    if amenity:
        return "other_amenity", str(amenity)

    # Named descriptive entities retained by the inclusion rule.
    name = extract_name(properties)

    if name:
        building = properties.get("building")
        landuse = properties.get("landuse")

        if building:
            return "other_amenity", str(building)

        if landuse:
            return "other_amenity", str(landuse)

    return None, None


def normalize_feature(feature: dict[str, Any]) -> dict[str, Any]:
    """
    Convert one acquired Overpass Turbo GeoJSON feature into the
    Islamabad GeoIntel normalized POI representation.

    This function does not decide whether the object should be imported.
    Call should_include_feature() before importing a normalized object.
    """

    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}

    osm_reference = properties.get("@id")
    osm_type, osm_id = parse_osm_identity(osm_reference)

    if geometry.get("type") != "Point":
        raise ValueError(
            f"{osm_reference}: expected Point geometry, "
            f"got {geometry.get('type')!r}"
        )

    coordinates = geometry.get("coordinates")

    if (
        not isinstance(coordinates, (list, tuple))
        or len(coordinates) < 2
    ):
        raise ValueError(
            f"{osm_reference}: missing or invalid coordinates"
        )

    longitude = float(coordinates[0])
    latitude = float(coordinates[1])

    sector, sector_status = determine_sector(properties)
    category, subcategory = classify_feature(properties)

    return {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "name": extract_name(properties),
        "category": category,
        "subcategory": subcategory,
        "latitude": latitude,
        "longitude": longitude,
        "sector": sector,
        "sector_status": sector_status,
        "address": extract_address(properties),
        "tags_json": json.dumps(
            properties,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "source": "OpenStreetMap",
    }