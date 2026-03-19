"""Backfill historical data from MND list pages."""
import pathlib
import time
import sys

from scraper.fetcher import _session, BASE_URL, TIMEOUT
from scraper.parser import parse_list_page, parse_detail_page
from scraper.storage import save_daily_report, save_map_image, regenerate_csv
from scraper.vision import extract_positions
from scraper.zones import estimate_positions

DATA_DIR = pathlib.Path("data")


def fetch_list_page_num(page: int) -> str:
    """Fetch a specific page of the MND list."""
    if page <= 1:
        url = f"{BASE_URL}/PublishTable.aspx?Types=%E5%8D%B3%E6%99%82%E8%BB%8D%E4%BA%8B%E5%8B%95%E6%85%8B&title=%E5%9C%8B%E9%98%B2%E6%B6%88%E6%81%AF"
    else:
        url = f"{BASE_URL}/news/plaactlist/{page}"
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def backfill(start_date: str, end_date: str):
    """Fetch all reports between start_date and end_date (YYYY-MM-DD)."""
    # Collect all report entries across pages
    all_reports = []
    for page in range(1, 30):  # safety limit
        print(f"Fetching list page {page}...")
        html = fetch_list_page_num(page)
        reports = parse_list_page(html)

        if not reports:
            print(f"No reports on page {page}, stopping.")
            break

        oldest_date = reports[-1]["date"]
        all_reports.extend(reports)

        print(f"  Found {len(reports)} reports, oldest: {oldest_date}")

        if oldest_date < start_date:
            break

        time.sleep(1)  # be polite

    # Filter to date range and deduplicate
    seen = set()
    targets = []
    for r in all_reports:
        if start_date <= r["date"] <= end_date and r["id"] not in seen:
            seen.add(r["id"])
            targets.append(r)

    # Sort oldest first
    targets.sort(key=lambda r: r["date"])

    print(f"\n{len(targets)} reports to fetch ({targets[0]['date']} to {targets[-1]['date']})")

    fetched = 0
    skipped = 0
    failed = 0

    for r in targets:
        date_str = r["date"]
        json_path = DATA_DIR / "daily" / f"{date_str}.json"

        if json_path.exists():
            skipped += 1
            continue

        try:
            print(f"[{fetched + skipped + failed + 1}/{len(targets)}] Fetching {date_str} (ID {r['id']})...")

            detail_html = _session().get(
                f"{BASE_URL}/news/plaact/{r['id']}", timeout=TIMEOUT
            ).text
            report = parse_detail_page(detail_html)

            # Download map image
            image_path = ""
            if report.get("map_image_url"):
                from scraper.fetcher import fetch_image
                image_bytes = fetch_image(report["map_image_url"])
                saved_path = save_map_image(image_bytes, date_str, DATA_DIR)
                report["map_image"] = f"assets/maps/{date_str}.jpg"
                if saved_path and saved_path.exists():
                    image_path = str(saved_path)
            else:
                report["map_image"] = ""

            # Extract positions
            positions = None
            if image_path:
                positions = extract_positions(image_path)
            if positions is None:
                positions = estimate_positions(report)
            report["positions"] = positions

            report.pop("map_image_url", None)
            report["source_url"] = f"https://www.mnd.gov.tw/news/plaact/{r['id']}"

            save_daily_report(report, DATA_DIR)
            fetched += 1

            time.sleep(2)  # be polite

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            continue

    # Regenerate CSV
    regenerate_csv(DATA_DIR)

    print(f"\nDone: {fetched} fetched, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-10-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-03-19"
    backfill(start, end)
