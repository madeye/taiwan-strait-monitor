import warnings

import requests
from urllib.parse import urljoin

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://www.mnd.gov.tw"
LIST_URL = f"{BASE_URL}/PublishTable.aspx?Types=%E5%8D%B3%E6%99%82%E8%BB%8D%E4%BA%8B%E5%8B%95%E6%85%8B&title=%E5%9C%8B%E9%98%B2%E6%B6%88%E6%81%AF"
USER_AGENT = "taiwan-strait-monitor/1.0 (+https://github.com/user/taiwan-strait-monitor)"
TIMEOUT = 30


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    s.verify = False  # MND cert missing Subject Key Identifier; Python 3.13 rejects it
    a = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", a)
    return s


def fetch_list_page() -> str:
    """Fetch the MND PLA activities list page HTML."""
    resp = _session().get(LIST_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def fetch_detail_page(report_id: str) -> str:
    """Fetch a single MND report detail page HTML."""
    url = f"{BASE_URL}/news/plaact/{report_id}"
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def fetch_image(image_url: str) -> bytes:
    """Download a map image and return raw bytes."""
    url = image_url if image_url.startswith("http") else urljoin(BASE_URL, image_url)
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content
