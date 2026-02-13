(function () {

  // =========================================
  // Global Dashboard State (Hydrated Later)
  // =========================================
  let data = window.__DASHBOARD__ || {};
  const $ = (id) => document.getElementById(id);

  // =========================================
  // SAFE FETCH FROM /farmer/dashboard/data
  // =========================================
  async function fetchDashboardData(till) {
    const params = till ? `?till=${encodeURIComponent(till)}` : "";
    const res = await fetch(`/farmer/dashboard/data${params}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });

    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const txt = await res.text();
      console.error("Dashboard returned HTML:", txt.slice(0, 200));
      throw new Error("Dashboard API returned non-JSON response.");
    }

    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j?.error || `Dashboard API failed (${res.status})`);
    }

    return res.json();
  }

  // =========================================
  // Helpers
  // =========================================
  function safeNum(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : 0;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // =========================================
  // Charts
  // =========================================
  let soilChart = null;
  let orderChart = null;
  let weatherChart = null;
  let warehousePie = null;
  let mfgPie = null;

  // ---------- SOIL ----------
  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const labels = data.soil?.labels || [];
    const points = data.soil?.soil_temp || [];

    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, "rgba(124, 58, 237, 0.55)");
    gradient.addColorStop(0.6, "rgba(124, 58, 237, 0.20)");
    gradient.addColorStop(1, "rgba(124, 58, 237, 0.02)");

    if (soilChart) soilChart.destroy();

    soilChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Soil Temperature",
          data: points,
          tension: 0.35,
          fill: true,
          borderColor: "#7C3AED",
          backgroundColor: gradient,
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: "#7C3AED",
          pointBorderColor: "#fff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }},
          y: { grid: { display: false }, ticks: { display: false }}
        }
      }
    });
  }

  // ---------- ORDERS ----------
  function initOrderDonut() {
    const canvas = $("orderDonutChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const o = data.orders || {};
    const values = [
      safeNum(o.requested),
      safeNum(o.in_transit),
      safeNum(o.completed),
      safeNum(o.payment_received)
    ];

    if (orderChart) orderChart.destroy();

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In Transit", "Completed", "Paid"],
        datasets: [{
          data: values,
          borderWidth: 0,
          backgroundColor: ["#fde68a", "#60a5fa", "#86efac", "#c4b5fd"]
        }]
      },
      options: {
        cutout: "70%",
        plugins: { legend: { display: false }}
      }
    });
  }

  // ---------- WAREHOUSE ----------
  function initWarehousePie() {
    const canvas = $("warehousePieChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const w = data.warehouse_summary || {};
    const values = [
      safeNum(w.requested),
      safeNum(w.stored),
      safeNum(w.pending_payment)
    ];

    if (warehousePie) warehousePie.destroy();

    warehousePie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Stored", "Pending"],
        datasets: [{
          data: values,
          borderWidth: 0,
          backgroundColor: ["#fde68a", "#6366f1", "#60a5fa"]
        }]
      },
      options: { plugins: { legend: { display: false }}}
    });
  }

  // ---------- MANUFACTURER ----------
  function initManufacturerPie() {
    const canvas = $("mfgPieChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const m = data.manufacturer_summary || {};
    const values = [
      safeNum(m.requested),
      safeNum(m.processing),
      safeNum(m.pending_payment)
    ];

    if (mfgPie) mfgPie.destroy();

    mfgPie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Processing", "Pending"],
        datasets: [{
          data: values,
          borderWidth: 0,
          backgroundColor: ["#60a5fa", "#f59e0b", "#6366f1"]
        }]
      },
      options: { plugins: { legend: { display: false }}}
    });
  }

  // =========================================
  // WEATHER (Fix spacing + radius)
  // =========================================
  function ensureWeatherChart(labels, values) {
    const canvas = $("weatherBarChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (weatherChart) weatherChart.destroy();

    weatherChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: "rgba(99,102,241,0.2)",
          borderColor: "#6366F1",
          borderWidth: 2,
          borderRadius: 6,
          categoryPercentage: 0.98,
          barPercentage: 0.92,
          maxBarThickness: 26
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }},
        scales: {
          x: { grid: { display: false }, offset: false },
          y: { grid: { display: false }, ticks: { display: false }}
        }
      }
    });
  }

  // =========================================
  // BOOT SEQUENCE
  // =========================================
  document.addEventListener("DOMContentLoaded", async () => {

    try {
      const fresh = await fetchDashboardData();
      data = fresh;
      window.__DASHBOARD__ = fresh;
    } catch (e) {
      console.warn("Using pre-rendered dashboard JSON", e);
    }

    initSoilChart();
    initOrderDonut();
    initWarehousePie();
    initManufacturerPie();

    // Optional: If your backend provides weather data, pass here
    if (data.weather?.labels && data.weather?.values) {
      ensureWeatherChart(data.weather.labels, data.weather.values);
    }

  });

})();
