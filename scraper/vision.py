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
    """Extract positions from a map image using vision API.

    Returns a positions dict with 'source': 'vision', or None on failure.
    """
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        logger.info("MINIMAX_API_KEY not set, skipping vision extraction")
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
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
            temperature=0.1,
        )

        raw_text = response.content[0].text
        parsed = parse_vision_response(raw_text)
        if parsed is None:
            return None

        validated = validate_positions(parsed)
        if validated is None:
            return None

        validated["source"] = "vision"
        return validated

    except Exception as e:
        logger.warning(f"Vision extraction failed: {e}")
        return None
