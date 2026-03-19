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
    assert rows[0]["date"] == "2026-03-17"
    assert rows[0]["aircraft_total"] == "10"
