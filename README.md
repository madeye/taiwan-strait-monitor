# Taiwan Strait Monitor

An automated dashboard tracking PLA military activity around Taiwan, powered by daily scraping of Taiwan's Ministry of National Defense (MND) reports.

**Live Dashboard:** [madeye.github.io/taiwan-strait-monitor](https://madeye.github.io/taiwan-strait-monitor/)

## Features

- Daily automated scraping of MND PLA activity reports (aircraft sorties, naval vessels)
- Interactive ECharts geo map with aircraft and vessel position markers
- Trend chart showing historical activity over time
- Timeline slider with playback for browsing historical data
- Vision AI position extraction via NVIDIA NIM API (with zone-based fallback)
- Responsive design for mobile and desktop
- Fully automated via GitHub Actions — scrapes daily, commits data, deploys to GitHub Pages

## Data Source

All data is sourced from the [Taiwan Ministry of National Defense](https://www.mnd.gov.tw/PublishTable.aspx?Types=%E5%8D%B3%E6%99%82%E8%BB%8D%E4%BA%8B%E5%8B%95%E6%85%8B&title=%E5%9C%8B%E9%98%B2%E6%B6%88%E6%81%AF) daily PLA activity reports.

## Local Development

```bash
pip install -r requirements.txt
make scrape   # fetch latest MND data
make serve    # preview dashboard at http://localhost:8000
```

## Project Structure

```
├── scraper/          # Python scraper (fetcher, parser, storage, vision, zones)
├── site/             # Static dashboard (HTML, CSS, JS, GeoJSON)
├── data/             # Scraped data (daily JSON, summary CSV, map images)
├── tests/            # Unit tests
├── .github/workflows # GitHub Actions CI/CD
└── Makefile          # Local dev commands
```

## License

[MIT](LICENSE)

## Disclaimer / 免责声明

This project is for informational and research purposes only. It does not represent any political stance or position.

All data displayed is sourced exclusively from publicly available reports published by the Republic of China (Taiwan) Ministry of National Defense. The developers make no guarantees regarding the accuracy, completeness, or timeliness of the data.

Position markers on the map are approximate — either AI-estimated from official route map images or derived from zone-based fallback. They do not represent precise military positions.

This project is not affiliated with, endorsed by, or associated with any government or military organization.

---

本项目仅供信息参考和研究用途，不代表任何政治立场或观点。

所有展示的数据均来源于中华民国（台湾）国防部公开发布的报告。开发者不对数据的准确性、完整性或时效性做任何保证。

地图上的位置标记为近似值——通过 AI 从官方航迹示意图中提取，或基于区域估算生成，不代表精确的军事位置。

本项目与任何政府或军事组织无关，未获其认可或授权。
