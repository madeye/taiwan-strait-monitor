import json

from scraper.refresh_zones import refresh_zone_positions
from scraper.storage import save_daily_report
from scraper.zones import estimate_positions


def test_refresh_stale_positions_preserves_report_and_is_idempotent(tmp_path):
    report = {
        "date": "2026-03-19",
        "aircraft": {"total": 5, "adiz_regions": ["north", "central"]},
        "vessels": {"naval": 9, "official": 2},
        "source_url": "https://example.com/report",
        "positions": {
            "source": "zones",
            "aircraft": [{"lat": 24.0, "lon": 120.5, "label": "central"}],
            "vessels": [{"lat": 24.5, "lon": 120.5, "type": "naval"}],
        },
    }
    path = save_daily_report(report, tmp_path)
    assert refresh_zone_positions(tmp_path) == 1
    saved = json.loads(path.read_text())
    assert saved == {**report, "positions": estimate_positions(report)}
    assert saved["positions"]["vessels"][0]["lon"] == 119.5
    before = path.read_bytes()
    assert refresh_zone_positions(tmp_path) == 0
    assert path.read_bytes() == before


def test_refresh_preserves_ai_and_missing_positions(tmp_path):
    paths = []
    for i, source in enumerate(("vision", "vision+cv", None), start=1):
        report = {"date": f"2026-03-{i:02d}", "vessels": {"naval": 3}}
        if source:
            report["positions"] = {
                "source": source,
                "aircraft": [],
                "vessels": [{"lat": 24.5, "lon": 120.5, "type": "naval"}],
            }
        path = save_daily_report(report, tmp_path)
        paths.append((path, path.read_bytes()))
    assert refresh_zone_positions(tmp_path) == 0
    for path, before in paths:
        assert path.read_bytes() == before
