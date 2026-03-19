import re

from bs4 import BeautifulSoup


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


def _roc_to_iso(roc_year: int, month: int, day: int) -> str:
    """Convert ROC year/month/day to ISO 8601 datetime at 06:00 UTC+8."""
    year = roc_year + 1911
    return f"{year:04d}-{month:02d}-{day:02d}T06:00:00+08:00"


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

        # Date is in a child <div class="date"> element
        date_div = link.find("div", class_="date")
        if date_div:
            date_str = parse_roc_date_compact(date_div.get_text(strip=True))
        else:
            # Fallback: scan parent text for compact date pattern
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


def parse_detail_page(html: str) -> dict:
    """Parse MND detail page HTML into structured data."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text()

    # Extract date period: "115年3月18日（星期三）0600時至115年3月19日（星期四）0600時止"
    period_match = re.search(
        r"(\d+)年(\d+)月(\d+)日[^至]*0600時至(\d+)年(\d+)月(\d+)日[^0-9]*0600時",
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

    # Extract crossed median: "逾越中線...N架次" (inside parentheses)
    median_match = re.search(r"逾越中線[^（(）)0-9]*(\d+)架次", text)
    crossed_median = int(median_match.group(1)) if median_match else 0

    # Extract entered ADIZ: may differ from crossed_median
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
    if re.search(r"南部(?!.*西南)", text) and "空域" in text:
        adiz_regions.append("south")

    # Extract naval vessels: "共艦9艘"
    naval_match = re.search(r"共艦(\d+)艘", text)
    naval = int(naval_match.group(1)) if naval_match else 0

    # Extract official vessels: "公務船2艘"
    official_match = re.search(r"公務船(\d+)艘", text)
    official = int(official_match.group(1)) if official_match else 0

    # Extract map image URL from <img> tag containing "NewUpload"
    map_image_url = ""
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "NewUpload" in src and src.upper().endswith(".JPG"):
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
