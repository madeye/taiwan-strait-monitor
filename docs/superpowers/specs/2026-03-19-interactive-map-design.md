# Interactive Map with Vision-Extracted Positions — Design Spec

## Overview

Replace the static MND route map image with an interactive ECharts geo map showing aircraft and vessel positions. Positions are extracted from the MND route map image using NVIDIA Nemotron vision model at scrape time, with a zone-based fallback when vision fails.

## Goals

- Extract aircraft/vessel positions from MND route map images using vision AI
- Display positions on an interactive map of the Taiwan Strait region
- Fall back to predefined zone centroids when vision extraction fails
- Keep the static site pure — no API calls at browse time

## Non-Goals

- Exact military-grade position tracking (approximate positions are sufficient)
- Real-time position updates
- User-editable position corrections

## Data Model Changes

Add a `positions` field to the daily JSON (`data/daily/YYYY-MM-DD.json`):

```json
{
  "...existing fields...",
  "positions": {
    "source": "vision",
    "aircraft": [
      {"lat": 24.5, "lon": 120.8, "label": "group"},
      {"lat": 23.2, "lon": 119.5, "label": "group"}
    ],
    "vessels": [
      {"lat": 24.0, "lon": 120.2, "type": "naval"},
      {"lat": 23.8, "lon": 119.8, "type": "official"}
    ]
  }
}
```

When vision fails, fallback produces:

```json
{
  "positions": {
    "source": "zones",
    "aircraft": [
      {"lat": 25.0, "lon": 121.0, "label": "north"},
      {"lat": 24.0, "lon": 120.5, "label": "central"},
      {"lat": 23.0, "lon": 119.5, "label": "southwest"}
    ],
    "vessels": [
      {"lat": 24.2, "lon": 120.3, "type": "naval"}
    ]
  }
}
```

- `source`: `"vision"` or `"zones"` — indicates data quality to the dashboard
- The CSV (`summary.csv`) is unchanged — positions are only in the daily JSON
- Existing fields are untouched; `positions` is additive
- Historical JSON files (created before this feature) will have no `positions` field — see "Historical data" section below

## Vision Extraction

### New file: `scraper/vision.py`

Sends the route map image to NVIDIA Nemotron via the OpenAI-compatible API at `https://integrate.api.nvidia.com/v1/chat/completions`.

**Model:** `nvidia/nemotron-3-super-120b-a12b` (verify exact model ID against the [NIM catalog](https://build.nvidia.com/explore/discover) before implementation — the ID may differ from user's initial specification).

**Auth:** `NVIDIA_API_KEY` environment variable. Locally from `.env` or shell env. In GitHub Actions, stored as a repository secret and explicitly passed to the scraper step via `env:`:

```yaml
- name: Run scraper
  env:
    NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}
  run: python -m scraper.main
```

**Request:** The route map image is base64-encoded and sent as an image content part in a chat completion request. MIME type is detected from image bytes (magic bytes check), not hardcoded as `image/jpeg`.

**Prompt strategy:** Provide the model with:
- Taiwan Strait geographic reference frame: bounding box 21.5°N–26°N, 119°E–122.5°E
- Key landmarks: Taipei (~25.03°N, 121.57°E), Kaohsiung (~22.63°N, 120.27°E), Taiwan Strait median line (~120.5°E)
- Instruction to identify aircraft groups and vessel positions from the route map
- Output format: JSON with `aircraft` and `vessels` arrays containing `lat`, `lon`, and `label`/`type` fields

**Validation:** Check that returned coordinates fall within the bounding box. Discard any that don't. If all are discarded or the response is unparseable, return `None` to trigger fallback.

**Error handling:** Any exception (network, auth, parse) is caught and logged. Returns `None` — never blocks the scrape pipeline.

### New file: `scraper/zones.py`

Maps ADIZ region names from parsed text data to predefined centroid coordinates:

| Region | Lat | Lon |
|--------|-----|-----|
| north | 25.5 | 121.0 |
| central | 24.0 | 120.5 |
| southwest | 22.5 | 119.5 |
| southeast | 22.5 | 121.5 |
| south | 22.0 | 120.5 |
| median_line | 24.5 | 120.5 |

Generates one aircraft marker per ADIZ region mentioned in `report["aircraft"]["adiz_regions"]`.

For vessels: emit one aggregate naval marker at the median line centroid (24.5°N, 120.5°E) if `vessels.naval > 0`, and one aggregate official vessel marker slightly offset (24.3°N, 120.3°E) if `vessels.official > 0`. This avoids generating overlapping markers for each individual vessel count.

No API call needed. Always succeeds.

### Pipeline integration (`scraper/main.py`)

After the existing fetch-parse-store steps:

1. Try `vision.extract_positions(image_path)` — returns positions dict or `None`
2. If `None`, use `zones.estimate_positions(report)` — always returns positions dict
3. Add `positions` to the report dict before calling `save_daily_report()`

### Retry behavior

Zone-fallback records are permanent — the idempotency check (`json_path.exists()`) will skip re-processing. This is an accepted tradeoff to keep the pipeline simple. If a vision retry is desired for a specific date, manually delete the JSON file and re-run. Historical backfill of vision data for past dates is a future enhancement, not part of this spec.

### New dependency

`openai` — NVIDIA's build.nvidia.com API is OpenAI-compatible. Added to `requirements.txt`.

## Interactive Map

### GeoJSON

A simplified GeoJSON file of the Taiwan Strait region (Taiwan island outline + China southeast coastline) bundled at `site/geo/taiwan-strait.json`. Source: Natural Earth data, simplified to keep file size small (<100KB).

### ECharts geo map

Replace the `#map-container` section (currently a static `<img>`) with an ECharts instance using the `geo` component.

**Important:** `app.js` must fetch the GeoJSON and call `echarts.registerMap('taiwan-strait', geojsonData)` before initializing the geo chart. This fetch can be parallelized with the `summary.csv` fetch at page load.

Map configuration:

- **Center:** ~24°N, 121°E
- **Zoom:** covers Taiwan Strait from Fujian to east of Taiwan
- **Base map:** Light theme — colored landmass on white/light background

**Marker layers (ECharts scatter series on geo):**

| Series | Symbol | Color | Data source |
|--------|--------|-------|-------------|
| Aircraft | `path://` plane icon or circle | Red (#e74c3c) | `positions.aircraft` |
| Naval vessels | Triangle or diamond | Blue (#3498db) | `positions.vessels` where `type == "naval"` |
| Official vessels | Triangle or diamond | Light blue (#85c1e9) | `positions.vessels` where `type == "official"` |

Tooltip on hover shows the label/type.

### Data loading changes

- `app.js` currently loads only `summary.csv` at page load
- Add: when a date is selected (slider, chart click, initial load), fetch `daily/YYYY-MM-DD.json` via `fetch()` and update the map markers
- Cache fetched JSON in memory to avoid re-fetching on slider scrub back to a visited date
- Show a small badge under the map: "Positions: AI-extracted" or "Positions: Estimated" based on `positions.source`

### Historical data

Daily JSON files created before this feature have no `positions` field. When `app.js` fetches a JSON without `positions`:
- Show no markers on the map
- Show badge: "No position data available"
- The map still renders (empty base map with Taiwan coastline)

Historical backfill is a future enhancement.

### Layout changes

- The ECharts geo map becomes the visual centerpiece, placed between the stats cards and the trend chart
- Map height: ~400px
- Remove the old `#map-container` with the static `<img>` element
- The MND source route map image is still downloadable but no longer displayed inline

### Build changes

- `make build` must also copy `data/daily/*.json` to `site/daily/` for client-side fetching
- `.gitignore` must add `site/daily/`
- The Makefile `build` target and GitHub Actions "Build site" step must be updated
- The Makefile `clean` target must also remove `site/daily/`
- GeoJSON file (`site/geo/taiwan-strait.json`) is committed to the repo (static asset, not a build artifact)

## File Changes Summary

| File | Change |
|------|--------|
| `scraper/vision.py` | New: vision extraction via NVIDIA API |
| `scraper/zones.py` | New: zone-based fallback positions |
| `scraper/main.py` | Modify: add vision/zone step after parse |
| `requirements.txt` | Modify: add `openai` |
| `site/js/app.js` | Modify: add geo map, fetch daily JSON, update markers on date select, switch ECharts from `"dark"` theme to default (light) |
| `site/index.html` | Modify: replace static img with map div, add source badge |
| `site/css/style.css` | Modify: switch entire dashboard from dark to light theme, style map container and source badge |
| `site/geo/taiwan-strait.json` | New: GeoJSON for the map |
| `Makefile` | Modify: copy daily JSON to site/ in build target |
| `.gitignore` | Modify: add `site/daily/` |
| `.github/workflows/scrape-and-deploy.yml` | Modify: add NVIDIA_API_KEY secret, copy daily JSON |
| `tests/test_vision.py` | New: unit tests for vision response parsing and validation |
| `tests/test_zones.py` | New: unit tests for zone estimation |
