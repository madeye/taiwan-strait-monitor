# Interactive Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static route map image with an interactive ECharts geo map showing vision-extracted aircraft/vessel positions, with a zone-based fallback.

**Architecture:** Vision extraction at scrape time via NVIDIA Nemotron (OpenAI-compatible API). Zone fallback uses parsed ADIZ region text. ECharts geo component renders the map client-side from pre-computed positions stored in daily JSON. Entire dashboard switches from dark to light theme.

**Tech Stack:** Python (openai SDK), NVIDIA NIM API, ECharts geo, Natural Earth GeoJSON

**Spec:** `docs/superpowers/specs/2026-03-19-interactive-map-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `scraper/zones.py` | New: zone-based fallback position estimation |
| `scraper/vision.py` | New: vision extraction via NVIDIA API |
| `scraper/main.py` | Modify: integrate vision + zones into pipeline |
| `requirements.txt` | Modify: add `openai` |
| `site/geo/taiwan-strait.json` | New: GeoJSON for ECharts map |
| `site/index.html` | Modify: replace static img with map div, add badge |
| `site/css/style.css` | Modify: light theme, map container, badge styles |
| `site/js/app.js` | Modify: geo map, daily JSON fetch, light ECharts theme |
| `Makefile` | Modify: copy daily JSON in build, clean site/daily/ |
| `.gitignore` | Modify: add site/daily/ |
| `.github/workflows/scrape-and-deploy.yml` | Modify: NVIDIA_API_KEY env |
| `tests/test_zones.py` | New: unit tests for zone estimation |
| `tests/test_vision.py` | New: unit tests for vision response parsing |

---

## Task 1: Zone-based fallback (TDD)

**Files:**
- Create: `scraper/zones.py`, `tests/test_zones.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_zones.py
from scraper.zones import estimate_positions


def test_estimate_positions_with_regions():
    report = {
        "aircraft": {
            "total": 12,
            "crossed_median": 5,
            "entered_adiz": 5,
            "adiz_regions": ["north", "central", "southwest"],
        },
        "vessels": {"naval": 9, "official": 2},
    }
    result = estimate_positions(report)

    assert result["source"] == "zones"
    assert len(result["aircraft"]) == 3
    assert result["aircraft"][0]["label"] == "north"
    assert 25.0 <= result["aircraft"][0]["lat"] <= 26.0
    assert len(result["vessels"]) == 2  # one naval + one official


def test_estimate_positions_no_regions():
    report = {
        "aircraft": {
            "total": 2,
            "crossed_median": 0,
            "entered_adiz": 0,
            "adiz_regions": [],
        },
        "vessels": {"naval": 3, "official": 0},
    }
    result = estimate_positions(report)

    assert result["source"] == "zones"
    assert len(result["aircraft"]) == 0
    assert len(result["vessels"]) == 1  # naval only, no official


def test_estimate_positions_no_vessels():
    report = {
        "aircraft": {
            "total": 0,
            "crossed_median": 0,
            "entered_adiz": 0,
            "adiz_regions": [],
        },
        "vessels": {"naval": 0, "official": 0},
    }
    result = estimate_positions(report)

    assert result["source"] == "zones"
    assert len(result["aircraft"]) == 0
    assert len(result["vessels"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest tests/test_zones.py -v
```

- [ ] **Step 3: Implement zones.py**

```python
# scraper/zones.py

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest tests/test_zones.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add scraper/zones.py tests/test_zones.py && git commit -m "feat: zone-based fallback position estimation"
```

---

## Task 2: Vision extraction — response parsing and validation (TDD)

**Files:**
- Create: `scraper/vision.py`, `tests/test_vision.py`

- [ ] **Step 0: Verify NVIDIA model ID**

Before writing any code, verify the exact model ID `nvidia/nemotron-3-super-120b-a12b` exists at `https://build.nvidia.com/explore/discover`. If the ID is different, update the `MODEL` constant in the implementation below. The spec warns the user-provided ID may not match the catalog.

- [ ] **Step 1: Write failing tests for parsing and validation**

```python
# tests/test_vision.py
import json
from scraper.vision import parse_vision_response, validate_positions

BOUNDING_BOX = (21.5, 26.0, 119.0, 122.5)  # min_lat, max_lat, min_lon, max_lon


def test_parse_vision_response_valid():
    raw = json.dumps({
        "aircraft": [
            {"lat": 24.5, "lon": 120.8, "label": "group"},
            {"lat": 23.2, "lon": 119.5, "label": "group"},
        ],
        "vessels": [
            {"lat": 24.0, "lon": 120.2, "type": "naval"},
        ],
    })
    result = parse_vision_response(raw)
    assert len(result["aircraft"]) == 2
    assert len(result["vessels"]) == 1


def test_parse_vision_response_with_markdown_fences():
    raw = '```json\n{"aircraft": [{"lat": 24.5, "lon": 120.8, "label": "group"}], "vessels": []}\n```'
    result = parse_vision_response(raw)
    assert len(result["aircraft"]) == 1


def test_parse_vision_response_invalid():
    result = parse_vision_response("This is not JSON at all")
    assert result is None


def test_validate_positions_filters_out_of_bounds():
    positions = {
        "aircraft": [
            {"lat": 24.5, "lon": 120.8, "label": "ok"},
            {"lat": 50.0, "lon": 120.0, "label": "out"},  # too far north
        ],
        "vessels": [
            {"lat": 24.0, "lon": 200.0, "type": "naval"},  # out of bounds
        ],
    }
    result = validate_positions(positions)
    assert len(result["aircraft"]) == 1
    assert result["aircraft"][0]["label"] == "ok"
    assert len(result["vessels"]) == 0


def test_validate_positions_returns_none_when_all_filtered():
    positions = {
        "aircraft": [{"lat": 50.0, "lon": 120.0, "label": "out"}],
        "vessels": [],
    }
    result = validate_positions(positions)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest tests/test_vision.py -v
```

- [ ] **Step 3: Implement parse and validate functions**

```python
# scraper/vision.py
import base64
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"

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
    return "image/jpeg"  # default


def extract_positions(image_path: str) -> dict | None:
    """Extract positions from a map image using NVIDIA Nemotron vision API.

    Returns a positions dict with 'source': 'vision', or None on failure.
    """
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        logger.info("NVIDIA_API_KEY not set, skipping vision extraction")
        return None

    try:
        from openai import OpenAI

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        mime_type = _detect_mime_type(image_bytes)
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
                        },
                    ],
                }
            ],
            max_tokens=1024,
            temperature=0.1,
        )

        raw_text = response.choices[0].message.content
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest tests/test_vision.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run all tests**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest -v
```

Expected: 17 passed (9 existing + 3 zones + 5 vision).

- [ ] **Step 6: Commit**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add scraper/vision.py tests/test_vision.py && git commit -m "feat: vision extraction with NVIDIA Nemotron API"
```

---

## Task 3: Integrate vision + zones into pipeline

**Files:**
- Modify: `scraper/main.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add openai to requirements.txt**

Append to `requirements.txt`:
```
openai>=1.0,<2
```

- [ ] **Step 2: Modify scraper/main.py**

Read the current file first, then modify. Add vision/zones integration between the map image download and the `save_daily_report` call.

The modified `main.py` should be:

```python
import pathlib
import sys

from scraper.fetcher import fetch_list_page, fetch_detail_page, fetch_image
from scraper.parser import parse_list_page, parse_detail_page
from scraper.storage import save_daily_report, save_map_image, regenerate_csv
from scraper.vision import extract_positions
from scraper.zones import estimate_positions

DATA_DIR = pathlib.Path("data")
RESULT_FILE = pathlib.Path("scraper_result.txt")


def main() -> int:
    list_html = fetch_list_page()
    reports = parse_list_page(list_html)

    if not reports:
        print("ERROR: No reports found on list page")
        return 1

    latest = reports[0]
    date_str = latest["date"]
    json_path = DATA_DIR / "daily" / f"{date_str}.json"

    if json_path.exists():
        print(f"Data for {date_str} already exists, skipping.")
        RESULT_FILE.write_text("skipped")
        return 0

    print(f"Fetching report {latest['id']} for {date_str}...")
    detail_html = fetch_detail_page(latest["id"])
    report = parse_detail_page(detail_html)

    # Download map image
    image_path = ""
    if report.get("map_image_url"):
        print("Downloading map image...")
        image_bytes = fetch_image(report["map_image_url"])
        saved_path = save_map_image(image_bytes, date_str, DATA_DIR)
        report["map_image"] = f"assets/maps/{date_str}.jpg"
        if saved_path and saved_path.exists():
            image_path = str(saved_path)
    else:
        report["map_image"] = ""

    # Extract positions: try vision, fall back to zones
    positions = None
    if image_path:
        print("Extracting positions via vision API...")
        positions = extract_positions(image_path)

    if positions is None:
        print("Using zone-based position estimation...")
        positions = estimate_positions(report)

    report["positions"] = positions

    # Clean up and save
    report.pop("map_image_url", None)
    report["source_url"] = f"https://www.mnd.gov.tw/news/plaact/{latest['id']}"

    save_daily_report(report, DATA_DIR)
    print(f"Saved {json_path}")

    regenerate_csv(DATA_DIR)
    print("Regenerated summary.csv")

    RESULT_FILE.write_text("new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run all tests**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest -v
```

Expected: 17 passed.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add scraper/main.py requirements.txt && git commit -m "feat: integrate vision + zones into scraper pipeline"
```

---

## Task 4: GeoJSON for Taiwan Strait

**Files:**
- Create: `site/geo/taiwan-strait.json`

- [ ] **Step 1: Download and simplify Natural Earth GeoJSON**

Download the 110m countries GeoJSON from Natural Earth, extract Taiwan and China coastlines, and simplify to a small file. We need just the landmass outlines for visual context.

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && mkdir -p site/geo

# Download Natural Earth 110m countries GeoJSON
curl -sL "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson" | \
python -c "
import json, sys
data = json.load(sys.stdin)
# Filter to countries visible in Taiwan Strait region
names = {'Taiwan', 'China', 'Philippines', 'Japan'}
features = [f for f in data['features'] if f['properties'].get('NAME') in names or f['properties'].get('ADMIN') in names]
out = {'type': 'FeatureCollection', 'features': features}
json.dump(out, sys.stdout, separators=(',', ':'))
" > site/geo/taiwan-strait.json
```

- [ ] **Step 2: Verify the file is valid and reasonably sized**

```bash
python -c "import json; d=json.load(open('site/geo/taiwan-strait.json')); print(f'{len(d[\"features\"])} features'); [print(f['properties'].get('NAME','?')) for f in d['features']]"
ls -lh site/geo/taiwan-strait.json
```

Expected: 2-4 features (Taiwan, China, possibly Philippines/Japan), file < 100KB.

- [ ] **Step 3: Commit**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add site/geo/taiwan-strait.json && git commit -m "feat: add Taiwan Strait GeoJSON from Natural Earth"
```

---

## Task 5: Light theme CSS

**Files:**
- Modify: `site/css/style.css`

- [ ] **Step 1: Replace style.css with light theme**

Read the current file, then replace entirely:

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f8f9fa;
    color: #212529;
    max-width: 960px;
    margin: 0 auto;
    padding: 1rem;
}

header {
    text-align: center;
    margin-bottom: 2rem;
}

header h1 { font-size: 1.5rem; margin-bottom: 0.25rem; color: #212529; }
header p { color: #6c757d; font-size: 0.85rem; }
header a { color: #0d6efd; font-size: 0.85rem; }

#stats {
    display: flex;
    gap: 0.75rem;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 1.5rem;
}

.card {
    background: #fff;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 0.75rem 1.25rem;
    text-align: center;
    min-width: 100px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.card-value {
    display: block;
    font-size: 1.75rem;
    font-weight: bold;
    color: #212529;
}

.card-label {
    display: block;
    font-size: 0.75rem;
    color: #6c757d;
    margin-top: 0.25rem;
}

#geo-map-container { margin-bottom: 1rem; }
#geo-map { width: 100%; height: 400px; }

#position-badge {
    text-align: center;
    font-size: 0.75rem;
    color: #6c757d;
    margin-top: 0.25rem;
    margin-bottom: 1rem;
}

#chart-container { margin-bottom: 1rem; }
#trend-chart { width: 100%; height: 300px; }

#timeline-container {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
    padding: 0 0.5rem;
}

#timeline-slider { flex: 1; cursor: pointer; }
#timeline-date { font-size: 0.9rem; min-width: 90px; text-align: right; }
```

- [ ] **Step 2: Commit**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add site/css/style.css && git commit -m "feat: switch dashboard to light theme"
```

---

## Task 6: Update HTML — replace static map with geo map div

**Files:**
- Modify: `site/index.html`

- [ ] **Step 1: Replace index.html**

Read current file, then replace:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Taiwan Strait Monitor</title>
    <link rel="stylesheet" href="css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
</head>
<body>
    <header>
        <h1>Taiwan Strait Monitor</h1>
        <p id="last-updated">Loading...</p>
        <a href="https://www.mnd.gov.tw/PublishTable.aspx?Types=%E5%8D%B3%E6%99%82%E8%BB%8D%E4%BA%8B%E5%8B%95%E6%85%8B&title=%E5%9C%8B%E9%98%B2%E6%B6%88%E6%81%AF"
           target="_blank" rel="noopener">MND Source</a>
    </header>

    <main>
        <section id="stats">
            <div class="card">
                <span class="card-value" id="stat-aircraft">-</span>
                <span class="card-label">Aircraft</span>
            </div>
            <div class="card">
                <span class="card-value" id="stat-median">-</span>
                <span class="card-label">Crossed Median</span>
            </div>
            <div class="card">
                <span class="card-value" id="stat-adiz">-</span>
                <span class="card-label">Entered ADIZ</span>
            </div>
            <div class="card">
                <span class="card-value" id="stat-naval">-</span>
                <span class="card-label">Naval Vessels</span>
            </div>
            <div class="card">
                <span class="card-value" id="stat-official">-</span>
                <span class="card-label">Official Vessels</span>
            </div>
        </section>

        <section id="geo-map-container">
            <div id="geo-map"></div>
            <p id="position-badge">-</p>
        </section>

        <section id="chart-container">
            <div id="trend-chart"></div>
        </section>

        <section id="timeline-container">
            <input type="range" id="timeline-slider" min="0" max="0" value="0">
            <span id="timeline-date">-</span>
        </section>
    </main>

    <script src="js/app.js"></script>
</body>
</html>
```

**Note:** Do NOT commit yet — Task 6 and Task 7 must be committed together. Committing the HTML alone leaves the site broken because the old app.js references removed DOM elements.

---

## Task 7: Update app.js — geo map, daily JSON fetch, light theme

**Files:**
- Modify: `site/js/app.js`

- [ ] **Step 1: Replace app.js**

Read the current file, then replace entirely:

```javascript
(async function () {
    // Parallel fetch: CSV + GeoJSON
    const [csvResp, geoResp] = await Promise.all([
        fetch("summary.csv"),
        fetch("geo/taiwan-strait.json"),
    ]);
    const csvText = await csvResp.text();
    const geoData = await geoResp.json();
    const rows = parseCSV(csvText);

    if (rows.length === 0) {
        document.getElementById("last-updated").textContent = "No data available";
        return;
    }

    // Register map for ECharts geo
    echarts.registerMap("taiwan-strait", geoData);

    let selectedIndex = rows.length - 1;
    const jsonCache = {};

    // Timeline slider
    const slider = document.getElementById("timeline-slider");
    slider.min = 0;
    slider.max = rows.length - 1;
    slider.value = selectedIndex;

    // Geo map
    const geoChart = echarts.init(document.getElementById("geo-map"));
    const geoOption = {
        geo: {
            map: "taiwan-strait",
            roam: true,
            center: [121, 24],
            zoom: 5,
            itemStyle: {
                areaColor: "#e8e8e8",
                borderColor: "#aaa",
            },
            emphasis: {
                itemStyle: { areaColor: "#ddd" },
            },
        },
        tooltip: { trigger: "item" },
        series: [
            {
                name: "Aircraft",
                type: "scatter",
                coordinateSystem: "geo",
                data: [],
                symbol: "circle",
                symbolSize: 12,
                itemStyle: { color: "#e74c3c" },
                tooltip: {
                    formatter: function (params) {
                        return "Aircraft: " + (params.data.label || "group");
                    },
                },
            },
            {
                name: "Naval Vessels",
                type: "scatter",
                coordinateSystem: "geo",
                data: [],
                symbol: "diamond",
                symbolSize: 12,
                itemStyle: { color: "#3498db" },
                tooltip: {
                    formatter: function (params) {
                        return "Naval Vessel";
                    },
                },
            },
            {
                name: "Official Vessels",
                type: "scatter",
                coordinateSystem: "geo",
                data: [],
                symbol: "diamond",
                symbolSize: 10,
                itemStyle: { color: "#85c1e9" },
                tooltip: {
                    formatter: function (params) {
                        return "Official Vessel";
                    },
                },
            },
        ],
    };
    geoChart.setOption(geoOption);

    // Trend chart (light theme — no "dark" arg)
    const trendChart = echarts.init(document.getElementById("trend-chart"));
    const trendOption = {
        tooltip: { trigger: "axis" },
        legend: { data: ["Aircraft", "Naval Vessels"], top: 0 },
        xAxis: {
            type: "category",
            data: rows.map((r) => r.date),
            axisLabel: { rotate: 45, fontSize: 10 },
        },
        yAxis: [
            { type: "value", name: "Aircraft", position: "left" },
            { type: "value", name: "Vessels", position: "right" },
        ],
        series: [
            {
                name: "Aircraft",
                type: "line",
                data: rows.map((r) => r.aircraft_total),
                yAxisIndex: 0,
                smooth: true,
                symbolSize: 6,
            },
            {
                name: "Naval Vessels",
                type: "line",
                data: rows.map((r) => r.vessels_naval),
                yAxisIndex: 1,
                smooth: true,
                symbolSize: 6,
            },
        ],
    };
    trendChart.setOption(trendOption);

    // Fetch daily JSON (with cache)
    async function fetchDailyJSON(date) {
        if (jsonCache[date]) return jsonCache[date];
        try {
            const resp = await fetch("daily/" + date + ".json");
            if (!resp.ok) return null;
            const data = await resp.json();
            jsonCache[date] = data;
            return data;
        } catch (e) {
            return null;
        }
    }

    // Update map markers from positions data
    function updateMapMarkers(positions) {
        const badge = document.getElementById("position-badge");

        if (!positions) {
            geoChart.setOption({
                series: [
                    { name: "Aircraft", data: [] },
                    { name: "Naval Vessels", data: [] },
                    { name: "Official Vessels", data: [] },
                ],
            });
            badge.textContent = "No position data available";
            return;
        }

        const aircraftData = (positions.aircraft || []).map((p) => ({
            value: [p.lon, p.lat],
            label: p.label,
        }));

        const navalData = (positions.vessels || [])
            .filter((v) => v.type === "naval")
            .map((p) => ({ value: [p.lon, p.lat] }));

        const officialData = (positions.vessels || [])
            .filter((v) => v.type === "official")
            .map((p) => ({ value: [p.lon, p.lat] }));

        geoChart.setOption({
            series: [
                { name: "Aircraft", data: aircraftData },
                { name: "Naval Vessels", data: navalData },
                { name: "Official Vessels", data: officialData },
            ],
        });

        if (positions.source === "vision") {
            badge.textContent = "Positions: AI-extracted";
        } else if (positions.source === "zones") {
            badge.textContent = "Positions: Estimated";
        } else {
            badge.textContent = "";
        }
    }

    // Select date — update everything
    async function selectDate(index) {
        selectedIndex = Math.max(0, Math.min(index, rows.length - 1));
        const row = rows[selectedIndex];

        // Stats
        document.getElementById("stat-aircraft").textContent = row.aircraft_total;
        document.getElementById("stat-median").textContent = row.crossed_median;
        document.getElementById("stat-adiz").textContent = row.entered_adiz;
        document.getElementById("stat-naval").textContent = row.vessels_naval;
        document.getElementById("stat-official").textContent = row.vessels_official;

        // Timeline
        slider.value = selectedIndex;
        document.getElementById("timeline-date").textContent = row.date;

        // Trend chart tooltip
        trendChart.dispatchAction({
            type: "showTip",
            seriesIndex: 0,
            dataIndex: selectedIndex,
        });

        // Geo map — fetch daily JSON
        const daily = await fetchDailyJSON(row.date);
        updateMapMarkers(daily ? daily.positions : null);
    }

    // Events
    slider.addEventListener("input", (e) => selectDate(parseInt(e.target.value)));
    trendChart.on("click", (params) => selectDate(params.dataIndex));

    // Last updated
    const latest = rows[rows.length - 1];
    document.getElementById("last-updated").textContent = "Last updated: " + latest.date;

    // Responsive
    window.addEventListener("resize", () => {
        trendChart.resize();
        geoChart.resize();
    });

    // Initial render
    selectDate(selectedIndex);
})();

function parseCSV(text) {
    const lines = text.trim().split("\n");
    if (lines.length < 2) return [];

    const headers = lines[0].split(",");
    return lines.slice(1).map((line) => {
        const values = line.split(",");
        const obj = {};
        headers.forEach((h, i) => {
            const v = values[i];
            obj[h] = isNaN(v) || v === "" ? v : parseInt(v);
        });
        return obj;
    });
}
```

- [ ] **Step 2: Commit HTML + app.js together**

These must be committed together to avoid a broken intermediate state (HTML removes DOM elements that the old app.js referenced):

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add site/index.html site/js/app.js && git commit -m "feat: interactive geo map with daily JSON fetch and light theme"
```

---

## Task 8: Build infrastructure updates

**Files:**
- Modify: `Makefile`, `.gitignore`, `.github/workflows/scrape-and-deploy.yml`

- [ ] **Step 1: Update Makefile**

Read current file, then replace:

```makefile
.PHONY: scrape build serve clean

scrape:
	python -m scraper.main

build:
	mkdir -p site/maps site/daily
	cp data/assets/maps/* site/maps/ 2>/dev/null || true
	cp data/summary.csv site/summary.csv 2>/dev/null || true
	cp data/daily/*.json site/daily/ 2>/dev/null || true

serve: build
	cd site && python -m http.server 8000

clean:
	rm -rf site/maps site/daily site/summary.csv scraper_result.txt
```

- [ ] **Step 2: Update .gitignore**

Read current file, then add `site/daily/` after `site/summary.csv`:

```
__pycache__/
*.pyc
.pytest_cache/
site/maps/
site/summary.csv
site/daily/
scraper_result.txt
venv/
.env
```

- [ ] **Step 3: Update GitHub Actions workflow**

Read current file, then modify the "Run scraper" step to pass `NVIDIA_API_KEY`:

```yaml
      - name: Run scraper
        env:
          NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}
        run: python -m scraper.main
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add Makefile .gitignore .github/workflows/scrape-and-deploy.yml && git commit -m "feat: update build infra for daily JSON copy and NVIDIA API key"
```

---

## Task 9: End-to-end local verification

- [ ] **Step 1: Install new dependency**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && pip install -r requirements.txt
```

- [ ] **Step 2: Run all tests**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && python -m pytest -v
```

Expected: 17 passed.

- [ ] **Step 3: Re-scrape to get positions data**

Delete existing data to force a re-scrape with vision/zones:

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && rm data/daily/2026-03-19.json data/assets/maps/2026-03-19.jpg data/summary.csv
python -m scraper.main
```

Check the JSON now has a `positions` field:

```bash
python -c "import json; d=json.load(open('data/daily/2026-03-19.json')); print(json.dumps(d.get('positions'), indent=2))"
```

Expected: `positions` with either `"source": "vision"` (if NVIDIA_API_KEY is set) or `"source": "zones"`.

- [ ] **Step 4: Build and preview site**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && make build && make serve
```

Open `http://localhost:8000`. Verify:
- Light theme (white background)
- Interactive map with Taiwan coastline visible
- Aircraft markers (red circles) and/or vessel markers (blue diamonds) on the map
- Badge shows "Positions: AI-extracted" or "Positions: Estimated"
- Stats cards, trend chart, timeline slider all still work
- Clicking chart or dragging slider updates map markers

- [ ] **Step 5: Commit updated data**

```bash
cd /Volumes/DATA/workspace/taiwan-strait-monitor && git add data/ && git commit -m "data: re-scrape with positions data"
```
