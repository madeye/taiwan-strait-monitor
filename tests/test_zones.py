from scraper.zones import estimate_positions


def test_estimate_positions_with_regions():
    report = {
        "aircraft": {
            "total": 12,
            "crossed_median": 5,
            "entered_adiz": 5,
            "adiz_regions": ["north", "central", "southwest"],
        },
        "vessels": {"naval": 9, "official": 2},
    }
    result = estimate_positions(report)

    assert result["source"] == "zones"
    assert len(result["aircraft"]) == 3
    assert result["aircraft"][0]["label"] == "north"
    assert 25.0 <= result["aircraft"][0]["lat"] <= 26.0
    assert len(result["vessels"]) == 2


def test_estimate_positions_no_regions():
    report = {
        "aircraft": {
            "total": 2,
            "crossed_median": 0,
            "entered_adiz": 0,
            "adiz_regions": [],
        },
        "vessels": {"naval": 3, "official": 0},
    }
    result = estimate_positions(report)

    assert result["source"] == "zones"
    assert len(result["aircraft"]) == 0
    assert len(result["vessels"]) == 1


def test_estimate_positions_no_vessels():
    report = {
        "aircraft": {
            "total": 0,
            "crossed_median": 0,
            "entered_adiz": 0,
            "adiz_regions": [],
        },
        "vessels": {"naval": 0, "official": 0},
    }
    result = estimate_positions(report)

    assert result["source"] == "zones"
    assert len(result["aircraft"]) == 0
    assert len(result["vessels"]) == 0
