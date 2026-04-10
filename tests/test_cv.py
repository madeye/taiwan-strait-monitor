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
