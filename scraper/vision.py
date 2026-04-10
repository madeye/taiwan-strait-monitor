import base64
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic"
MODEL = "MiniMax-M2.7"

MIN_LAT, MAX_LAT = 21.5, 26.0
MIN_LON, MAX_LON = 119.0, 122.5

VISION_PROMPT = """You are analyzing a military activity route map of the Taiwan Strait region.

Geographic reference:
- Bounding box: 21.5°N–26°N latitude, 119°E–122.5°E longitude
- Taiwan island: eastern side of the strait
- Taipei: ~25.03°N, 121.57°E (northern Taiwan)
- Kaohsiung: ~22.63°N, 120.27°E (southern Taiwan)
- Taiwan Strait median line: approximately 120.5°E

Identify all aircraft groups and vessel positions shown on this map.

Return ONLY a JSON object (no other text) with this exact structure:
{
  "aircraft": [{"lat": <number>, "lon": <number>, "label": "group"}],
  "vessels": [{"lat": <number>, "lon": <number>, "type": "naval" or "official"}]
}

If you cannot identify positions, return: {"aircraft": [], "vessels": []}
"""


MARKER_PROMPT = """You are analyzing a military activity route map of the Taiwan Strait region.
This image is 720 pixels wide and 1040 pixels tall.

Read the legend/table at the top-left of the map. Each numbered entry (①, ②, ③, etc.)
describes a group of aircraft or vessels with their activity details.

For each numbered marker visible on the map, report:
- id: the marker number (1, 2, 3, etc.)
- type: "aircraft" or "vessel"
- subtype: e.g. "fighter", "support", "naval", "official"
- count: number of units
- region: approximate region ("north", "central", "southwest", "southeast", "south")
- px: the marker's horizontal pixel position (0 = left edge, 720 = right edge)
- py: the marker's vertical pixel position (0 = top edge, 1040 = bottom edge)

Return ONLY a JSON object (no other text):
{"markers": [{"id": 1, "type": "aircraft", "subtype": "fighter", "count": 5, "region": "north", "px": 480, "py": 350}, ...]}

If you cannot identify markers, return: {"markers": []}
"""


def parse_marker_response(raw: str) -> dict | None:
    """Parse the VLM marker identification response."""
    if not raw:
        return None

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = cleaned.rstrip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse marker response as JSON")
        return None

    if "markers" not in data:
        logger.warning("Marker response missing 'markers' key")
        return None

    return data


def build_positions_from_markers(markers: list[dict], transform) -> dict:
    """Convert VLM marker data with pixel positions to lat/lon positions.

    Uses the CV affine transform to convert pixel coords to geographic coords.
    Filters out positions outside the Taiwan Strait bounding box.
    """
    aircraft = []
    vessels = []

    for m in markers:
        px = m.get("px", 0)
        py = m.get("py", 0)
        lat, lon = transform.to_latlon(px, py)

        if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
            logger.info(f"Marker {m.get('id')} at ({lat:.2f}, {lon:.2f}) outside bounds, skipping")
            continue

        if m.get("type") == "vessel":
            vessels.append({
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "type": m.get("subtype", "naval"),
            })
        else:
            aircraft.append({
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "label": m.get("subtype", m.get("region", "unknown")),
            })

    return {"aircraft": aircraft, "vessels": vessels}


def parse_vision_response(raw: str) -> dict | None:
    """Parse the vision model's text response into a positions dict."""
    if not raw:
        return None

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = cleaned.rstrip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse vision response as JSON")
        return None

    if "aircraft" not in data or "vessels" not in data:
        logger.warning("Vision response missing required keys")
        return None

    return data


def validate_positions(positions: dict) -> dict | None:
    """Filter positions to bounding box. Returns None if nothing remains."""
    def in_bounds(p):
        return MIN_LAT <= p.get("lat", 0) <= MAX_LAT and MIN_LON <= p.get("lon", 0) <= MAX_LON

    aircraft = [p for p in positions.get("aircraft", []) if in_bounds(p)]
    vessels = [p for p in positions.get("vessels", []) if in_bounds(p)]

    if not aircraft and not vessels:
        return None

    return {"aircraft": aircraft, "vessels": vessels}


def _detect_mime_type(image_bytes: bytes) -> str:
    """Detect MIME type from image magic bytes."""
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    if image_bytes[:4] == b"GIF8":
        return "image/gif"
    return "image/jpeg"


def extract_positions(image_path: str) -> dict | None:
    """Extract positions from a map image using CV grid calibration + VLM marker identification.

    Pipeline: CV calibration → VLM markers → merge.
    Fallback chain: vision+cv → vision-only → None (caller falls back to zones).
    """
    api_key = os.environ.get("MINIMAX_API_KEY")

    # Stage 1: CV grid calibration (always attempted)
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(image_path)

    # Stage 2: VLM marker identification
    if not api_key:
        logger.info("MINIMAX_API_KEY not set, skipping VLM extraction")
        return None

    try:
        import anthropic

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime_type = _detect_mime_type(image_bytes)
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        client = anthropic.Anthropic(base_url=MINIMAX_BASE_URL, api_key=api_key)

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": MARKER_PROMPT},
                    ],
                }
            ],
            temperature=0.1,
        )

        raw_text = response.content[0].text

        # Try CV+VLM path first (marker prompt with pixel positions)
        marker_data = parse_marker_response(raw_text)
        if marker_data and marker_data.get("markers") and transform:
            positions = build_positions_from_markers(marker_data["markers"], transform)
            validated = validate_positions(positions)
            if validated:
                validated["source"] = "vision+cv"
                return validated

        # Fallback: try parsing as legacy vision response (lat/lon from VLM)
        parsed = parse_vision_response(raw_text)
        if parsed:
            validated = validate_positions(parsed)
            if validated:
                validated["source"] = "vision"
                return validated

        return None

    except Exception as e:
        logger.warning(f"Vision extraction failed: {e}")
        return None
