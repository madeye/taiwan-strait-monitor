ZONE_CENTROIDS = {
    "north": (25.5, 121.0),
    "central": (24.0, 120.5),
    "southwest": (22.5, 119.5),
    "southeast": (22.5, 121.5),
    "south": (22.0, 120.5),
}

NAVAL_CENTROID = (24.5, 120.5)
OFFICIAL_CENTROID = (24.3, 120.3)


def estimate_positions(report: dict) -> dict:
    """Estimate aircraft/vessel positions from ADIZ region text data."""
    aircraft = []
    for region in report.get("aircraft", {}).get("adiz_regions", []):
        if region in ZONE_CENTROIDS:
            lat, lon = ZONE_CENTROIDS[region]
            aircraft.append({"lat": lat, "lon": lon, "label": region})

    vessels = []
    if report.get("vessels", {}).get("naval", 0) > 0:
        vessels.append({"lat": NAVAL_CENTROID[0], "lon": NAVAL_CENTROID[1], "type": "naval"})
    if report.get("vessels", {}).get("official", 0) > 0:
        vessels.append({"lat": OFFICIAL_CENTROID[0], "lon": OFFICIAL_CENTROID[1], "type": "official"})

    return {
        "source": "zones",
        "aircraft": aircraft,
        "vessels": vessels,
    }
