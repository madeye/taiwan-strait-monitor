# CV + VLM Position Extraction Pipeline

## Problem

The current vision-only approach relies on the VLM to estimate lat/lon coordinates from map images. VLMs are poor at spatial coordinate estimation, causing frequent fallbacks to coarse zone-based centroids. The MND map images have a well-defined coordinate grid that CV can exploit for precise positioning.

## Architecture

Three-stage pipeline:

```
Image -> [CV: calibrate grid] -> [CV: detect markers] -> [VLM: classify markers] -> positions
```

### Stage 1: Grid Calibration (`scraper/cv.py: calibrate_grid`)

- Detect the map boundary and coordinate tick marks using edge/line detection
- MND maps use a consistent grid: ~118E-122E longitude, ~21N-27N latitude
- Build a linear affine transform: pixel (x, y) -> (lat, lon)
- If dynamic grid detection fails, return a hardcoded fallback calibration measured from known MND map layout (720x1040 images with consistent positioning)

Returns an `AffineTransform` dataclass with a `to_latlon(px, py) -> (lat, lon)` method, or `None` on total failure.

### Stage 2: Marker Detection (`scraper/cv.py: detect_markers`)

- Detect circled number markers (numbered circles like 1, 2, 3) on the map
- Strategy: grayscale -> threshold -> contour detection -> filter by circularity and size (~20-30px diameter)
- Filter out non-marker circles by position (must be within the map area, not in legend/header)
- Return list of `{"px": int, "py": int}` centroids
- No OCR needed on marker numbers -- VLM handles identification

### Stage 3: VLM Classification (`scraper/vision.py`)

- Send image to MiniMax-M2.7 with a label-only prompt (no coordinate estimation)
- Prompt asks VLM to read the legend and for each numbered marker return:
  - type: "aircraft" or "vessel"
  - subtype: e.g. "fighter", "support", "naval", "official"
  - count: number of units
  - region: approximate location ("north", "southwest", etc.)
- Returns JSON: `{"markers": [{"id": 1, "type": "aircraft", "subtype": "fighter", "count": 5, "region": "north"}, ...]}`

### Matching Logic

Greedy nearest-neighbor matching between CV marker positions and VLM labels:

1. Convert each CV marker pixel position to lat/lon using the affine transform
2. For each VLM label (which includes a region hint), compute distance to each unmatched CV marker
3. Assign closest unmatched CV marker to each VLM label
4. Unmatched CV markers get generic "aircraft" label
5. Unmatched VLM labels placed at their region centroid (zone fallback)

This works because MND maps typically have 2-4 well-separated markers.

## Fallback Chain

Inside `extract_positions()`:

1. **vision+cv**: CV markers + VLM labels -- best case
2. **cv**: CV markers found, VLM fails -- markers with generic labels
3. **vision**: CV fails, VLM available -- ask VLM for coordinates too (current behavior)
4. **None**: Everything fails -- caller falls back to `estimate_positions()` (zone-based)

## Module Changes

### New: `scraper/cv.py`

```python
class AffineTransform:
    """2D affine transform from pixel coords to lat/lon."""
    def to_latlon(self, px: int, py: int) -> tuple[float, float]: ...

def calibrate_grid(image_path: str) -> AffineTransform | None:
    """Detect coordinate grid, return pixel-to-latlon transform."""

def detect_markers(image_path: str) -> list[dict]:
    """Detect circled-number markers, return pixel centroids."""
```

### Modified: `scraper/vision.py`

- `extract_positions()` becomes the orchestrator calling CV then VLM
- VLM prompt changes from "identify positions" to "read legend, classify each marker"
- New helper: `match_markers(cv_markers, vlm_labels)` for nearest-neighbor matching
- Existing `parse_vision_response()` updated for new response format
- Existing `validate_positions()` unchanged

### Unchanged: `scraper/main.py`

Still calls `extract_positions(image_path)` and falls back to `estimate_positions(report)`.

## New Dependency

`opencv-python-headless` added to `requirements.txt` (headless variant, no GUI, smaller for CI).

## Data Model

Unchanged. Output remains:
```json
{
  "source": "vision+cv",
  "aircraft": [{"lat": 25.1, "lon": 120.3, "label": "fighter"}],
  "vessels": [{"lat": 24.0, "lon": 119.8, "type": "naval"}]
}
```

## Testing

- `tests/test_cv.py`: Test `calibrate_grid` and `detect_markers` against sample MND image fixture
- `tests/test_vision.py`: Update for new label-only prompt parsing and marker matching logic
- No VLM API calls in tests -- mock API responses
