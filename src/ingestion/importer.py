import json
from pathlib import Path
from typing import Any

from src.database.connection import get_connection
from src.database.repository import (
    complete_import_run,
    create_import_run,
    fail_import_run,
    upsert_poi,
)
from src.ingestion.normalizer import (
    normalize_feature,
    should_include_feature,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

PILOT_FILES = (
    "f5_address_candidates.geojson",
    "f5_radius_candidates.geojson",
    "f6_address_candidates.geojson",
    "f6_radius_candidates.geojson",
    "f7_address_candidates.geojson",
    "f7_radius_candidates.geojson",
)


def load_geojson_features(
    file_path: Path,
) -> list[dict[str, Any]]:
    """
    Load and validate the feature collection from one GeoJSON file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw GeoJSON file not found: {file_path}"
        )

    data = json.loads(
        file_path.read_text(encoding="utf-8")
    )

    if data.get("type") != "FeatureCollection":
        raise ValueError(
            f"{file_path.name}: expected GeoJSON FeatureCollection"
        )

    features = data.get("features")

    if not isinstance(features, list):
        raise ValueError(
            f"{file_path.name}: missing or invalid features list"
        )

    return features


def load_unique_pilot_features() -> tuple[
    dict[str, dict[str, Any]],
    int,
]:
    """
    Load all six pilot acquisition files and deduplicate objects
    using their Overpass Turbo @id values.

    Returns:
        unique_features:
            Mapping of @id to one GeoJSON feature.

        total_occurrences:
            Number of feature occurrences before cross-file
            deduplication.
    """

    unique_features: dict[str, dict[str, Any]] = {}
    total_occurrences = 0

    for filename in PILOT_FILES:
        file_path = RAW_DATA_DIR / filename
        features = load_geojson_features(file_path)

        total_occurrences += len(features)

        for feature in features:
            properties = feature.get("properties") or {}
            osm_reference = properties.get("@id")

            if not osm_reference:
                raise ValueError(
                    f"{filename}: feature missing @id"
                )

            if osm_reference not in unique_features:
                unique_features[osm_reference] = feature

    return unique_features, total_occurrences


def prepare_pilot_pois() -> tuple[
    list[dict[str, Any]],
    dict[str, int],
]:
    """
    Build the validated pilot POI/entity collection without writing
    anything to SQLite.
    """

    unique_features, total_occurrences = (
        load_unique_pilot_features()
    )

    pois: list[dict[str, Any]] = []
    excluded = 0

    for feature in unique_features.values():
        properties = feature.get("properties") or {}

        if not should_include_feature(properties):
            excluded += 1
            continue

        normalized = normalize_feature(feature)

        if (
            normalized["category"] is None
            or normalized["subcategory"] is None
        ):
            osm_reference = properties.get("@id")

            raise ValueError(
                f"{osm_reference}: included feature is unclassified"
            )

        pois.append(normalized)

    statistics = {
        "total_occurrences": total_occurrences,
        "unique_objects": len(unique_features),
        "duplicate_occurrences": (
            total_occurrences - len(unique_features)
        ),
        "included_pois": len(pois),
        "excluded_objects": excluded,
    }

    return pois, statistics


def import_pilot() -> dict[str, int]:
    """
    Import the normalized F-5/F-6/F-7 pilot dataset into SQLite.

    The database transaction is committed only after every POI has
    been processed successfully. On failure, POI changes are rolled
    back and the import run is recorded as failed.
    """

    pois, statistics = prepare_pilot_pois()

    connection = get_connection()
    import_run_id: int | None = None

    try:
        import_run_id = create_import_run(
            connection,
            source="OpenStreetMap",
            area="F-5, F-6, F-7 pilot",
        )

        # Persist the running import record separately so that a later
        # rollback of POI changes does not erase the audit record.
        connection.commit()

        inserted = 0
        updated = 0

        try:
            for poi in pois:
                result = upsert_poi(
                    connection,
                    poi,
                )

                if result == "inserted":
                    inserted += 1
                elif result == "updated":
                    updated += 1
                else:
                    raise RuntimeError(
                        f"Unexpected upsert result: {result!r}"
                    )

            complete_import_run(
                connection,
                import_run_id=import_run_id,
                records_received=statistics["unique_objects"],
                records_inserted=inserted,
                records_updated=updated,
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    except Exception as exc:
        if import_run_id is not None:
            fail_import_run(
                connection,
                import_run_id=import_run_id,
                error_message=str(exc),
            )
            connection.commit()

        raise

    finally:
        connection.close()

    return {
        **statistics,
        "records_inserted": inserted,
        "records_updated": updated,
    }