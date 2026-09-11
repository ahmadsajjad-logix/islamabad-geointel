"""
Command-line entry point for importing the Islamabad GeoIntel pilot dataset.

Historical filename note:
    This script was originally created for the F-5 proof of concept.
    The validated pilot was subsequently expanded to F-5, F-6 and F-7.
    The filename is retained to preserve the approved project structure.
"""

from src.ingestion.importer import import_pilot


def main() -> None:
    """Run the validated F-5/F-6/F-7 pilot import."""

    print("=" * 80)
    print("ISLAMABAD GEOINTEL - PILOT IMPORT")
    print("Coverage: F-5, F-6 and F-7")
    print("=" * 80)

    result = import_pilot()

    print()
    print("IMPORT SUMMARY")
    print("-" * 80)
    print(
        f"{'Feature occurrences:':<30}"
        f"{result['total_occurrences']}"
    )
    print(
        f"{'Unique OSM objects:':<30}"
        f"{result['unique_objects']}"
    )
    print(
        f"{'Duplicate occurrences:':<30}"
        f"{result['duplicate_occurrences']}"
    )
    print(
        f"{'Included POIs/entities:':<30}"
        f"{result['included_pois']}"
    )
    print(
        f"{'Excluded objects:':<30}"
        f"{result['excluded_objects']}"
    )
    print(
        f"{'Records inserted:':<30}"
        f"{result['records_inserted']}"
    )
    print(
        f"{'Records updated/refreshed:':<30}"
        f"{result['records_updated']}"
    )

    print()
    print("Pilot import completed successfully.")


if __name__ == "__main__":
    main()