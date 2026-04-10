import json
from scraper.vision import parse_vision_response, validate_positions


def test_parse_vision_response_valid():
    raw = json.dumps({
        "aircraft": [
            {"lat": 24.5, "lon": 120.8, "label": "group"},
            {"lat": 23.2, "lon": 119.5, "label": "group"},
        ],
        "vessels": [
            {"lat": 24.0, "lon": 120.2, "type": "naval"},
        ],
    })
    result = parse_vision_response(raw)
    assert len(result["aircraft"]) == 2
    assert len(result["vessels"]) == 1


def test_parse_vision_response_with_markdown_fences():
    raw = '```json\n{"aircraft": [{"lat": 24.5, "lon": 120.8, "label": "group"}], "vessels": []}\n```'
    result = parse_vision_response(raw)
    assert len(result["aircraft"]) == 1


def test_parse_vision_response_invalid():
    result = parse_vision_response("This is not JSON at all")
    assert result is None


def test_validate_positions_filters_out_of_bounds():
    positions = {
        "aircraft": [
            {"lat": 24.5, "lon": 120.8, "label": "ok"},
            {"lat": 50.0, "lon": 120.0, "label": "out"},
        ],
        "vessels": [
            {"lat": 24.0, "lon": 200.0, "type": "naval"},
        ],
    }
    result = validate_positions(positions)
    assert len(result["aircraft"]) == 1
    assert result["aircraft"][0]["label"] == "ok"
    assert len(result["vessels"]) == 0


def test_validate_positions_returns_none_when_all_filtered():
    positions = {
        "aircraft": [{"lat": 50.0, "lon": 120.0, "label": "out"}],
        "vessels": [],
    }
    result = validate_positions(positions)
    assert result is None


def test_parse_marker_response_valid():
    raw = json.dumps({
        "markers": [
            {"id": 1, "type": "aircraft", "subtype": "fighter", "count": 5, "region": "north", "px": 480, "py": 350},
            {"id": 2, "type": "aircraft", "subtype": "support", "count": 2, "region": "southwest", "px": 200, "py": 650},
        ]
    })
    from scraper.vision import parse_marker_response
    result = parse_marker_response(raw)
    assert result is not None
    assert len(result["markers"]) == 2
    assert result["markers"][0]["type"] == "aircraft"
    assert result["markers"][0]["px"] == 480


def test_parse_marker_response_missing_markers_key():
    from scraper.vision import parse_marker_response
    result = parse_marker_response('{"data": []}')
    assert result is None


def test_parse_marker_response_with_fences():
    raw = '```json\n{"markers": [{"id": 1, "type": "aircraft", "subtype": "fighter", "count": 5, "region": "north", "px": 480, "py": 350}]}\n```'
    from scraper.vision import parse_marker_response
    result = parse_marker_response(raw)
    assert result is not None
    assert len(result["markers"]) == 1
