.PHONY: scrape build serve clean

scrape:
	python -m scraper.main

build:
	mkdir -p site/maps
	cp data/assets/maps/* site/maps/ 2>/dev/null || true
	cp data/summary.csv site/summary.csv 2>/dev/null || true

serve: build
	cd site && python -m http.server 8000

clean:
	rm -rf site/maps site/summary.csv scraper_result.txt
