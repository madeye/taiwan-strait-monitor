import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Expected grid spacing in pixels (measured from multiple MND map samples)
EXPECTED_LON_SPACING = 82  # px per degree longitude
EXPECTED_LAT_SPACING = 89  # px per degree latitude
SPACING_TOLERANCE = 10  # px tolerance for grid spacing matching

# Hardcoded fallback calibration (measured from 2026-03-31 and 2026-04-10 maps)
# lon = scale_x * px + offset_x, lat = scale_y * py + offset_y
FALLBACK_SCALE_X = 0.01224
FALLBACK_OFFSET_X = 115.49
FALLBACK_SCALE_Y = -0.01126
FALLBACK_OFFSET_Y = 31.15


@dataclass
class AffineTransform:
    """Linear transform from pixel (x, y) to (lat, lon)."""

    scale_x: float  # lon per pixel
    offset_x: float  # lon offset
    scale_y: float  # lat per pixel (negative: y increases downward)
    offset_y: float  # lat offset

    def to_latlon(self, px: int, py: int) -> tuple[float, float]:
        lon = self.scale_x * px + self.offset_x
        lat = self.scale_y * py + self.offset_y
        return (lat, lon)


def fallback_calibration() -> AffineTransform:
    """Return a hardcoded calibration for standard MND 720x1040 maps."""
    return AffineTransform(
        scale_x=FALLBACK_SCALE_X,
        offset_x=FALLBACK_OFFSET_X,
        scale_y=FALLBACK_SCALE_Y,
        offset_y=FALLBACK_OFFSET_Y,
    )


def _detect_lines(gray: np.ndarray) -> tuple[list[int], list[int]]:
    """Detect vertical and horizontal line positions from a grayscale image.

    Returns (vertical_x_positions, horizontal_y_positions) as clustered lists.
    """
    edges = cv2.Canny(gray, 50, 150)
    raw_lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=400, maxLineGap=10)

    if raw_lines is None:
        return [], []

    v_positions = []
    h_positions = []

    for line in raw_lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        if 85 < angle < 95 and length > 400:
            v_positions.append(int(round((x1 + x2) / 2)))
        elif (angle < 5 or angle > 175) and length > 300:
            h_positions.append(int(round((y1 + y2) / 2)))

    return _cluster(v_positions), _cluster(h_positions)


def _cluster(positions: list[int], gap: int = 5) -> list[int]:
    """Cluster nearby positions and return their means."""
    if not positions:
        return []
    positions.sort()
    clusters: list[list[int]] = [[positions[0]]]
    for p in positions[1:]:
        if p - clusters[-1][-1] <= gap:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [int(np.mean(c)) for c in clusters]


def _find_grid_lines(positions: list[int], expected_spacing: int) -> list[int]:
    """Find the subset of positions that form a regular grid with the expected spacing.

    Returns the positions that best match a regular grid.
    """
    if len(positions) < 2:
        return positions

    best_grid = []

    # Try each pair of adjacent positions as the seed
    for i in range(len(positions) - 1):
        spacing = positions[i + 1] - positions[i]
        if abs(spacing - expected_spacing) > SPACING_TOLERANCE:
            continue

        # Extend grid in both directions from this pair
        grid = [positions[i], positions[i + 1]]
        actual_spacing = spacing

        # Extend left
        expected_prev = positions[i] - actual_spacing
        for j in range(i - 1, -1, -1):
            if abs(positions[j] - expected_prev) <= SPACING_TOLERANCE:
                grid.insert(0, positions[j])
                expected_prev = positions[j] - actual_spacing

        # Extend right
        expected_next = positions[i + 1] + actual_spacing
        for j in range(i + 2, len(positions)):
            if abs(positions[j] - expected_next) <= SPACING_TOLERANCE:
                grid.append(positions[j])
                expected_next = positions[j] + actual_spacing

        if len(grid) > len(best_grid):
            best_grid = grid

    return best_grid


def _assign_degrees(
    grid_positions: list[int],
    expected_spacing: int,
    center_degree: float,
    reverse: bool = False,
    anchor_idx: int | None = None,
) -> list[tuple[int, float]]:
    """Assign degree values to grid positions.

    By default, the position closest to the median gets center_degree.
    If anchor_idx is specified, that index gets center_degree instead.
    Each step of expected_spacing corresponds to 1 degree.

    Set reverse=True when degree decreases as position increases (e.g. latitude,
    where pixel y increases downward but latitude increases upward).
    """
    if not grid_positions:
        return []

    if anchor_idx is None:
        median_pos = int(np.median(grid_positions))
        ref_idx = min(range(len(grid_positions)), key=lambda i: abs(grid_positions[i] - median_pos))
    else:
        ref_idx = anchor_idx

    result = []
    for i, pos in enumerate(grid_positions):
        step = i - ref_idx
        degree = center_degree + (-step if reverse else step)
        result.append((pos, degree))

    return result


def calibrate_grid(image_path: str) -> AffineTransform:
    """Detect coordinate grid in an MND map image and return a pixel-to-latlon transform.

    Always returns a transform (uses hardcoded fallback if detection fails).
    """
    fallback = fallback_calibration()

    img = cv2.imread(image_path)
    if img is None:
        logger.warning(f"Could not read image: {image_path}, using fallback calibration")
        return fallback

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    v_positions, h_positions = _detect_lines(gray)

    # Find longitude grid lines (vertical, ~82px spacing)
    lon_grid = _find_grid_lines(v_positions, EXPECTED_LON_SPACING)
    # Find latitude grid lines (horizontal, ~89px spacing)
    lat_grid = _find_grid_lines(h_positions, EXPECTED_LAT_SPACING)

    if len(lon_grid) < 2 and len(lat_grid) < 2:
        logger.info("Grid detection failed, using fallback calibration")
        return fallback

    # Assign degrees: center of lon grid is 120E (the map is centered on the Taiwan Strait).
    # For latitude, use the fallback scale to estimate the degree at the first detected line,
    # then assign integer degrees downward (lat decreases as pixel y increases).
    lon_points = _assign_degrees(lon_grid, EXPECTED_LON_SPACING, 120.0)
    if lat_grid:
        first_lat_estimate = fallback.scale_y * lat_grid[0] + fallback.offset_y
        first_lat_degree = float(round(first_lat_estimate))
        lat_points = _assign_degrees(
            lat_grid, EXPECTED_LAT_SPACING, first_lat_degree, reverse=True, anchor_idx=0
        )
    else:
        lat_points = []

    # Fit linear regression for each axis
    if len(lon_points) >= 2:
        x_px = [p[0] for p in lon_points]
        x_deg = [p[1] for p in lon_points]
        lon_fit = np.polyfit(x_px, x_deg, 1)
        scale_x, offset_x = float(lon_fit[0]), float(lon_fit[1])
    else:
        scale_x, offset_x = fallback.scale_x, fallback.offset_x

    if len(lat_points) >= 2:
        y_px = [p[0] for p in lat_points]
        y_deg = [p[1] for p in lat_points]
        lat_fit = np.polyfit(y_px, y_deg, 1)
        scale_y, offset_y = float(lat_fit[0]), float(lat_fit[1])
    else:
        scale_y, offset_y = fallback.scale_y, fallback.offset_y

    logger.info(
        f"Grid calibration: lon={scale_x:.6f}*x+{offset_x:.2f}, "
        f"lat={scale_y:.6f}*y+{offset_y:.2f} "
        f"({len(lon_points)} lon points, {len(lat_points)} lat points)"
    )

    return AffineTransform(scale_x=scale_x, offset_x=offset_x, scale_y=scale_y, offset_y=offset_y)
