import re


def parse_roc_date_compact(date_str: str) -> str:
    """Parse compact ROC date like '115.03.19' to '2026-03-19'."""
    parts = date_str.strip().split(".")
    year = int(parts[0]) + 1911
    month = int(parts[1])
    day = int(parts[2])
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_roc_date_prose(text: str) -> str:
    """Parse prose ROC date like '中華民國115年3月18日' to '2026-03-18'."""
    match = re.search(r"(\d+)年(\d+)月(\d+)日", text)
    if not match:
        raise ValueError(f"Cannot parse ROC date from: {text}")
    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"
