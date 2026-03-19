from scraper.parser import parse_roc_date_compact, parse_roc_date_prose


def test_parse_roc_date_compact():
    assert parse_roc_date_compact("115.03.19") == "2026-03-19"


def test_parse_roc_date_compact_single_digit():
    assert parse_roc_date_compact("115.1.5") == "2026-01-05"


def test_parse_roc_date_prose():
    assert parse_roc_date_prose("中華民國115年3月18日") == "2026-03-18"


def test_parse_roc_date_prose_with_day_of_week():
    assert parse_roc_date_prose("中華民國115年3月18日（星期三）") == "2026-03-18"
