(async function () {
    // Fetch CSV
    const csvResp = await fetch("summary.csv");
    const csvText = await csvResp.text();
    const rows = parseCSV(csvText);

    if (rows.length === 0) {
        document.getElementById("last-updated").textContent = "No data available";
        return;
    }

    let selectedIndex = rows.length - 1;
    const jsonCache = {};

    // Timeline slider
    const slider = document.getElementById("timeline-slider");
    slider.min = 0;
    slider.max = rows.length - 1;
    slider.value = selectedIndex;

    // Detect mobile
    const isMobile = window.innerWidth <= 600;

    // --- Leaflet Map ---
    const map = L.map("geo-map", {
        center: [24, 121],
        zoom: isMobile ? 6 : 7,
        zoomControl: !isMobile,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 12,
        minZoom: 5,
    }).addTo(map);

    // Median line (Davis Line — Taiwan MND, 2004)
    L.polyline(
        [
            [26.5, 121.383],
            [24.833, 119.983],
            [23.283, 117.85],
        ],
        { color: "#999", weight: 1.5, dashArray: "6 4", interactive: false }
    ).addTo(map);

    // Marker layers
    const aircraftLayer = L.layerGroup().addTo(map);
    const navalLayer = L.layerGroup().addTo(map);
    const officialLayer = L.layerGroup().addTo(map);

    // --- ECharts Trend Chart ---
    const trendChart = echarts.init(document.getElementById("trend-chart"));
    const trendOption = {
        tooltip: { trigger: "axis" },
        legend: { data: ["Aircraft", "Naval Vessels"], top: 0, textStyle: { fontSize: isMobile ? 10 : 12 } },
        grid: { left: isMobile ? 35 : 50, right: isMobile ? 35 : 50, bottom: isMobile ? 60 : 50, top: 30 },
        xAxis: {
            type: "category",
            data: rows.map((r) => r.date),
            axisLabel: { rotate: 45, fontSize: isMobile ? 8 : 10 },
        },
        yAxis: [
            { type: "value", name: "Aircraft", position: "left", nameTextStyle: { fontSize: isMobile ? 9 : 12 } },
            { type: "value", name: "Vessels", position: "right", nameTextStyle: { fontSize: isMobile ? 9 : 12 } },
        ],
        series: [
            {
                name: "Aircraft",
                type: "line",
                data: rows.map((r) => r.aircraft_total),
                yAxisIndex: 0,
                smooth: true,
                symbolSize: 6,
            },
            {
                name: "Naval Vessels",
                type: "line",
                data: rows.map((r) => r.vessels_naval),
                yAxisIndex: 1,
                smooth: true,
                symbolSize: 6,
            },
        ],
    };
    trendChart.setOption(trendOption);

    // Fetch daily JSON (with cache)
    async function fetchDailyJSON(date) {
        if (jsonCache[date]) return jsonCache[date];
        try {
            const resp = await fetch("daily/" + date + ".json");
            if (!resp.ok) return null;
            const data = await resp.json();
            jsonCache[date] = data;
            return data;
        } catch (e) {
            return null;
        }
    }

    // Update map markers from positions data
    function updateMapMarkers(positions) {
        const badge = document.getElementById("position-badge");
        aircraftLayer.clearLayers();
        navalLayer.clearLayers();
        officialLayer.clearLayers();

        if (!positions) {
            badge.textContent = "No position data available";
            return;
        }

        var markerSize = isMobile ? 8 : 6;

        (positions.aircraft || []).forEach(function (p) {
            L.circleMarker([p.lat, p.lon], {
                radius: markerSize,
                color: "#c0392b",
                fillColor: "#e74c3c",
                fillOpacity: 0.85,
                weight: 1.5,
            })
                .bindTooltip("Aircraft: " + (p.label || "group"))
                .addTo(aircraftLayer);
        });

        (positions.vessels || [])
            .filter(function (v) { return v.type === "naval"; })
            .forEach(function (p) {
                L.circleMarker([p.lat, p.lon], {
                    radius: markerSize,
                    color: "#2471a3",
                    fillColor: "#3498db",
                    fillOpacity: 0.85,
                    weight: 1.5,
                })
                    .bindTooltip("Naval Vessel")
                    .addTo(navalLayer);
            });

        (positions.vessels || [])
            .filter(function (v) { return v.type === "official"; })
            .forEach(function (p) {
                L.circleMarker([p.lat, p.lon], {
                    radius: markerSize - 1,
                    color: "#5dade2",
                    fillColor: "#85c1e9",
                    fillOpacity: 0.85,
                    weight: 1.5,
                })
                    .bindTooltip("Official Vessel")
                    .addTo(officialLayer);
            });

        if (positions.source === "vision") {
            badge.textContent = "Positions: AI-extracted";
        } else if (positions.source === "zones") {
            badge.textContent = "Positions: Estimated";
        } else {
            badge.textContent = "";
        }
    }

    // Select date — update everything
    async function selectDate(index) {
        selectedIndex = Math.max(0, Math.min(index, rows.length - 1));
        const row = rows[selectedIndex];

        // Stats
        document.getElementById("stat-aircraft").textContent = row.aircraft_total;
        document.getElementById("stat-median").textContent = row.crossed_median;
        document.getElementById("stat-adiz").textContent = row.entered_adiz;
        document.getElementById("stat-naval").textContent = row.vessels_naval;
        document.getElementById("stat-official").textContent = row.vessels_official;

        // Timeline
        slider.value = selectedIndex;
        document.getElementById("timeline-date").textContent = row.date;

        // Trend chart tooltip
        trendChart.dispatchAction({
            type: "showTip",
            seriesIndex: 0,
            dataIndex: selectedIndex,
        });

        // Geo map — fetch daily JSON
        const daily = await fetchDailyJSON(row.date);
        updateMapMarkers(daily ? daily.positions : null);
    }

    // Playback
    const playBtn = document.getElementById("play-btn");
    let playInterval = null;

    function startPlayback() {
        if (selectedIndex >= rows.length - 1) selectedIndex = -1;
        playBtn.textContent = "\u275A\u275A";
        playBtn.classList.add("playing");
        playInterval = setInterval(() => {
            if (selectedIndex >= rows.length - 1) {
                stopPlayback();
                return;
            }
            selectDate(selectedIndex + 1);
        }, 1000);
    }

    function stopPlayback() {
        clearInterval(playInterval);
        playInterval = null;
        playBtn.textContent = "\u25B6";
        playBtn.classList.remove("playing");
    }

    playBtn.addEventListener("click", () => {
        if (playInterval) {
            stopPlayback();
        } else {
            startPlayback();
        }
    });

    // Events
    slider.addEventListener("input", (e) => {
        if (playInterval) stopPlayback();
        selectDate(parseInt(e.target.value));
    });

    trendChart.on("click", (params) => {
        if (playInterval) stopPlayback();
        selectDate(params.dataIndex);
    });

    // Last updated
    const latest = rows[rows.length - 1];
    document.getElementById("last-updated").textContent = "Last updated: " + latest.date;

    // Responsive
    window.addEventListener("resize", () => {
        trendChart.resize();
        map.invalidateSize();
    });

    // Initial render
    selectDate(selectedIndex);
})();

function parseCSV(text) {
    const lines = text.trim().split("\n");
    if (lines.length < 2) return [];

    const headers = lines[0].split(",");
    return lines.slice(1).map((line) => {
        const values = line.split(",");
        const obj = {};
        headers.forEach((h, i) => {
            const v = values[i];
            obj[h] = isNaN(v) || v === "" ? v : parseInt(v);
        });
        return obj;
    });
}
