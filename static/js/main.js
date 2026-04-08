/**
 * Monitor-AI — live dashboard logic
 * Fetches /api/stats every second, updates DOM and Chart.js charts.
 * History buffer: 60 data points (= 60 seconds).
 */

const HISTORY = 60;        // number of seconds to show on charts
const INTERVAL = 1000;     // milliseconds between updates
const WARN_THRESHOLD = 80; // percent — show warning color above this

// ── History buffers ─────────────────────────────────────────────
const cpuHistory     = Array(HISTORY).fill(0);
const ramHistory     = Array(HISTORY).fill(0);
const netDownHistory = Array(HISTORY).fill(0);
const netUpHistory   = Array(HISTORY).fill(0);

// ── Chart factory ────────────────────────────────────────────────
function makeChart(canvasId, datasets) {
    /**
     * Create a minimal Chart.js line chart.
     * canvasId: string — id of <canvas> element
     * datasets: array of { label, data, color } objects
     */
    const ctx = document.getElementById(canvasId).getContext("2d");
    return new Chart(ctx, {
        type: "line",
        data: {
            labels: Array(HISTORY).fill(""),
            datasets: datasets.map(d => ({
                label: d.label,
                data: d.data,
                borderColor: d.color,
                backgroundColor: d.color + "1a",  // 10% opacity fill
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.3,
                fill: true,
            })),
        },
        options: {
            responsive: true,
            animation: false,
            scales: {
                x: { display: false },
                y: {
                    min: 0,
                    max: 100,
                    display: false,
                    grid: { display: false },
                },
            },
            plugins: { legend: { display: false } },
        },
    });
}

// ── Initialise charts ────────────────────────────────────────────
const cpuChart = makeChart("chart-cpu", [
    { label: "CPU %", data: cpuHistory, color: "#00ff88" },
]);

const ramChart = makeChart("chart-ram", [
    { label: "RAM %", data: ramHistory, color: "#00ff88" },
]);

const netChart = makeChart("chart-net", [
    { label: "Down Mbps", data: netDownHistory, color: "#00ff88" },
    { label: "Up Mbps",   data: netUpHistory,   color: "#ff6b6b" },
]);

// Network chart auto-scales — remove fixed max
netChart.options.scales.y.max = undefined;
netChart.options.scales.y.suggestedMax = 10;
netChart.update();

// ── DOM helpers ──────────────────────────────────────────────────
function setText(id, value) {
    /** Update text content of element by id. */
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setWarning(cardId, isWarning) {
    /** Add or remove the warning CSS class from a card. */
    const card = document.getElementById(cardId);
    if (card) card.classList.toggle("warning", isWarning);
}

function pushHistory(buffer, value) {
    /** Add new value to circular buffer, drop oldest. */
    buffer.push(value);
    buffer.shift();
}

// ── Update functions ─────────────────────────────────────────────
function updateCpu(data) {
    /** Update CPU total, per-core badges, and chart. */
    const pct = data.cpu_total;
    setText("cpu-total", pct.toFixed(1) + "%");
    setWarning("card-cpu", pct > WARN_THRESHOLD);

    // Rebuild cores grid
    const grid = document.getElementById("cpu-cores");
    grid.innerHTML = data.cpu_cores
        .map((c, i) =>
            `<span class="core-badge${c > WARN_THRESHOLD ? " hot" : ""}">C${i}: ${c.toFixed(0)}%</span>`
        )
        .join("");

    pushHistory(cpuHistory, pct);
    cpuChart.update();
}

function updateRam(data) {
    /** Update RAM percent, used/total text, and chart. */
    const ram = data.ram;
    setText("ram-percent", ram.percent.toFixed(1) + "%");
    setText("ram-detail", `${ram.used_mb} MB / ${ram.total_mb} MB`);
    setWarning("card-ram", ram.percent > WARN_THRESHOLD);

    pushHistory(ramHistory, ram.percent);
    ramChart.update();
}

function updateDisk(data) {
    /** Update disk percent, used/total text, and progress bar. */
    const disk = data.disk;
    setText("disk-percent", disk.percent.toFixed(1) + "%");
    setText("disk-detail", `${disk.used_gb} GB / ${disk.total_gb} GB`);

    const bar = document.getElementById("disk-bar");
    if (bar) {
        bar.style.width = disk.percent + "%";
        bar.classList.toggle("warning", disk.percent > WARN_THRESHOLD);
    }
}

function updateNetwork(data) {
    /** Update network download/upload speed and chart. */
    const net = data.network;
    setText("net-down", net.download_mbps.toFixed(2) + " Mbps");
    setText("net-up",   net.upload_mbps.toFixed(2) + " Mbps");

    pushHistory(netDownHistory, net.download_mbps);
    pushHistory(netUpHistory,   net.upload_mbps);

    // Auto-scale y-axis to current max speed
    const maxSpeed = Math.max(...netDownHistory, ...netUpHistory, 1);
    netChart.options.scales.y.max = Math.ceil(maxSpeed * 1.2);
    netChart.update();
}

// ── Main fetch loop ──────────────────────────────────────────────
async function fetchAndUpdate() {
    /**
     * Fetch /api/stats, update all widgets.
     * On error: flash status dot red.
     */
    const dot = document.getElementById("status");
    try {
        const response = await fetch("/api/stats");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        updateCpu(data);
        updateRam(data);
        updateDisk(data);
        updateNetwork(data);

        dot.classList.add("active");
    } catch (err) {
        console.error("Failed to fetch stats:", err);
        dot.classList.remove("active");
    }
}

// Start immediately, then repeat every second
fetchAndUpdate();
setInterval(fetchAndUpdate, INTERVAL);
