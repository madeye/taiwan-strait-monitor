"""Refresh stored zone estimates without fetching reports or changing AI positions."""

import argparse
import json
import pathlib

from scraper.storage import save_daily_report
from scraper.zones import estimate_positions


def refresh_zone_positions(data_dir: pathlib.Path) -> int:
    updated = 0
    for path in sorted((data_dir / "daily").glob("*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        positions = report.get("positions") or {}
        if positions.get("source") != "zones":
            continue
        refreshed = estimate_positions(report)
        if positions != refreshed:
            report["positions"] = refreshed
            save_daily_report(report, data_dir)
            updated += 1
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=pathlib.Path, default=pathlib.Path("data"))
    args = parser.parse_args()
    print(f"Refreshed zone estimates in {refresh_zone_positions(args.data_dir)} reports")
