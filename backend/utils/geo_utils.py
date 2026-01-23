# backend/utils/geo_utils.py
"""
Utility functions for geographical calculations.
Used by Farmer Dashboard for land-area computation.
"""

from shapely.geometry import Polygon


def calculate_polygon_area(lat_lon_points):
    """
    Calculate area of a polygon (list of [lat, lon] points) in square meters.

    Input format expected:
    [
        {"lat": 18.5204, "lng": 73.8567},
        {"lat": 18.5206, "lng": 73.8569},
        ...
    ]

    Returns:
        float: area in square meters
    """

    if not lat_lon_points or len(lat_lon_points) < 3:
        return 0.0

    try:
        poly_points = [(p["lng"], p["lat"]) for p in lat_lon_points]  # (x, y) = (lon, lat)
        polygon = Polygon(poly_points)

        # Shapely outputs square degrees → must convert to meters
        # Approx conversion for small polygons
        # 1 degree lat ≈ 111,320 meters
        lat_factor = 111320
        lon_factor = 111320

        area_deg = polygon.area
        area_m2 = area_deg * lat_factor * lon_factor

        return round(area_m2, 2)

    except Exception:
        return 0.0


__all__ = ["calculate_polygon_area"]
