(async function () {
    // Parallel fetch: CSV + GeoJSON
    const [csvResp, geoResp] = await Promise.all([
        fetch("summary.csv"),
        fetch("geo/taiwan-strait.json"),
    ]);
    const csvText = await csvResp.text();
    const geoData = await geoResp.json();
    const rows = parseCSV(csvText);

    if (rows.length === 0) {
        document.getElementById("last-updated").textContent = "No data available";
        return;
    }

    // Register map for ECharts geo
    echarts.registerMap("taiwan-strait", geoData);

    let selectedIndex = rows.length - 1;
    const jsonCache = {};

    // Timeline slider
    const slider = document.getElementById("timeline-slider");
    slider.min = 0;
    slider.max = rows.length - 1;
    slider.value = selectedIndex;

    // Detect mobile
    const isMobile = window.innerWidth <= 600;

    // Geo map
    const geoChart = echarts.init(document.getElementById("geo-map"));
    const geoOption = {
        geo: {
            map: "taiwan-strait",
            roam: true,
            center: [121, 24],
            zoom: isMobile ? 4 : 5,
            itemStyle: {
                areaColor: "#e8e8e8",
                borderColor: "#aaa",
            },
            emphasis: {
                itemStyle: { areaColor: "#ddd" },
            },
        },
        tooltip: { trigger: "item" },
        series: [
            {
                name: "Median Line",
                type: "lines",
                coordinateSystem: "geo",
                polyline: true,
                silent: true,
                lineStyle: {
                    color: "#999",
                    width: 1.5,
                    type: "dashed",
                },
                data: [
                    {
                        // Official Davis Line coordinates (Taiwan MND, 2004)
                        coords: [
                            [121.383, 26.5],
                            [119.983, 24.833],
                            [117.85, 23.283],
                        ],
                    },
                ],
                tooltip: { show: false },
            },
            {
                name: "Aircraft",
                type: "scatter",
                coordinateSystem: "geo",
                data: [],
                symbol: "circle",
                symbolSize: isMobile ? 16 : 12,
                itemStyle: { color: "#e74c3c" },
                tooltip: {
                    formatter: function (params) {
                        return "Aircraft: " + (params.data.label || "group");
                    },
                },
            },
            {
                name: "Naval Vessels",
                type: "scatter",
                coordinateSystem: "geo",
                data: [],
                symbol: "diamond",
                symbolSize: isMobile ? 16 : 12,
                itemStyle: { color: "#3498db" },
                tooltip: {
                    formatter: function (params) {
                        return "Naval Vessel";
                    },
                },
            },
            {
                name: "Official Vessels",
                type: "scatter",
                coordinateSystem: "geo",
                data: [],
                symbol: "diamond",
                symbolSize: isMobile ? 14 : 10,
                itemStyle: { color: "#85c1e9" },
                tooltip: {
                    formatter: function (params) {
                        return "Official Vessel";
                    },
                },
            },
        ],
    };
    geoChart.setOption(geoOption);

    // Trend chart (light theme — no "dark" arg)
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

        if (!positions) {
            geoChart.setOption({
                series: [
                    { name: "Aircraft", data: [] },
                    { name: "Naval Vessels", data: [] },
                    { name: "Official Vessels", data: [] },
                ],
            });
            badge.textContent = "No position data available";
            return;
        }

        const aircraftData = (positions.aircraft || []).map((p) => ({
            value: [p.lon, p.lat],
            label: p.label,
        }));

        const navalData = (positions.vessels || [])
            .filter((v) => v.type === "naval")
            .map((p) => ({ value: [p.lon, p.lat] }));

        const officialData = (positions.vessels || [])
            .filter((v) => v.type === "official")
            .map((p) => ({ value: [p.lon, p.lat] }));

        geoChart.setOption({
            series: [
                { name: "Aircraft", data: aircraftData },
                { name: "Naval Vessels", data: navalData },
                { name: "Official Vessels", data: officialData },
            ],
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
        if (selectedIndex >= rows.length - 1) selectedIndex = -1; // restart from beginning
        playBtn.textContent = "\u275A\u275A"; // pause icon
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
        playBtn.textContent = "\u25B6"; // play icon
        playBtn.classList.remove("playing");
    }

    playBtn.addEventListener("click", () => {
        if (playInterval) {
            stopPlayback();
        } else {
            startPlayback();
        }
    });

    // Events — slider works with both mouse drag and touch
    slider.addEventListener("input", (e) => {
        if (playInterval) stopPlayback();
        selectDate(parseInt(e.target.value));
    });

    // Chart click works on both desktop and mobile (ECharts handles touch internally)
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
        geoChart.resize();
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
