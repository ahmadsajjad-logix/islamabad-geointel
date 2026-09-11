from math import asin, cos, radians, sin, sqrt


EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """
    Calculate the great-circle distance between two WGS84
    latitude/longitude points using the Haversine formula.

    Returns:
        Distance in kilometres.
    """

    for latitude in (latitude1, latitude2):
        if not -90.0 <= latitude <= 90.0:
            raise ValueError(
                f"Latitude must be between -90 and 90: {latitude}"
            )

    for longitude in (longitude1, longitude2):
        if not -180.0 <= longitude <= 180.0:
            raise ValueError(
                f"Longitude must be between -180 and 180: {longitude}"
            )

    lat1 = radians(latitude1)
    lon1 = radians(longitude1)
    lat2 = radians(latitude2)
    lon2 = radians(longitude2)

    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1

    a = (
        sin(delta_latitude / 2.0) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_longitude / 2.0) ** 2
    )

    c = 2.0 * asin(sqrt(a))

    return EARTH_RADIUS_KM * c


def haversine_m(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """
    Calculate the great-circle distance between two WGS84
    latitude/longitude points.

    Returns:
        Distance in metres.
    """

    return (
        haversine_km(
            latitude1,
            longitude1,
            latitude2,
            longitude2,
        )
        * 1000.0
    )
