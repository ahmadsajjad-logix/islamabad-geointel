"""Execution layer for Islamabad GeoIntel natural-language query plans."""

from __future__ import annotations

import sqlite3
from typing import Any

from src.ai.query_parser import QueryPlan
from src.database.repository import search_pois
from src.search.search_service import nearest_pois, search_within_radius


DEFAULT_PROXIMITY_RADIUS_KM = 2.0
DEFAULT_NEAREST_MAX_RADIUS_KM = 10.0


def execute_query_plan(
    connection: sqlite3.Connection,
    plan: QueryPlan,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> list[dict[str, Any]]:
    """Execute a validated QueryPlan using the existing search engines.

    Geographic query plans require an explicit origin supplied by the
    caller. Coordinates are never inferred or fabricated here.
    """

    if not isinstance(plan, QueryPlan):
        raise TypeError("plan must be a QueryPlan.")

    if not plan.understood:
        return []

    if plan.requires_origin:
        if latitude is None or longitude is None:
            raise ValueError(
                "This query requires a geographic origin."
            )

    if plan.intent == "search":
        rows = search_pois(
            connection,
            category=plan.category,
            subcategory=plan.subcategory,
            sector=plan.sector,
            name=plan.name,
            limit=plan.limit,
        )
        return [dict(row) for row in rows]

    if plan.intent == "proximity":
        radius_km = (
            plan.radius_km
            if plan.radius_km is not None
            else DEFAULT_PROXIMITY_RADIUS_KM
        )

        return search_within_radius(
            connection,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            category=plan.category,
            subcategory=plan.subcategory,
            sector=plan.sector,
            name=plan.name,
            limit=plan.limit,
        )

    if plan.intent == "nearest":
        max_radius_km = (
            plan.radius_km
            if plan.radius_km is not None
            else DEFAULT_NEAREST_MAX_RADIUS_KM
        )

        return nearest_pois(
            connection,
            latitude=latitude,
            longitude=longitude,
            category=plan.category,
            subcategory=plan.subcategory,
            sector=plan.sector,
            name=plan.name,
            max_radius_km=max_radius_km,
            limit=plan.limit,
        )

    raise ValueError(
        f"Unsupported query intent: {plan.intent}"
    )