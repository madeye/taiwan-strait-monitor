(async function () {
    const resp = await fetch("summary.csv");
    const text = await resp.text();
    const rows = parseCSV(text);

    if (rows.length === 0) {
        document.getElementById("last-updated").textContent = "No data available";
        return;
    }

    let selectedIndex = rows.length - 1;

    const slider = document.getElementById("timeline-slider");
    slider.min = 0;
    slider.max = rows.length - 1;
    slider.value = selectedIndex;

    const chart = echarts.init(document.getElementById("trend-chart"), "dark");
    const chartOption = {
        backgroundColor: "transparent",
        tooltip: { trigger: "axis" },
        legend: { data: ["Aircraft", "Naval Vessels"], top: 0 },
        xAxis: {
            type: "category",
            data: rows.map((r) => r.date),
            axisLabel: { rotate: 45, fontSize: 10 },
        },
        yAxis: [
            { type: "value", name: "Aircraft", position: "left" },
            { type: "value", name: "Vessels", position: "right" },
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
    chart.setOption(chartOption);

    function selectDate(index) {
        selectedIndex = Math.max(0, Math.min(index, rows.length - 1));
        const row = rows[selectedIndex];

        document.getElementById("stat-aircraft").textContent = row.aircraft_total;
        document.getElementById("stat-median").textContent = row.crossed_median;
        document.getElementById("stat-adiz").textContent = row.entered_adiz;
        document.getElementById("stat-naval").textContent = row.vessels_naval;
        document.getElementById("stat-official").textContent = row.vessels_official;

        slider.value = selectedIndex;
        document.getElementById("timeline-date").textContent = row.date;

        document.getElementById("map-date").textContent = row.date;
        const mapImg = document.getElementById("map-image");
        if (row.map_image) {
            mapImg.src = row.map_image;
            mapImg.style.display = "";
        } else {
            mapImg.src = "";
            mapImg.style.display = "none";
        }

        chart.dispatchAction({
            type: "showTip",
            seriesIndex: 0,
            dataIndex: selectedIndex,
        });
    }

    slider.addEventListener("input", (e) => selectDate(parseInt(e.target.value)));
    chart.on("click", (params) => selectDate(params.dataIndex));

    const latest = rows[rows.length - 1];
    document.getElementById("last-updated").textContent = "Last updated: " + latest.date;

    window.addEventListener("resize", () => chart.resize());

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
