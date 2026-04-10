import pathlib
import pytest

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample_map.jpg"


def test_calibrate_grid_returns_transform():
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(str(FIXTURE_PATH))
    assert transform is not None


def test_calibrate_grid_correct_center():
    """The center pixel of the map should be in the Taiwan Strait area (~120E, ~25N).

    Prior analysis shows pixel (360, 520) maps to approximately (120E, 25N) —
    the visual center of the 720x1040 image is in the northern Taiwan Strait.
    """
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(str(FIXTURE_PATH))
    # Image is 720x1040; center pixel is (360, 520)
    lat, lon = transform.to_latlon(360, 520)
    assert 119.5 < lon < 120.5, f"Center lon {lon} not near 120E"
    assert 23.0 < lat < 26.0, f"Center lat {lat} not in expected range for Taiwan Strait"


def test_calibrate_grid_known_point_kinmen():
    """Kinmen is at approximately (118.3E, 24.4N), pixel ~(230, 620)."""
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(str(FIXTURE_PATH))
    lat, lon = transform.to_latlon(230, 620)
    assert 117.5 < lon < 119.0, f"Kinmen lon {lon} not near 118.3E"
    assert 23.5 < lat < 25.0, f"Kinmen lat {lat} not near 24.4N"


def test_calibrate_grid_longitude_increases_rightward():
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(str(FIXTURE_PATH))
    _, lon_left = transform.to_latlon(200, 500)
    _, lon_right = transform.to_latlon(500, 500)
    assert lon_right > lon_left


def test_calibrate_grid_latitude_increases_upward():
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(str(FIXTURE_PATH))
    lat_top, _ = transform.to_latlon(360, 200)
    lat_bottom, _ = transform.to_latlon(360, 800)
    assert lat_top > lat_bottom


def test_calibrate_grid_invalid_image():
    from scraper.cv import calibrate_grid

    result = calibrate_grid("/nonexistent/path.jpg")
    assert result is not None  # Should return hardcoded fallback, not None


def test_fallback_calibration():
    """Fallback should still give reasonable coordinates."""
    from scraper.cv import fallback_calibration

    transform = fallback_calibration()
    lat, lon = transform.to_latlon(368, 636)
    # Should be near 120E, 24N (center of strait)
    assert 119.0 < lon < 121.0
    assert 23.0 < lat < 25.0


def test_calibrate_grid_degree_spacing():
    """Verify that 1 degree longitude ~ 82px and 1 degree latitude ~ 89px."""
    from scraper.cv import calibrate_grid

    transform = calibrate_grid(str(FIXTURE_PATH))

    # 1 degree longitude: check pixel spacing
    _, lon_at_300 = transform.to_latlon(300, 500)
    _, lon_at_382 = transform.to_latlon(382, 500)
    lon_diff = lon_at_382 - lon_at_300
    assert 0.8 < lon_diff < 1.2, f"82px should be ~1 deg lon, got {lon_diff:.2f}"

    # 1 degree latitude: check pixel spacing
    lat_at_500, _ = transform.to_latlon(360, 500)
    lat_at_589, _ = transform.to_latlon(360, 589)
    lat_diff = lat_at_500 - lat_at_589  # lat decreases as y increases
    assert 0.8 < lat_diff < 1.2, f"89px should be ~1 deg lat, got {lat_diff:.2f}"


def test_calibrate_grid_multiple_images():
    """Test that calibration works on different date images if available."""
    import pathlib
    from scraper.cv import calibrate_grid

    maps_dir = pathlib.Path("data/assets/maps")
    if not maps_dir.exists():
        pytest.skip("No maps directory")

    images = sorted(maps_dir.glob("*.jpg"))[-3:]  # last 3
    for img_path in images:
        transform = calibrate_grid(str(img_path))
        assert transform is not None
        # Center should always be approximately 120E, 24N
        lat, lon = transform.to_latlon(360, 520)
        assert 119.0 < lon < 121.0, f"{img_path.name}: center lon={lon}"
        assert 23.0 < lat < 26.0, f"{img_path.name}: center lat={lat}"
