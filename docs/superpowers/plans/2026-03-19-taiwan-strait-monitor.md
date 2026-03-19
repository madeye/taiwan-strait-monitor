# Taiwan Strait Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated daily scraper for Taiwan MND PLA activity reports with a static dashboard deployed to GitHub Pages.

**Architecture:** Python scraper fetches and parses MND HTML pages, stores structured JSON + summary CSV. A static HTML/JS site uses ECharts to render trends with an interactive timeline slider. GitHub Actions runs the pipeline daily and deploys to GitHub Pages.

**Tech Stack:** Python 3.11+ (requests, beautifulsoup4, lxml), HTML/CSS/JS (ECharts via CDN), GitHub Actions, GNU Make

**Spec:** `docs/superpowers/specs/2026-03-19-taiwan-strait-monitor-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `scraper/__init__.py` | Package marker |
| `scraper/fetcher.py` | HTTP requests to MND: list page, detail page, map image download |
| `scraper/parser.py` | HTML parsing: extract dates, counts, image URLs from detail page |
| `scraper/storage.py` | Write daily JSON, download map image, regenerate summary CSV |
| `scraper/main.py` | Pipeline orchestration, idempotency check, result signaling |
| `site/index.html` | Dashboard layout: header, chart container, timeline, map, stats cards |
| `site/js/app.js` | CSV loading, ECharts rendering, timeline slider, date sync logic |
| `site/css/style.css` | Dashboard styling |
| `Makefile` | Local dev commands: scrape, build, serve, clean |
| `.github/workflows/scrape-and-deploy.yml` | CI: daily scrape, commit, deploy |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Exclude build artifacts, __pycache__, etc. |
| `pyproject.toml` | Pytest config (pythonpath) |
| `tests/test_parser.py` | Unit tests for HTML parsing and ROC date conversion |
| `tests/test_storage.py` | Unit tests for JSON/CSV writing |
| `tests/fixtures/detail_page.html` | Saved MND detail page HTML for offline testing |
| `tests/fixtures/list_page.html` | Saved MND list page HTML for offline testing |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`, `.gitignore`, `scraper/__init__.py`, `Makefile`

- [ ] **Step 1: Create requirements.txt**

```
requests>=2.31,<3
beautifulsoup4>=4.12,<5
lxml>=5.0,<6
pytest>=8.0,<9
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
site/maps/
site/summary.csv
scraper_result.txt
venv/
.env
```

- [ ] **Step 3: Create pyproject.toml**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 4: Create scraper/__init__.py**

Empty file.

- [ ] **Step 5: Create Makefile**

```makefile
.PHONY: scrape build serve clean

scrape:
	python -m scraper.main

build:
	mkdir -p site/maps
	cp data/assets/maps/* site/maps/ 2>/dev/null || true
	cp data/summary.csv site/summary.csv 2>/dev/null || true

serve: build
	cd site && python -m http.server 8000

clean:
	rm -rf site/maps site/summary.csv scraper_result.txt
```

- [ ] **Step 6: Create directory structure**

```bash
mkdir -p data/daily data/assets/maps tests/fixtures
```

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore pyproject.toml scraper/__init__.py Makefile
git commit -m "feat: project scaffolding with dependencies and Makefile"
```

---

## Task 2: HTML test fixtures

**Files:**
- Create: `tests/fixtures/detail_page.html`, `tests/fixtures/list_page.html`

- [ ] **Step 1: Save a real MND detail page as a test fixture**

Fetch `https://www.mnd.gov.tw/news/plaact/86346` and save the HTML response body to `tests/fixtures/detail_page.html`. This is the page for 2026-03-19 with 12 aircraft, 9 naval vessels, 2 official vessels.

```bash
curl -s -o tests/fixtures/detail_page.html \
  -H "User-Agent: taiwan-strait-monitor/1.0" \
  "https://www.mnd.gov.tw/news/plaact/86346"
```

- [ ] **Step 2: Save a real MND list page as a test fixture**

```bash
curl -s -o tests/fixtures/list_page.html \
  -H "User-Agent: taiwan-strait-monitor/1.0" \
  "https://www.mnd.gov.tw/PublishTable.aspx?Types=%E5%8D%B3%E6%99%82%E8%BB%8D%E4%BA%8B%E5%8B%95%E6%85%8B&title=%E5%9C%8B%E9%98%B2%E6%B6%88%E6%81%AF"
```

- [ ] **Step 3: Verify fixtures are non-empty and contain expected content**

```bash
grep -c "plaact" tests/fixtures/list_page.html   # should be > 0
grep -c "共機" tests/fixtures/detail_page.html    # should be > 0 (or 偵獲)
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/
git commit -m "feat: add MND HTML test fixtures for offline testing"
```

---

## Task 3: Parser — ROC date conversion

**Files:**
- Create: `scraper/parser.py`, `tests/test_parser.py`

- [ ] **Step 1: Write failing tests for ROC date parsing**

```python
# tests/test_parser.py
from scraper.parser import parse_roc_date_compact, parse_roc_date_prose


def test_parse_roc_date_compact():
    assert parse_roc_date_compact("115.03.19") == "2026-03-19"


def test_parse_roc_date_compact_single_digit():
    assert parse_roc_date_compact("115.1.5") == "2026-01-05"


def test_parse_roc_date_prose():
    assert parse_roc_date_prose("中華民國115年3月18日") == "2026-03-18"


def test_parse_roc_date_prose_with_day_of_week():
    assert parse_roc_date_prose("中華民國115年3月18日（星期三）") == "2026-03-18"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py -v
```

Expected: FAIL — `scraper.parser` does not exist yet.

- [ ] **Step 3: Implement ROC date parsing**

```python
# scraper/parser.py
import re


def parse_roc_date_compact(date_str: str) -> str:
    """Parse compact ROC date like '115.03.19' to '2026-03-19'."""
    parts = date_str.strip().split(".")
    year = int(parts[0]) + 1911
    month = int(parts[1])
    day = int(parts[2])
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_roc_date_prose(text: str) -> str:
    """Parse prose ROC date like '中華民國115年3月18日' to '2026-03-18'."""
    match = re.search(r"(\d+)年(\d+)月(\d+)日", text)
    if not match:
        raise ValueError(f"Cannot parse ROC date from: {text}")
    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scraper/parser.py tests/test_parser.py
git commit -m "feat: ROC date parsing (compact and prose formats)"
```

---

## Task 4: Parser — detail page extraction

**Files:**
- Modify: `scraper/parser.py`
- Modify: `tests/test_parser.py`

- [ ] **Step 1: Write failing test for detail page parsing using fixture**

```python
# tests/test_parser.py (append)
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_parse_detail_page():
    html = (FIXTURES / "detail_page.html").read_text(encoding="utf-8")
    result = parse_detail_page(html)

    assert result["date"] == "2026-03-19"
    assert result["period"]["start"] == "2026-03-18T06:00:00+08:00"
    assert result["period"]["end"] == "2026-03-19T06:00:00+08:00"
    assert result["aircraft"]["total"] == 12
    assert result["aircraft"]["crossed_median"] == 5
    assert result["vessels"]["naval"] == 9
    assert result["vessels"]["official"] == 2
    assert result["map_image_url"].endswith(".JPG") or result["map_image_url"].endswith(".jpg")
```

Update the import line to include `parse_detail_page`:

```python
from scraper.parser import parse_roc_date_compact, parse_roc_date_prose, parse_detail_page
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser.py::test_parse_detail_page -v
```

Expected: FAIL — `parse_detail_page` not defined.

- [ ] **Step 3: Implement parse_detail_page**

Add to `scraper/parser.py`:

```python
from bs4 import BeautifulSoup


def parse_detail_page(html: str) -> dict:
    """Parse MND detail page HTML into structured data."""
    soup = BeautifulSoup(html, "lxml")

    # Extract the main report text — look for the paragraph with activity data
    text = soup.get_text()

    # Extract date period: "115年3月18日（星期三）0600時至115年3月19日（星期四）0600時"
    period_match = re.search(
        r"(\d+)年(\d+)月(\d+)日[^0-9]*0600時至(\d+)年(\d+)月(\d+)日[^0-9]*0600時",
        text,
    )
    if not period_match:
        raise ValueError("Cannot find date period in detail page")

    start_date = _roc_to_iso(
        int(period_match.group(1)),
        int(period_match.group(2)),
        int(period_match.group(3)),
    )
    end_date = _roc_to_iso(
        int(period_match.group(4)),
        int(period_match.group(5)),
        int(period_match.group(6)),
    )

    # Extract aircraft count: "共機12架次"
    aircraft_match = re.search(r"共機(\d+)架次", text)
    aircraft_total = int(aircraft_match.group(1)) if aircraft_match else 0

    # Extract crossed median: "逾越中線...N架次"
    median_match = re.search(r"逾越中線[^0-9]*(\d+)架次", text)
    crossed_median = int(median_match.group(1)) if median_match else 0

    # Extract entered ADIZ: same count as crossed median in current format
    # or separate "進入...空域N架次"
    adiz_match = re.search(r"進入[^0-9]*空域(\d+)架次", text)
    entered_adiz = int(adiz_match.group(1)) if adiz_match else crossed_median

    # Extract ADIZ regions
    adiz_regions = []
    if "北部" in text and "空域" in text:
        adiz_regions.append("north")
    if "中部" in text and "空域" in text:
        adiz_regions.append("central")
    if "西南" in text and "空域" in text:
        adiz_regions.append("southwest")
    if "東南" in text and "空域" in text:
        adiz_regions.append("southeast")
    if "南部" in text and "空域" in text:
        adiz_regions.append("south")

    # Extract naval vessels: "共艦9艘"
    naval_match = re.search(r"共艦(\d+)艘", text)
    naval = int(naval_match.group(1)) if naval_match else 0

    # Extract official vessels: "公務船2艘"
    official_match = re.search(r"公務船(\d+)艘", text)
    official = int(official_match.group(1)) if official_match else 0

    # Extract map image URL from <img> tag
    map_image_url = ""
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "NewUpload" in src and ("示意圖" in src or "JPG" in src.upper()):
            map_image_url = src
            break

    return {
        "date": end_date.split("T")[0],
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "aircraft": {
            "total": aircraft_total,
            "crossed_median": crossed_median,
            "entered_adiz": entered_adiz,
            "adiz_regions": adiz_regions,
        },
        "vessels": {
            "naval": naval,
            "official": official,
        },
        "map_image_url": map_image_url,
    }


def _roc_to_iso(roc_year: int, month: int, day: int) -> str:
    """Convert ROC year/month/day to ISO 8601 datetime at 06:00 UTC+8."""
    year = roc_year + 1911
    return f"{year:04d}-{month:02d}-{day:02d}T06:00:00+08:00"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: all passed. If the test fails, inspect the fixture HTML to adjust regex patterns — the MND page format may have minor variations. The key patterns to validate against the fixture:
- `共機N架次` for aircraft
- `共艦N艘` for naval vessels
- `公務船N艘` for official vessels
- Date period with `0600時至...0600時`

- [ ] **Step 5: Commit**

```bash
git add scraper/parser.py tests/test_parser.py
git commit -m "feat: parse MND detail page (aircraft, vessels, dates, map)"
```

---

## Task 5: Parser — list page extraction

**Files:**
- Modify: `scraper/parser.py`
- Modify: `tests/test_parser.py`

- [ ] **Step 1: Write failing test for list page parsing**

```python
# tests/test_parser.py (append)


def test_parse_list_page():
    html = (FIXTURES / "list_page.html").read_text(encoding="utf-8")
    reports = parse_list_page(html)

    assert len(reports) > 0
    first = reports[0]
    assert "id" in first  # numeric report ID
    assert "date" in first  # Gregorian date string
    assert first["url"].startswith("/news/plaact/") or first["url"].startswith("news/plaact/")
```

Update import to include `parse_list_page`.

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser.py::test_parse_list_page -v
```

- [ ] **Step 3: Implement parse_list_page**

Add to `scraper/parser.py`:

```python
def parse_list_page(html: str) -> list[dict]:
    """Parse MND list page, returning report entries sorted newest-first."""
    soup = BeautifulSoup(html, "lxml")
    reports = []

    for link in soup.find_all("a", href=re.compile(r"news/plaact/\d+")):
        href = link.get("href", "")
        id_match = re.search(r"plaact/(\d+)", href)
        if not id_match:
            continue

        report_id = id_match.group(1)

        # Find the date near this link — look in parent/sibling text
        parent_text = link.parent.get_text() if link.parent else ""
        date_match = re.search(r"(\d+\.\d+\.\d+)", parent_text)
        date_str = parse_roc_date_compact(date_match.group(1)) if date_match else ""

        url = href if href.startswith("/") else f"/{href}"

        reports.append({
            "id": report_id,
            "date": date_str,
            "url": url,
        })

    return reports
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/parser.py tests/test_parser.py
git commit -m "feat: parse MND list page for report IDs and dates"
```

---

## Task 6: Fetcher

**Files:**
- Create: `scraper/fetcher.py`

- [ ] **Step 1: Implement fetcher**

```python
# scraper/fetcher.py
import requests
from urllib.parse import urljoin

BASE_URL = "https://www.mnd.gov.tw"
LIST_URL = f"{BASE_URL}/PublishTable.aspx?Types=%E5%8D%B3%E6%99%82%E8%BB%8D%E4%BA%8B%E5%8B%95%E6%85%8B&title=%E5%9C%8B%E9%98%B2%E6%B6%88%E6%81%AF"
USER_AGENT = "taiwan-strait-monitor/1.0 (+https://github.com/user/taiwan-strait-monitor)"
TIMEOUT = 30


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    a = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", a)
    return s


def fetch_list_page() -> str:
    """Fetch the MND PLA activities list page HTML."""
    resp = _session().get(LIST_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def fetch_detail_page(report_id: str) -> str:
    """Fetch a single MND report detail page HTML."""
    url = f"{BASE_URL}/news/plaact/{report_id}"
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def fetch_image(image_url: str) -> bytes:
    """Download a map image and return raw bytes."""
    url = image_url if image_url.startswith("http") else urljoin(BASE_URL, image_url)
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content
```

- [ ] **Step 2: Commit**

```bash
git add scraper/fetcher.py
git commit -m "feat: MND HTTP fetcher with retry and timeout"
```

---

## Task 7: Storage — JSON + CSV + map image

**Files:**
- Create: `scraper/storage.py`, `tests/test_storage.py`

- [ ] **Step 1: Write failing tests for storage**

```python
# tests/test_storage.py
import csv
import json
import pathlib

from scraper.storage import save_daily_report, regenerate_csv


def test_save_daily_report(tmp_path):
    data_dir = tmp_path / "data"
    report = {
        "date": "2026-03-19",
        "period": {
            "start": "2026-03-18T06:00:00+08:00",
            "end": "2026-03-19T06:00:00+08:00",
        },
        "aircraft": {
            "total": 12,
            "crossed_median": 5,
            "entered_adiz": 5,
            "adiz_regions": ["north", "central", "southwest"],
        },
        "vessels": {"naval": 9, "official": 2},
        "source_url": "https://www.mnd.gov.tw/news/plaact/86346",
        "map_image": "assets/maps/2026-03-19.jpg",
    }

    save_daily_report(report, data_dir)

    json_path = data_dir / "daily" / "2026-03-19.json"
    assert json_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["aircraft"]["total"] == 12
    assert saved["vessels"]["naval"] == 9


def test_save_daily_report_rejects_empty_data(tmp_path):
    data_dir = tmp_path / "data"
    report = {
        "date": "2026-03-19",
        "period": {"start": "", "end": ""},
        "aircraft": {},
        "vessels": {},
        "source_url": "",
        "map_image": "",
    }
    import pytest
    with pytest.raises(ValueError, match="empty"):
        save_daily_report(report, data_dir)


def test_regenerate_csv(tmp_path):
    data_dir = tmp_path / "data"
    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True)

    for i, (ac, nav) in enumerate([(10, 5), (8, 3)]):
        report = {
            "date": f"2026-03-{17 + i:02d}",
            "period": {"start": "", "end": ""},
            "aircraft": {"total": ac, "crossed_median": 0, "entered_adiz": 0, "adiz_regions": []},
            "vessels": {"naval": nav, "official": 0},
            "source_url": "",
            "map_image": f"assets/maps/2026-03-{17 + i:02d}.jpg",
        }
        (daily_dir / f"2026-03-{17 + i:02d}.json").write_text(
            json.dumps(report), encoding="utf-8"
        )

    regenerate_csv(data_dir)

    csv_path = data_dir / "summary.csv"
    assert csv_path.exists()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-03-17"  # sorted by date
    assert rows[0]["aircraft_total"] == "10"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage.py -v
```

- [ ] **Step 3: Implement storage**

```python
# scraper/storage.py
import csv
import json
import pathlib
import tempfile


def save_daily_report(report: dict, data_dir: pathlib.Path) -> pathlib.Path:
    """Save a daily report as JSON. Atomic write. Rejects empty data."""
    ac = report.get("aircraft", {})
    vs = report.get("vessels", {})
    if ac.get("total") is None and vs.get("naval") is None and vs.get("official") is None:
        raise ValueError("Refusing to write empty report data — likely a parse failure")

    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    dest = daily_dir / f"{report['date']}.json"

    # Atomic write: write to temp file, then rename
    fd, tmp_path = tempfile.mkstemp(dir=daily_dir, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        pathlib.Path(tmp_path).replace(dest)
    except Exception:
        pathlib.Path(tmp_path).unlink(missing_ok=True)
        raise

    return dest


def save_map_image(image_bytes: bytes, date_str: str, data_dir: pathlib.Path) -> pathlib.Path:
    """Save map image as YYYY-MM-DD.jpg."""
    maps_dir = data_dir / "assets" / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    dest = maps_dir / f"{date_str}.jpg"
    dest.write_bytes(image_bytes)
    return dest


def regenerate_csv(data_dir: pathlib.Path) -> pathlib.Path:
    """Regenerate summary.csv from all daily JSON files."""
    daily_dir = data_dir / "daily"
    csv_path = data_dir / "summary.csv"

    rows = []
    for json_file in sorted(daily_dir.glob("*.json")):
        report = json.loads(json_file.read_text(encoding="utf-8"))
        ac = report.get("aircraft", {})
        vs = report.get("vessels", {})
        date = report["date"]
        map_img = report.get("map_image", "")
        csv_map = f"maps/{date}.jpg" if map_img else ""
        rows.append({
            "date": date,
            "aircraft_total": ac.get("total", 0),
            "crossed_median": ac.get("crossed_median", 0),
            "entered_adiz": ac.get("entered_adiz", 0),
            "vessels_naval": vs.get("naval", 0),
            "vessels_official": vs.get("official", 0),
            "map_image": csv_map,
        })

    fieldnames = [
        "date", "aircraft_total", "crossed_median", "entered_adiz",
        "vessels_naval", "vessels_official", "map_image",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_storage.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scraper/storage.py tests/test_storage.py
git commit -m "feat: storage layer with atomic JSON writes and CSV generation"
```

---

## Task 8: Main pipeline orchestrator

**Files:**
- Create: `scraper/main.py`

- [ ] **Step 1: Implement main.py**

```python
# scraper/main.py
import pathlib
import sys

from scraper.fetcher import fetch_list_page, fetch_detail_page, fetch_image
from scraper.parser import parse_list_page, parse_detail_page
from scraper.storage import save_daily_report, save_map_image, regenerate_csv

DATA_DIR = pathlib.Path("data")
RESULT_FILE = pathlib.Path("scraper_result.txt")


def main() -> int:
    # Check if today's data already exists
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

    # Fetch and parse detail page
    print(f"Fetching report {latest['id']} for {date_str}...")
    detail_html = fetch_detail_page(latest["id"])
    report = parse_detail_page(detail_html)

    # Download map image
    if report.get("map_image_url"):
        print(f"Downloading map image...")
        image_bytes = fetch_image(report["map_image_url"])
        save_map_image(image_bytes, date_str, DATA_DIR)
        report["map_image"] = f"assets/maps/{date_str}.jpg"
    else:
        report["map_image"] = ""

    # Remove temporary field, add source URL
    report.pop("map_image_url", None)
    report["source_url"] = f"https://www.mnd.gov.tw/news/plaact/{latest['id']}"

    # Save JSON
    save_daily_report(report, DATA_DIR)
    print(f"Saved {json_path}")

    # Regenerate CSV
    regenerate_csv(DATA_DIR)
    print("Regenerated summary.csv")

    RESULT_FILE.write_text("new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke test locally**

```bash
make scrape
cat data/daily/*.json | python -m json.tool | head -20
head data/summary.csv
```

Verify JSON and CSV contain today's data.

- [ ] **Step 3: Commit**

```bash
git add scraper/main.py
git commit -m "feat: scraper pipeline orchestrator with idempotency"
```

---

## Task 9: Static site — HTML + CSS

**Files:**
- Create: `site/index.html`, `site/css/style.css`

- [ ] **Step 1: Create index.html**

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

        <section id="chart-container">
            <div id="trend-chart"></div>
        </section>

        <section id="timeline-container">
            <input type="range" id="timeline-slider" min="0" max="0" value="0">
            <span id="timeline-date">-</span>
        </section>

        <section id="map-container">
            <h2>Route Map — <span id="map-date">-</span></h2>
            <img id="map-image" src="" alt="PLA activity route map">
        </section>
    </main>

    <script src="js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create style.css**

```css
/* site/css/style.css */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0a0a0a;
    color: #e0e0e0;
    max-width: 960px;
    margin: 0 auto;
    padding: 1rem;
}

header {
    text-align: center;
    margin-bottom: 2rem;
}

header h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
header p { color: #888; font-size: 0.85rem; }
header a { color: #5b9bd5; font-size: 0.85rem; }

#stats {
    display: flex;
    gap: 0.75rem;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 1.5rem;
}

.card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 0.75rem 1.25rem;
    text-align: center;
    min-width: 100px;
}

.card-value {
    display: block;
    font-size: 1.75rem;
    font-weight: bold;
    color: #fff;
}

.card-label {
    display: block;
    font-size: 0.75rem;
    color: #888;
    margin-top: 0.25rem;
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

#map-container { text-align: center; }
#map-container h2 { font-size: 1rem; margin-bottom: 0.75rem; }
#map-image {
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid #333;
}
```

- [ ] **Step 3: Commit**

```bash
git add site/index.html site/css/style.css
git commit -m "feat: dashboard HTML structure and dark theme CSS"
```

---

## Task 10: Static site — app.js (data loading + chart + timeline sync)

**Files:**
- Create: `site/js/app.js`

- [ ] **Step 1: Implement app.js**

```javascript
// site/js/app.js
(async function () {
    const resp = await fetch("summary.csv");
    const text = await resp.text();
    const rows = parseCSV(text);

    if (rows.length === 0) {
        document.getElementById("last-updated").textContent = "No data available";
        return;
    }

    // State
    let selectedIndex = rows.length - 1; // default to most recent

    // Setup timeline slider
    const slider = document.getElementById("timeline-slider");
    slider.min = 0;
    slider.max = rows.length - 1;
    slider.value = selectedIndex;

    // Setup chart
    const chart = echarts.init(document.getElementById("trend-chart"), "dark");
    const chartOption = {
        backgroundColor: "transparent",
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
    chart.setOption(chartOption);

    // Sync functions
    function selectDate(index) {
        selectedIndex = Math.max(0, Math.min(index, rows.length - 1));
        const row = rows[selectedIndex];

        // Update stats
        document.getElementById("stat-aircraft").textContent = row.aircraft_total;
        document.getElementById("stat-median").textContent = row.crossed_median;
        document.getElementById("stat-adiz").textContent = row.entered_adiz;
        document.getElementById("stat-naval").textContent = row.vessels_naval;
        document.getElementById("stat-official").textContent = row.vessels_official;

        // Update timeline
        slider.value = selectedIndex;
        document.getElementById("timeline-date").textContent = row.date;

        // Update map
        document.getElementById("map-date").textContent = row.date;
        const mapImg = document.getElementById("map-image");
        if (row.map_image) {
            mapImg.src = row.map_image;
            mapImg.style.display = "";
        } else {
            mapImg.src = "";
            mapImg.style.display = "none";
        }

        // Update chart marker
        chart.dispatchAction({
            type: "showTip",
            seriesIndex: 0,
            dataIndex: selectedIndex,
        });
    }

    // Event: slider drag
    slider.addEventListener("input", (e) => selectDate(parseInt(e.target.value)));

    // Event: chart click
    chart.on("click", (params) => selectDate(params.dataIndex));

    // Last updated
    const latest = rows[rows.length - 1];
    document.getElementById("last-updated").textContent = `Last updated: ${latest.date}`;

    // Responsive
    window.addEventListener("resize", () => chart.resize());

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

- [ ] **Step 2: Local test**

```bash
make serve
```

Open `http://localhost:8000` in a browser. Verify:
- Chart renders with data
- Stats cards show numbers
- Timeline slider is draggable and updates map + stats
- Clicking chart points updates the slider and map

- [ ] **Step 3: Commit**

```bash
git add site/js/app.js
git commit -m "feat: dashboard JS with ECharts, timeline slider, date sync"
```

---

## Task 11: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/scrape-and-deploy.yml`

- [ ] **Step 1: Create workflow**

```yaml
# .github/workflows/scrape-and-deploy.yml
name: Scrape and Deploy

on:
  schedule:
    - cron: '0 0 * * *'  # 00:00 UTC = 08:00 UTC+8
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scrape-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scraper
        run: python -m scraper.main

      - name: Check for new data
        id: check
        run: |
          if [ -f scraper_result.txt ] && [ "$(cat scraper_result.txt)" = "new" ]; then
            echo "has_new_data=true" >> "$GITHUB_OUTPUT"
          else
            echo "has_new_data=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Commit data
        if: steps.check.outputs.has_new_data == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git commit -m "data: $(date -u +%Y-%m-%d) PLA activity update"
          git push

      - name: Build site
        if: steps.check.outputs.has_new_data == 'true'
        run: make build

      - name: Deploy to GitHub Pages
        if: steps.check.outputs.has_new_data == 'true'
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
```

- [ ] **Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/scrape-and-deploy.yml
git commit -m "feat: GitHub Actions daily scrape and deploy workflow"
```

---

## Task 12: End-to-end local verification

- [ ] **Step 1: Clean slate test**

```bash
make clean
rm -rf data/daily/* data/assets/maps/* data/summary.csv
```

- [ ] **Step 2: Run full pipeline**

```bash
make scrape
```

Verify: `data/daily/YYYY-MM-DD.json` exists, `data/summary.csv` exists, `data/assets/maps/YYYY-MM-DD.jpg` exists.

- [ ] **Step 3: Preview site**

```bash
make serve
```

Open `http://localhost:8000`. Verify dashboard loads with one data point, chart renders, slider works (single point), map displays.

- [ ] **Step 4: Run scraper again to test idempotency**

```bash
make scrape
cat scraper_result.txt
```

Expected: `skipped`

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Final commit**

```bash
git add data/
git commit -m "data: initial scrape"
```
