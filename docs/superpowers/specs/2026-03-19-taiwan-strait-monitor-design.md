# Taiwan Strait Monitor — Design Spec

## Overview

A static-site dashboard that tracks PLA military activity around Taiwan, powered by daily automated scraping of Taiwan's Ministry of National Defense (MND) reports. Deployed via GitHub Pages with GitHub Actions for automation.

## Goals

- Scrape MND daily PLA activity reports (aircraft sorties, naval vessels, route maps)
- Store structured data as JSON (primary) and CSV (summary)
- Render a single-page dashboard with time-series trends and map archive
- Fully automated: GitHub Actions scrapes daily, commits data, deploys site

## Non-Goals

- Real-time monitoring (daily granularity is sufficient)
- Aircraft/vessel type breakdown (future enhancement)
- ADIZ region-level analytics (future enhancement)
- Event correlation or anomaly detection (future enhancement)
- User accounts, backend API, or database

## Data Source

**Primary:** Taiwan MND official website

| Item | Detail |
|------|--------|
| List page (zh) | `https://www.mnd.gov.tw/PublishTable.aspx?Types=即時軍事動態&title=國防消息` |
| Detail page pattern | `https://www.mnd.gov.tw/news/plaact/{ID}` |
| Map image | Extracted from `<img src>` on detail page HTML; not constructible from known parts. Example: `https://www.mnd.gov.tw/NewUpload/202603/1150319_臺海周邊海、空域活動示意圖_255136.JPG` |
| Update cadence | Daily, covering prior day 06:00 to current day 06:00 (UTC+8). Reports may appear later in the morning (not always at 06:00 sharp). |
| Date format | ROC calendar in two forms: compact `115.03.19` (list page) and prose `中華民國115年3月18日` (detail page). Conversion: Gregorian year = ROC year + 1911. |
| Data format | Unstructured HTML text, requires parsing |
| Scraping policy | One request per day; set a descriptive `User-Agent` header; confirm `robots.txt` permits access before launch; set request timeout of 30s. |

## Data Model

Each daily report is stored as `data/daily/YYYY-MM-DD.json`:

```json
{
  "date": "2026-03-19",
  "period": {
    "start": "2026-03-18T06:00:00+08:00",
    "end": "2026-03-19T06:00:00+08:00"
  },
  "aircraft": {
    "total": 12,
    "crossed_median": 5,
    "entered_adiz": 5,
    "adiz_regions": ["north", "central", "southwest"]
  },
  "vessels": {
    "naval": 9,
    "official": 2
  },
  "source_url": "https://www.mnd.gov.tw/news/plaact/86346",
  "map_image": "assets/maps/2026-03-19.jpg"
}
```

A summary CSV at `data/summary.csv` is regenerated on each run:

```
date,aircraft_total,crossed_median,entered_adiz,vessels_naval,vessels_official,map_image
2026-03-19,12,5,5,9,2,maps/2026-03-19.jpg
```

**Note:** `summary.csv` intentionally omits `adiz_regions` (a list) for simplicity. The daily JSON files are the lossless record. Future ADIZ region analytics would require `app.js` to fetch individual JSON files.

**Map naming convention:** Downloaded map images are saved as `YYYY-MM-DD.jpg` regardless of the original MND filename. In the JSON, `map_image` uses a `data/`-relative path (`assets/maps/YYYY-MM-DD.jpg`). In the CSV, `map_image` uses a `site/`-relative path (`maps/YYYY-MM-DD.jpg`), which `app.js` uses directly to render the map gallery.

## Architecture

### Project Structure

```
taiwan-strait-monitor/
├── scraper/
│   ├── __init__.py
│   ├── fetcher.py        # HTTP requests to MND site
│   ├── parser.py         # HTML parsing -> structured data
│   ├── storage.py        # Write JSON + update CSV
│   └── main.py           # Entry point: fetch -> parse -> store
├── site/
│   ├── index.html        # Single page dashboard
│   ├── js/
│   │   └── app.js        # Fetch CSV, render charts with ECharts
│   ├── css/
│   │   └── style.css     # Minimal styling
│   └── maps/             # Build artifact: copied from data/assets/maps, only exists on gh-pages
├── data/
│   ├── daily/            # Per-day JSON files
│   ├── assets/
│   │   └── maps/         # Downloaded route map images
│   └── summary.csv       # Aggregated CSV
├── .github/
│   └── workflows/
│       └── scrape-and-deploy.yml
├── Makefile              # Local dev commands: scrape, build, serve, clean
├── requirements.txt
├── .gitignore            # Excludes site/maps/, site/summary.csv, __pycache__, etc.
└── README.md
```

### Scraper Pipeline

1. **fetcher.py** — Requests the MND list page, extracts the latest report ID, fetches the detail page HTML. Extracts the map image URL from `<img src>` on the detail page and downloads it. Uses `requests` with retry logic, 30s timeout, and descriptive `User-Agent`.
2. **parser.py** — Parses detail page HTML with `BeautifulSoup`. Extracts: date/period, aircraft counts, median crossing count, ADIZ entries, vessel counts, map image URL. Handles ROC date conversion (Gregorian = ROC + 1911) in both compact (`115.03.19`) and prose (`中華民國115年3月18日`) formats. Parses the Chinese-language page (more detailed). `source_url` stored is the Chinese detail page URL.
3. **storage.py** — Validates parsed data before writing (refuses to write if all counts are None, which indicates a parse failure). Writes to a temp file and atomically renames on success. Downloads map image as `YYYY-MM-DD.jpg`. Regenerates `summary.csv` from all daily JSON files.
4. **main.py** — Orchestrates the pipeline. Skips if today's data already exists (idempotent). Writes a `scraper_result.txt` file with value `new` or `skipped` for the workflow to check. Exits 0 in both cases; exits non-zero only on error.

**Dependencies:** `requests`, `beautifulsoup4`, `lxml`

**Error handling:** If scraping fails (site down, format change), the workflow logs the error and exits non-zero. No partial data is written (atomic write ensures this).

### Static Site

- **Header:** Title, last updated timestamp, link to MND source
- **Trend chart:** ECharts line chart showing daily aircraft sorties and vessel counts. X-axis = date, dual Y-axes.
- **Map gallery:** Most recent route map displayed prominently, scrollable archive of past maps.
- **Stats cards:** Current day's numbers (total aircraft, crossed median, vessels).

Data loading: `app.js` fetches `summary.csv` at page load and renders client-side. Map paths are derived from the date column using the convention `maps/YYYY-MM-DD.jpg`. ECharts loaded via CDN. No build step.

### GitHub Actions Workflow

**File:** `.github/workflows/scrape-and-deploy.yml`

**Schedule:** `cron: '0 0 * * *'` (00:00 UTC = 08:00 UTC+8, giving MND 2 hours after the 06:00 cutoff to publish)

**Triggers:** Scheduled + `workflow_dispatch` for manual runs.

**Steps:**

1. Checkout repo
2. Setup Python, install dependencies from `requirements.txt`
3. Run `python -m scraper.main`
4. Check `scraper_result.txt` — if `skipped`, stop workflow here
5. Commit `data/` changes only (`data/daily/`, `data/assets/maps/`, `data/summary.csv`) to `main` branch (bot identity)
6. Copy `data/assets/maps/*` to `site/maps/` and `data/summary.csv` to `site/`
7. Deploy `site/` to GitHub Pages via `peaceiris/actions-gh-pages` (pushes to `gh-pages` branch)

**Note:** `site/maps/` and `site/summary.csv` are not committed to `main` — they are build artifacts generated for the deploy step only.

### Local Development

A `Makefile` at the project root provides local equivalents of the CI pipeline:

```makefile
scrape:          # Run scraper (fetch latest MND data)
build:           # Copy data assets into site/ for local preview
serve:           # Build + start a local HTTP server (python -m http.server) in site/
clean:           # Remove build artifacts from site/maps/ and site/summary.csv
```

**Usage:**

```bash
pip install -r requirements.txt
make scrape   # fetch today's data
make serve    # preview dashboard at http://localhost:8000
```

`make serve` runs `make build` first (copies `data/assets/maps/` and `data/summary.csv` into `site/`), then starts Python's built-in HTTP server. No extra dependencies needed.

`site/maps/` and `site/summary.csv` are in `.gitignore` — they are always generated, never committed to `main`.

## Future Enhancements

These are explicitly out of scope for MVP but noted for later:

- Aircraft/vessel type breakdown and statistics
- ADIZ region heatmaps
- Historical event annotations (exercises, political events)
- Anomaly detection and alerting
- English MND page as fallback source
- Backfill historical data from MND archives
