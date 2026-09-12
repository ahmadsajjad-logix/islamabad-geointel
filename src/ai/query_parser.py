"""Deterministic natural-language query parser for Islamabad GeoIntel.

This module converts supported user phrases into a constrained query plan.
It does not execute SQL and does not invent POIs, sectors, or coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


SUPPORTED_CATEGORIES = {
    "accommodation",
    "education",
    "emergency",
    "financial",
    "food_drink",
    "government",
    "healthcare",
    "other_amenity",
    "professional_services",
    "public_service",
    "recreation",
    "religion",
    "retail",
    "transport",
}

CATEGORY_ALIASES = {
    # Healthcare
    "hospital": ("healthcare", "hospital"),
    "hospitals": ("healthcare", "hospital"),
    "clinic": ("healthcare", "clinic"),
    "clinics": ("healthcare", "clinic"),
    "healthcare": ("healthcare", None),
    "health care": ("healthcare", None),

    # Food and drink
    "restaurant": ("food_drink", "restaurant"),
    "restaurants": ("food_drink", "restaurant"),
    "cafe": ("food_drink", "cafe"),
    "cafes": ("food_drink", "cafe"),
    "coffee": ("food_drink", None),
    "food": ("food_drink", None),

    # Financial
    "bank": ("financial", "bank"),
    "banks": ("financial", "bank"),
    "atm": ("financial", "atm"),
    "atms": ("financial", "atm"),
    "financial": ("financial", None),

    # Emergency
    "emergency": ("emergency", None),
    "police": ("emergency", "police"),

    # Education
    "school": ("education", "school"),
    "schools": ("education", "school"),
    "college": ("education", None),
    "colleges": ("education", None),
    "university": ("education", "university"),
    "universities": ("education", "university"),
    "education": ("education", None),

    # Transport
    "fuel": ("transport", "fuel"),
    "petrol": ("transport", "fuel"),
    "transport": ("transport", None),

    # Other broad categories
    "hotel": ("accommodation", None),
    "hotels": ("accommodation", None),
    "accommodation": ("accommodation", None),
    "shop": ("retail", None),
    "shops": ("retail", None),
    "retail": ("retail", None),
    "government": ("government", None),
    "recreation": ("recreation", None),
    "religious": ("religion", None),
    "religion": ("religion", None),
}


@dataclass(frozen=True)
class QueryPlan:
    """Structured representation of a supported natural-language request."""

    intent: str
    category: str | None = None
    subcategory: str | None = None
    sector: str | None = None
    name: str | None = None
    radius_km: float | None = None
    limit: int = 100
    requires_origin: bool = False
    understood: bool = True
    message: str | None = None


def _normalise_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _extract_sector(text: str) -> str | None:
    """Extract supported Islamabad pilot sectors such as F-5, F5 or F 5."""

    match = re.search(r"\bf[\s-]?([567])\b", text, flags=re.IGNORECASE)

    if match is None:
        return None

    return f"F-{match.group(1)}"


def _extract_category(text: str) -> tuple[str | None, str | None]:
    """Return normalized category and optional subcategory."""

    # Longest aliases first prevents a shorter phrase taking precedence.
    for alias in sorted(CATEGORY_ALIASES, key=len, reverse=True):
        if re.search(
            rf"(?<!\w){re.escape(alias)}(?!\w)",
            text,
            flags=re.IGNORECASE,
        ):
            return CATEGORY_ALIASES[alias]

    return None, None


def _extract_radius_km(text: str) -> float | None:
    """Extract a positive distance expressed in km, kilometre(s), m or metre(s)."""

    km_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:km|kms|kilometre|kilometres|kilometer|kilometers)\b",
        text,
        flags=re.IGNORECASE,
    )

    if km_match is not None:
        value = float(km_match.group(1))
        return value if value > 0 else None

    metre_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:m|metre|metres|meter|meters)\b",
        text,
        flags=re.IGNORECASE,
    )

    if metre_match is not None:
        value = float(metre_match.group(1))
        return value / 1000.0 if value > 0 else None

    return None


def parse_query(text: str) -> QueryPlan:
    """Parse supported natural language into a safe structured query plan.

    Examples:
        "hospitals in F-6"
        "restaurants in F7"
        "emergency within 2 km"
        "nearest hospital"
        "banks near me within 1500 m"

    Geographic queries deliberately contain no invented coordinates.
    The caller must provide the user's selected/current map origin.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string.")

    cleaned = _normalise_text(text)

    if not cleaned:
        raise ValueError("Query must contain non-whitespace characters.")

    category, subcategory = _extract_category(cleaned)
    sector = _extract_sector(cleaned)
    radius_km = _extract_radius_km(cleaned)

    nearest = bool(re.search(r"\bnearest\b", cleaned))
    proximity_language = bool(
        re.search(
            r"\b(?:near me|nearby|within|around|closest)\b",
            cleaned,
        )
    )

    if nearest:
        intent = "nearest"
        requires_origin = True
        limit = 1
    elif radius_km is not None or proximity_language:
        intent = "proximity"
        requires_origin = True
        limit = 100
    else:
        intent = "search"
        requires_origin = False
        limit = 100

    if category is None and sector is None:
        return QueryPlan(
            intent=intent,
            radius_km=radius_km,
            limit=limit,
            requires_origin=requires_origin,
            understood=False,
            message=(
                "I could not identify a supported category or pilot sector "
                "from this query."
            ),
        )

    return QueryPlan(
        intent=intent,
        category=category,
        subcategory=subcategory,
        sector=sector,
        radius_km=radius_km,
        limit=limit,
        requires_origin=requires_origin,
    )