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
