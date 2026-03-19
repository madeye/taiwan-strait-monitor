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
        print("Downloading map image...")
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
