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
