from scraper.parser import parse_roc_date_compact, parse_roc_date_prose, parse_detail_page, parse_list_page


def test_parse_roc_date_compact():
    assert parse_roc_date_compact("115.03.19") == "2026-03-19"


def test_parse_roc_date_compact_single_digit():
    assert parse_roc_date_compact("115.1.5") == "2026-01-05"


def test_parse_roc_date_prose():
    assert parse_roc_date_prose("中華民國115年3月18日") == "2026-03-18"


def test_parse_roc_date_prose_with_day_of_week():
    assert parse_roc_date_prose("中華民國115年3月18日（星期三）") == "2026-03-18"


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


def test_parse_list_page():
    html = (FIXTURES / "list_page.html").read_text(encoding="utf-8")
    reports = parse_list_page(html)

    assert len(reports) > 0
    first = reports[0]
    assert "id" in first
    assert "date" in first
    assert first["url"].startswith("/news/plaact/") or first["url"].startswith("news/plaact/")
