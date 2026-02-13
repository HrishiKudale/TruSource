(function () {
  "use strict";

  const data = window.__DASHBOARD__ || {};
  const $ = (id) => document.getElementById(id);

  /* -----------------------------
     Small utilities
  ----------------------------- */
  function safeNum(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : 0;
  }

  function toDate(val) {
    if (!val) return null;
    if (val instanceof Date) return val;
    const d = new Date(val);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtDate(d) {
    if (!d) return "-";
    return d.toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  function withinTill(itemDate, selectedDate) {
    if (!selectedDate) return true;
    const d1 = toDate(itemDate);
    const d2 = toDate(selectedDate);
    if (!d1 || !d2) return true;
    d2.setHours(23, 59, 59, 999);
    return d1.getTime() <= d2.getTime();
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function cap(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  // Wait until element has size (fix Chart.js rendering when hidden)
  function raf2(cb) {
    requestAnimationFrame(() => requestAnimationFrame(cb));
  }

  function waitForVisible(el, timeoutMs = 2500) {
    return new Promise((resolve) => {
      if (!el) return resolve(false);
      const start = Date.now();
      const tick = () => {
        const style = getComputedStyle(el);
        const ok =
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          el.offsetParent !== null &&
          el.offsetWidth > 20 &&
          el.offsetHeight > 20;

        if (ok) return resolve(true);
        if (Date.now() - start > timeoutMs) return resolve(false);
        raf2(tick);
      };
      tick();
    });
  }

  // Nice chart animation
  function chartAnimStagger(delayBase = 40) {
    return {
      duration: 900,
      easing: "easeOutQuart",
      delay: (ctx) => {
        if (ctx.type === "data") return ctx.dataIndex * delayBase;
        return 0;
      },
    };
  }

  /* -----------------------------
     Chart loading animation helpers
  ----------------------------- */
  function addChartLoading(canvasId) {
    const c = $(canvasId);
    if (!c) return;
    c.classList.add("chart-loading");
    // ensure parent has positioning if needed
    const p = c.parentElement;
    if (p && getComputedStyle(p).position === "static") p.style.position = "relative";
  }

  function removeChartLoading(canvasId) {
    const c = $(canvasId);
    if (!c) return;
    c.classList.remove("chart-loading");
  }

  // Inject CSS once
  function injectChartLoadingCSS() {
    if (document.getElementById("chart-loading-css")) return;
    const style = document.createElement("style");
    style.id = "chart-loading-css";
    style.textContent = `
      canvas.chart-loading { opacity: 0.55; filter: blur(0.2px); }

      /* shimmer overlay using pseudo-like approach (wrapper div) */
      .chart-wrap-loading {
        position: relative;
      }
      .chart-wrap-loading::after{
        content:"";
        position:absolute;
        inset:0;
        border-radius:12px;
        background: linear-gradient(
          90deg,
          rgba(229,231,235,0.0) 0%,
          rgba(229,231,235,0.45) 35%,
          rgba(229,231,235,0.0) 70%
        );
        transform: translateX(-100%);
        animation: chartShimmer 1.1s infinite;
        pointer-events:none;
      }
      @keyframes chartShimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
      }

      /* weather strip skeleton */
      .wx-skeleton{ display:flex; gap:10px; padding:8px 4px; }
      .wx-skel{
        height:74px; width:68px; border-radius:14px;
        background: linear-gradient(90deg, #f3f4f6 0%, #e5e7eb 40%, #f3f4f6 80%);
        background-size: 220% 100%;
        animation: wxSk 1.1s infinite;
      }
      @keyframes wxSk {
        0%{ background-position: 200% 0; }
        100%{ background-position: -200% 0; }
      }

      /* small icon animations already used in your code */
      .wx-anim-float { animation: wxFloat 1.8s ease-in-out infinite; }
      @keyframes wxFloat { 0%,100%{ transform: translateY(0);} 50%{ transform: translateY(-2px);} }

      .wx-anim-wiggle { animation: wxWiggle 1.6s ease-in-out infinite; }
      @keyframes wxWiggle { 0%,100%{ transform: rotate(0deg);} 50%{ transform: rotate(-1.5deg);} }
    `;
    document.head.appendChild(style);
  }

  function setWrapLoadingForCanvas(canvasId, loading) {
    const c = $(canvasId);
    if (!c) return;
    const wrap = c.parentElement;
    if (!wrap) return;
    if (loading) wrap.classList.add("chart-wrap-loading");
    else wrap.classList.remove("chart-wrap-loading");
  }

  /* -----------------------------
     Tabs: Soil / Weather / Status
  ----------------------------- */
  const tabBtns = document.querySelectorAll(".seg-btn");
  const panels = {
    soil: $("tab-soil"),
    weather: $("tab-weather"),
    status: $("tab-status"),
  };

  function setActiveTab(tabKey) {
    tabBtns.forEach((b) => b.classList.toggle("active", b.dataset.tab === tabKey));
    Object.keys(panels).forEach((k) => panels[k]?.classList.toggle("active", k === tabKey));
  }

  function isStatusTabActive() {
    return !!$("tab-status")?.classList.contains("active");
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      setActiveTab(tab);

      if (tab === "status") {
        openCropStatusAndRenderMap().catch((e) => console.warn("Map render failed:", e));
      }

      if (tab === "weather") {
        raf2(() => loadCleanWeatherCard());
        raf2(() => loadWeatherComboChart()); // ✅ bar+line chart
      }
    });
  });

  // Crop select -> refresh map only when status tab active
  document.addEventListener("DOMContentLoaded", () => {
    const cropTypeSelect = $("cropTypeSelect");
    if (cropTypeSelect) {
      cropTypeSelect.addEventListener("change", () => {
        if (isStatusTabActive()) {
          openCropStatusAndRenderMap().catch((e) => console.warn("Map render failed:", e));
        }
      });
    }
  });

  /* -----------------------------
     Charts (Chart.js)
  ----------------------------- */
  let soilChart = null;
  let orderChart = null;
  let shipChart = null;
  let weatherComboChart = null;
  let mfgPie = null;

  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas || typeof Chart === "undefined") return;
    const ctx = canvas.getContext("2d");

    const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, "rgba(124, 58, 237, 0.55)");
    gradient.addColorStop(0.6, "rgba(124, 58, 237, 0.20)");
    gradient.addColorStop(1, "rgba(124, 58, 237, 0.02)");

    if (soilChart) soilChart.destroy();

    addChartLoading("soilLineChart");
    setWrapLoadingForCanvas("soilLineChart", true);

    soilChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Soil Temperature",
            data: points,
            tension: 0.35,
            pointRadius: 4,
            pointHoverRadius: 5,
            fill: true,
            borderColor: "#7C3AED",
            backgroundColor: gradient,
            pointBackgroundColor: "#7C3AED",
            pointBorderColor: "#fff",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          ...chartAnimStagger(35),
          onComplete: () => {
            removeChartLoading("soilLineChart");
            setWrapLoadingForCanvas("soilLineChart", false);
          },
        },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { display: false }, ticks: { display: false } },
        },
      },
    });
  }

  function initSoilSelectors() {
    const metricSel = $("soilMetricSelect");
    if (!metricSel) return;

    metricSel.addEventListener("change", () => {
      const key = metricSel.value;
      const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const series =
        data.soil?.[key] ||
        data.soil?.soil_temp ||
        [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

      if (!soilChart) return;

      addChartLoading("soilLineChart");
      setWrapLoadingForCanvas("soilLineChart", true);

      soilChart.data.labels = labels;
      soilChart.data.datasets[0].data = series;
      soilChart.data.datasets[0].label =
        key === "soil_moisture"
          ? "Soil Moisture"
          : key === "ph"
          ? "pH"
          : key === "npk"
          ? "NPK Level"
          : "Soil Temperature";
      soilChart.update();

      // stop shimmer shortly after update
      setTimeout(() => {
        removeChartLoading("soilLineChart");
        setWrapLoadingForCanvas("soilLineChart", false);
      }, 450);
    });
  }

  function initOrderDonut() {
    const canvas = $("orderDonutChart");
    if (!canvas || typeof Chart === "undefined") return;
    const ctx = canvas.getContext("2d");

    const o = data.orders || {};
    const values = [
      safeNum(o.requested),
      safeNum(o.in_transit),
      safeNum(o.completed),
      safeNum(o.payment_received),
    ];

    const total = values.reduce((a, b) => a + b, 0);
    if ($("orderTotal")) $("orderTotal").textContent = String(total);
    if ($("oRequested")) $("oRequested").textContent = String(values[0]);
    if ($("oInTransit")) $("oInTransit").textContent = String(values[1]);
    if ($("oCompleted")) $("oCompleted").textContent = String(values[2]);
    if ($("oPaid")) $("oPaid").textContent = String(values[3]);

    if (orderChart) orderChart.destroy();

    addChartLoading("orderDonutChart");
    setWrapLoadingForCanvas("orderDonutChart", true);

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In transit", "Completed", "Payment Received"],
        datasets: [
          {
            data: values,
            borderWidth: 0,
            backgroundColor: ["#FDE68A", "#60A5FA", "#86EFAC", "#C4B5FD"],
          },
        ],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } },
        animation: {
          ...chartAnimStagger(35),
          onComplete: () => {
            removeChartLoading("orderDonutChart");
            setWrapLoadingForCanvas("orderDonutChart", false);
          },
        },
      },
    });
  }

  /* -----------------------------
     Shipment overview (numbers + chart)
     ✅ Fix: if data keys differ, fallback also reads shipments_summary
  ----------------------------- */
  async function initShipBars() {
    const canvas = $("shipBarChart");
    if (!canvas || typeof Chart === "undefined") return;

    await waitForVisible(canvas, 2500);

    const ctx = canvas.getContext("2d");

    // support both shapes: shipments or shipments_summary
    const s = data.shipments || data.shipments_summary || {};

    const values = [
      safeNum(s.requested ?? s.total_requested),
      safeNum(s.pending ?? s.total_pending),
      safeNum(s.in_transit ?? s.total_in_transit),
      safeNum(s.delivered ?? s.total_delivered),
      safeNum(s.payment ?? s.total_payment),
    ];

    // ✅ Set numbers
    if ($("sRequested")) $("sRequested").textContent = String(values[0]);
    if ($("sPending")) $("sPending").textContent = String(values[1]);
    if ($("sInTransit")) $("sInTransit").textContent = String(values[2]);
    if ($("sDelivered")) $("sDelivered").textContent = String(values[3]);
    if ($("sPayment")) $("sPayment").textContent = String(values[4]);

    // If all are zero, keep chart but avoid weird look
    const allZero = values.every((v) => v === 0);

    if (shipChart) shipChart.destroy();

    addChartLoading("shipBarChart");
    setWrapLoadingForCanvas("shipBarChart", true);

    shipChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Requested", "Pending", "In transit", "Delivered", "Payment"],
        datasets: [
          {
            label: "Shipments",
            data: allZero ? [1, 1, 1, 1, 1] : values,
            backgroundColor: ["#FDE68A", "#FCD34D", "#60A5FA", "#86EFAC", "#C4B5FD"],
            borderWidth: 0,
            borderRadius: 8,
            barThickness: 14,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          ...chartAnimStagger(60),
          onComplete: () => {
            removeChartLoading("shipBarChart");
            setWrapLoadingForCanvas("shipBarChart", false);
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: !allZero,
            displayColors: false,
            callbacks: {
              label: (ctx) => ` ${ctx.label}: ${allZero ? 0 : ctx.raw}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { display: false },
            border: { display: false },
          },
          y: {
            grid: { display: false },
            ticks: { color: "#6b7280", font: { size: 12, weight: "600" } },
            border: { display: false },
          },
        },
      },
    });
  }

  /* -----------------------------
     Manufacturer Pie (chart + numbers)
     ✅ No API call. Uses data.manufacturer_summary OR data.manufacturer_requests list.
  ----------------------------- */
  function countByStatus(items, statusKey = "status") {
    const out = {};
    (items || []).forEach((it) => {
      const s = String(it?.[statusKey] || "").toLowerCase().trim();
      if (!s) return;
      out[s] = (out[s] || 0) + 1;
    });
    return out;
  }

  function initManufacturerPieAndNumbers() {
    // Elements used in your HTML (must exist)
    const canvas = $("mfgPieChart");
    const wrap = $("mfgPieWrap");
    const emptyEl = $("emptyManufacturerCard");

    // Number elements
    const nReq = $("mfgRequested");
    const nProc = $("mfgProcessing");
    const nPay = $("mfgPendingPay");

    if (!canvas || typeof Chart === "undefined") return;

    // Prefer summary if backend provides
    const m = data.manufacturer_summary || data.manufacturer || null;

    // Else derive from list
    const fromList = countByStatus(data.manufacturer_requests);

    const requested = safeNum(m?.requested ?? fromList.requested ?? 0);
    const processing = safeNum(m?.processing ?? fromList.processing ?? 0);
    const pendingPay = safeNum(m?.pending_payment ?? fromList["pending payment"] ?? fromList.pending_payment ?? 0);

    const total = requested + processing + pendingPay;

    // show/hide empty state
    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "flex";
    } else {
      if (emptyEl) emptyEl.style.display = "none";
      if (wrap) wrap.style.display = "block";
    }

    // ✅ Set numbers (this was missing for you)
    if (nReq) nReq.textContent = String(requested);
    if (nProc) nProc.textContent = String(processing);
    if (nPay) nPay.textContent = String(pendingPay);

    // Chart
    const ctx = canvas.getContext("2d");
    if (mfgPie) mfgPie.destroy();

    addChartLoading("mfgPieChart");
    setWrapLoadingForCanvas("mfgPieChart", true);

    mfgPie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Processing", "Pending payment"],
        datasets: [
          {
            data: total <= 0 ? [1, 1, 1] : [requested, processing, pendingPay],
            borderWidth: 0,
            backgroundColor: ["#60A5FA", "#F59E0B", "#6366F1"],
          },
        ],
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: total > 0,
            callbacks: {
              label: (ctx) => {
                const v = total <= 0 ? 0 : ctx.raw;
                return ` ${ctx.label}: ${v}`;
              },
            },
          },
        },
        animation: {
          ...chartAnimStagger(40),
          onComplete: () => {
            removeChartLoading("mfgPieChart");
            setWrapLoadingForCanvas("mfgPieChart", false);
          },
        },
      },
    });
  }

  /* ============================================================
     WEATHER TAB
     ✅ Adds a REAL Chart.js combo chart (bar + line)
     Canvas required: id="weatherComboChart"
  ============================================================ */
  function wxSetStripSkeleton(el) {
    if (!el) return;
    el.innerHTML = `
      <div class="wx-skeleton">
        <div class="wx-skel"></div><div class="wx-skel"></div><div class="wx-skel"></div>
        <div class="wx-skel"></div><div class="wx-skel"></div><div class="wx-skel"></div>
      </div>
    `;
  }

  function wxSetStripError(el, msg) {
    if (!el) return;
    el.innerHTML = `<div class="muted" style="padding:10px;">${msg || "Weather unavailable"}</div>`;
  }

  function wxWindDirText(deg) {
    const d = Number(deg);
    if (!Number.isFinite(d)) return "—";
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(d / 45) % 8] + ` (${Math.round(d)}°)`;
  }

  function wxFmtHourLabel(dateObj, isNow) {
    if (isNow) return "Now";
    return dateObj.toLocaleTimeString([], { hour: "numeric" }).replace(" ", "");
  }

  function wxFmtDayLabel(dateStr, isToday) {
    if (isToday) return "Today";
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString([], { weekday: "short" });
  }

  function wxSvgIcon(code) {
    const common =
      'stroke="#0f172a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"';
    const sun = `
      <svg class="wx-anim-float" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="24" r="7" ${common}></circle>
        <path d="M24 4v6" ${common}></path><path d="M24 38v6" ${common}></path>
        <path d="M4 24h6" ${common}></path><path d="M38 24h6" ${common}></path>
        <path d="M9 9l4 4" ${common}></path><path d="M35 35l4 4" ${common}></path>
        <path d="M39 9l-4 4" ${common}></path><path d="M13 35l-4 4" ${common}></path>
      </svg>
    `;
    const cloud = `
      <svg class="wx-anim-float" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M16 34h18a8 8 0 0 0 0-16 10 10 0 0 0-19-3A7 7 0 0 0 16 34Z" ${common}></path>
      </svg>
    `;
    const partly = `
      <svg class="wx-anim-float" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M18 14a6 6 0 1 0 0.1 0" ${common}></path>
        <path d="M18 6v4" ${common}></path><path d="M8 14h4" ${common}></path><path d="M30 14h4" ${common}></path>
        <path d="M11 7l3 3" ${common}></path><path d="M25 7l-3 3" ${common}></path>
        <path d="M18 34h18a8 8 0 0 0 0-16 10 10 0 0 0-19-3A7 7 0 0 0 18 34Z" ${common}></path>
      </svg>
    `;
    const rain = `
      <svg class="wx-anim-wiggle" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M16 28h18a7 7 0 0 0 0-14 10 10 0 0 0-19-3A7 7 0 0 0 16 28Z" ${common}></path>
        <path d="M18 34l-2 4" ${common}></path>
        <path d="M26 34l-2 4" ${common}></path>
        <path d="M34 34l-2 4" ${common}></path>
      </svg>
    `;
    const thunder = `
      <svg class="wx-anim-wiggle" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M16 26h18a7 7 0 0 0 0-14 10 10 0 0 0-19-3A7 7 0 0 0 16 26Z" ${common}></path>
        <path d="M25 26l-6 10h6l-2 10 8-14h-6l2-6" ${common}></path>
      </svg>
    `;
    const fog = `
      <svg class="wx-anim-float" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M10 18h28" ${common}></path>
        <path d="M6 24h30" ${common}></path>
        <path d="M12 30h26" ${common}></path>
      </svg>
    `;

    const c = Number(code || 0);
    if ([0, 1].includes(c)) return sun;
    if ([2].includes(c)) return partly;
    if ([3].includes(c)) return cloud;
    if ([45, 48].includes(c)) return fog;
    if ([51, 53, 55, 56, 57, 61, 63, 65, 80, 81, 82].includes(c)) return rain;
    if ([95, 96, 99].includes(c)) return thunder;
    return cloud;
  }

  async function wxFetchForecast(lat, lng) {
    const url =
      `https://api.open-meteo.com/v1/forecast` +
      `?latitude=${encodeURIComponent(lat)}` +
      `&longitude=${encodeURIComponent(lng)}` +
      `&current_weather=true` +
      `&hourly=temperature_2m,weathercode` +
      `&daily=temperature_2m_max,temperature_2m_min,weathercode` +
      `&forecast_days=7` +
      `&timezone=auto`;

    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`Weather API failed (${res.status})`);
    return res.json();
  }

  function wxRenderCurrent(apiData) {
    const cur = apiData?.current_weather;
    const nowTemp = $("wxNowTemp");
    const nowIcon = $("wxNowIcon");
    const nowMeta = $("wxNowMeta");
    const wind = $("wxWind");
    const windDir = $("wxWindDir");
    const codeEl = $("wxCode");

    if (!cur || !nowTemp || !nowIcon) return;

    const t = Number(cur.temperature);
    const ws = Number(cur.windspeed);
    const wd = Number(cur.winddirection);
    const code = Number(cur.weathercode);

    nowTemp.textContent = Number.isFinite(t) ? `${t.toFixed(1)}°C` : "—";
    nowIcon.innerHTML = wxSvgIcon(code);
    if (nowMeta) nowMeta.textContent = cur.time ? `Updated: ${cur.time}` : "Updated just now";

    if (wind) wind.textContent = Number.isFinite(ws) ? `${ws.toFixed(1)} km/h` : "—";
    if (windDir) windDir.textContent = wxWindDirText(wd);
    if (codeEl) codeEl.textContent = Number.isFinite(code) ? String(code) : "—";
  }

  function wxRenderHourly(apiData) {
    const row = $("wxHourlyRow");
    const meta = $("wxHourlyMeta");
    if (!row) return;

    const times = apiData?.hourly?.time || [];
    const temps = apiData?.hourly?.temperature_2m || [];
    const codes = apiData?.hourly?.weathercode || [];

    if (!times.length || !temps.length) {
      wxSetStripError(row, "Hourly data not available.");
      if (meta) meta.textContent = "—";
      return;
    }

    const now = new Date();
    let startIdx = 0;
    for (let i = 0; i < times.length; i++) {
      const t = new Date(times[i]);
      if (t.getTime() >= now.getTime()) {
        startIdx = i;
        break;
      }
    }

    const items = [];
    for (let k = 0; k < 6; k++) {
      const i = startIdx + k;
      if (!times[i]) break;
      const t = new Date(times[i]);
      items.push(`
        <div class="wx-item">
          <div class="wx-time">${wxFmtHourLabel(t, k === 0)}</div>
          <div class="wx-icon">${wxSvgIcon(codes[i])}</div>
          <div class="wx-temp">${Math.round(Number(temps[i] ?? 0))}°</div>
        </div>
      `);
    }

    row.innerHTML = items.join("");
    if (meta) meta.textContent = "Next 6 hours";
  }

  function wxRenderWeekly(apiData) {
    const row = $("wxWeeklyRow");
    const meta = $("wxWeeklyMeta");
    if (!row) return;

    const days = apiData?.daily?.time || [];
    const tmax = apiData?.daily?.temperature_2m_max || [];
    const tmin = apiData?.daily?.temperature_2m_min || [];
    const codes = apiData?.daily?.weathercode || [];

    if (!days.length || !tmax.length || !tmin.length) {
      wxSetStripError(row, "Weekly data not available.");
      if (meta) meta.textContent = "—";
      return;
    }

    const items = [];
    for (let i = 0; i < Math.min(7, days.length); i++) {
      items.push(`
        <div class="wx-item">
          <div class="wx-time">${wxFmtDayLabel(days[i], i === 0)}</div>
          <div class="wx-icon">${wxSvgIcon(codes[i])}</div>
          <div class="wx-temp">
            ${Math.round(Number(tmax[i] ?? 0))}°
            <span class="wx-tempSub">/${Math.round(Number(tmin[i] ?? 0))}°</span>
          </div>
        </div>
      `);
    }

    row.innerHTML = items.join("");
    if (meta) meta.textContent = apiData?.timezone || "Next 7 days";
  }

  function wxOpenModal() {
    const m = $("wxLocModal");
    if (m) m.style.display = "block";
  }
  function wxCloseModal() {
    const m = $("wxLocModal");
    if (m) m.style.display = "none";
  }

  function wxGetSavedCoords() {
    try {
      const raw = localStorage.getItem("wx_live_coords");
      if (!raw) return null;
      const obj = JSON.parse(raw);
      const lat = Number(obj?.lat);
      const lng = Number(obj?.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
      return { lat, lng, source: "device" };
    } catch {
      return null;
    }
  }

  function wxSaveCoords(lat, lng) {
    try {
      localStorage.setItem("wx_live_coords", JSON.stringify({ lat, lng, at: Date.now() }));
    } catch {}
  }

  function wxGetDashboardCoords() {
    const geo = data?.geo || {};
    const lat = Number(geo?.lat);
    const lng = Number(geo?.lng);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return { lat, lng, source: "dashboard", address: geo?.address || "" };
    }
    return null;
  }

  // Build the next 12 hours series for combo chart
  function wxBuildNextHours(apiData, hours = 12) {
    const times = apiData?.hourly?.time || [];
    const temps = apiData?.hourly?.temperature_2m || [];
    if (!times.length || !temps.length) return { labels: [], values: [] };

    const now = new Date();
    let startIdx = 0;
    for (let i = 0; i < times.length; i++) {
      const t = new Date(times[i]);
      if (t.getTime() >= now.getTime()) { startIdx = i; break; }
    }

    const labels = [];
    const values = [];
    for (let k = 0; k < hours; k++) {
      const i = startIdx + k;
      if (!times[i]) break;
      const d = new Date(times[i]);
      labels.push(d.toLocaleTimeString([], { hour: "numeric" }).replace(" ", ""));
      values.push(Number(temps[i] ?? 0));
    }
    return { labels, values };
  }

  // ✅ Weather combo chart (bar + line)
  async function renderWeatherComboChart(apiData) {
    const canvas = $("weatherComboChart"); // <-- your canvas id
    if (!canvas || typeof Chart === "undefined") return;

    await waitForVisible(canvas, 2500);

    const ctx = canvas.getContext("2d");
    const { labels, values } = wxBuildNextHours(apiData, 12);

    if (!labels.length) return;

    if (weatherComboChart) weatherComboChart.destroy();

    addChartLoading("weatherComboChart");
    setWrapLoadingForCanvas("weatherComboChart", true);

    // Smooth line gradient
    const lineGrad = ctx.createLinearGradient(0, 0, 0, canvas.height);
    lineGrad.addColorStop(0, "rgba(99,102,241,0.35)");
    lineGrad.addColorStop(1, "rgba(99,102,241,0.02)");

    weatherComboChart = new Chart(ctx, {
      data: {
        labels,
        datasets: [
          // Bars
          {
            type: "bar",
            label: "Temp (bars)",
            data: values,
            backgroundColor: "rgba(99,102,241,0.18)",
            borderColor: "rgba(99,102,241,0.55)",
            borderWidth: 1,
            borderRadius: 8, // less radius than earlier (more premium)
            barThickness: 20,
            maxBarThickness: 26,
            categoryPercentage: 0.85,
            barPercentage: 0.9,
          },
          // Line
          {
            type: "line",
            label: "Temp (line)",
            data: values,
            borderColor: "#4F46E5",
            backgroundColor: lineGrad,
            fill: true,
            tension: 0.35,
            pointRadius: 3.5,
            pointHoverRadius: 5,
            pointBackgroundColor: "#4F46E5",
            pointBorderColor: "#ffffff",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          ...chartAnimStagger(35),
          onComplete: () => {
            removeChartLoading("weatherComboChart");
            setWrapLoadingForCanvas("weatherComboChart", false);
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            displayColors: false,
            backgroundColor: "#ffffff",
            titleColor: "#111827",
            bodyColor: "#111827",
            borderColor: "#e5e7eb",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              title: (ctx) => `Time: ${ctx[0].label}`,
              label: (ctx) => `${Number(ctx.raw).toFixed(1)} °C`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#6b7280", font: { size: 11 } },
          },
          y: {
            grid: { display: false },
            ticks: { color: "#6b7280", font: { size: 11 } },
          },
        },
      },
    });
  }

  // Store last fetched weather payload so tab switch can re-render chart without re-fetch
  let __WX_CACHE = null;

  async function wxLoadWeatherUsing(lat, lng, label) {
    if ($("wxLocText")) $("wxLocText").textContent = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;

    wxSetStripSkeleton($("wxHourlyRow"));
    wxSetStripSkeleton($("wxWeeklyRow"));

    try {
      const apiData = await wxFetchForecast(lat, lng);
      __WX_CACHE = apiData;

      wxRenderCurrent(apiData);
      wxRenderHourly(apiData);
      wxRenderWeekly(apiData);

      // ✅ render combo chart
      await renderWeatherComboChart(apiData);
    } catch (e) {
      console.error("Weather fetch failed:", e);
      wxSetStripError($("wxHourlyRow"), "Weather unavailable right now.");
      wxSetStripError($("wxWeeklyRow"), "Weather unavailable right now.");
    }
  }

  async function loadCleanWeatherCard() {
    const panel = $("tab-weather");
    if (panel) await waitForVisible(panel, 2500);

    const live = wxGetSavedCoords();
    if (live) return wxLoadWeatherUsing(live.lat, live.lng, "Live location");

    const dash = wxGetDashboardCoords();
    if (dash) {
      const label = (dash.address || "").trim() || `${dash.lat.toFixed(4)}, ${dash.lng.toFixed(4)}`;
      return wxLoadWeatherUsing(dash.lat, dash.lng, label);
    }

    wxSetStripError($("wxHourlyRow"), "No location found (lat/lng missing).");
    wxSetStripError($("wxWeeklyRow"), "No location found (lat/lng missing).");
  }

  async function loadWeatherComboChart() {
    // Re-render chart from cache if available
    const panel = $("tab-weather");
    if (panel) await waitForVisible(panel, 2500);

    if (__WX_CACHE) {
      await renderWeatherComboChart(__WX_CACHE);
    }
  }

  async function requestLiveLocationAndLoad() {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported in this browser.");
      return;
    }

    wxSetStripSkeleton($("wxHourlyRow"));
    wxSetStripSkeleton($("wxWeeklyRow"));

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos?.coords?.latitude);
        const lng = Number(pos?.coords?.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          wxCloseModal();
          return;
        }
        wxSaveCoords(lat, lng);
        wxCloseModal();
        wxLoadWeatherUsing(lat, lng, "Live location");
      },
      (err) => {
        console.warn("Geolocation denied/failed:", err);
        wxCloseModal();
        loadCleanWeatherCard();
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 600000 }
    );
  }

  function initWeatherUI() {
    const modal = $("wxLocModal");
    if (modal && !modal.__bound) {
      modal.__bound = true;
      modal.addEventListener("click", (e) => {
        const t = e.target;
        if (t && t.getAttribute && t.getAttribute("data-close") === "1") wxCloseModal();
      });
    }

    const allowBtn = $("wxAllowBtn");
    if (allowBtn && !allowBtn.__bound) {
      allowBtn.__bound = true;
      allowBtn.addEventListener("click", requestLiveLocationAndLoad);
    }

    const useMyLocBtn = $("weatherUseMyLocationBtn");
    if (useMyLocBtn && !useMyLocBtn.__bound) {
      useMyLocBtn.__bound = true;
      useMyLocBtn.addEventListener("click", () => wxOpenModal());
    }

    const refreshBtn = $("weatherRefreshBtn");
    if (refreshBtn && !refreshBtn.__bound) {
      refreshBtn.__bound = true;
      refreshBtn.addEventListener("click", async () => {
        await loadCleanWeatherCard();
        await loadWeatherComboChart();
      });
    }

    // If weather tab active on load
    if ($("tab-weather")?.classList.contains("active")) {
      raf2(async () => {
        await loadCleanWeatherCard();
        await loadWeatherComboChart();
      });
    }
  }

  // expose
  window.loadCleanWeatherCard = loadCleanWeatherCard;

  /* -----------------------------
     Right lists
  ----------------------------- */
  function renderList(containerId, items, selectedDate) {
    const el = $(containerId);
    if (!el) return;

    el.innerHTML = "";
    const filtered = (items || []).filter((x) => withinTill(x.due_at || x.created_at, selectedDate));
    if (!filtered.length) return;

    filtered.forEach((it) => {
      const title = it.title || it.task || "Task";
      const sub = it.sub || it.subtitle || it.meta || "";
      const status = (it.status || "").toLowerCase();
      const dateLabel = fmtDate(toDate(it.due_at || it.created_at));

      el.insertAdjacentHTML(
        "beforeend",
        `
        <div class="task-item">
          <div class="task-ico" aria-hidden="true">⚙️</div>
          <div style="flex:1;">
            <div class="task-title">${escapeHtml(title)}</div>
            <div class="task-sub">${escapeHtml(sub)} ${dateLabel !== "-" ? "• " + dateLabel : ""}</div>
            ${status ? `<div class="pill">${escapeHtml(cap(status))}</div>` : ""}
          </div>
          <div style="color:#9ca3af; padding-top:2px;">›</div>
        </div>
      `
      );
    });
  }

  function initDateFilters() {
    const todayISO = new Date().toISOString().slice(0, 10);

    const tasksDate = $("tasksDate");
    const warehouseDate = $("warehouseDate");
    const mfgDate = $("mfgDate");
    if (!tasksDate || !warehouseDate || !mfgDate) return;

    tasksDate.value = todayISO;
    warehouseDate.value = todayISO;
    mfgDate.value = todayISO;

    function refreshAll() {
      renderList("pendingTasksList", data.pending_tasks, tasksDate.value);
      renderList("warehouseList", data.warehouse_requests, warehouseDate.value);
      renderList("manufacturerList", data.manufacturer_requests, mfgDate.value);

      try {
        if (typeof window.applyDashboardEmptyStates === "function") {
          window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
        }
      } catch (e) {}
    }

    tasksDate.addEventListener("change", refreshAll);
    warehouseDate.addEventListener("change", refreshAll);
    mfgDate.addEventListener("change", refreshAll);

    refreshAll();
  }

  /* -----------------------------
     Leaflet Crop Status Map (unchanged)
  ----------------------------- */
  let dashboardLeafletMap = null;
  let dashboardPolygonLayers = [];

  function isLeafletReady() {
    return typeof L !== "undefined";
  }

  async function ensureLeafletMapInitialized() {
    if (dashboardLeafletMap) return dashboardLeafletMap;

    const el = $("farmMap");
    if (!el) return null;

    await waitForVisible(el, 8000);

    const start = Date.now();
    while (!isLeafletReady()) {
      await new Promise((r) => setTimeout(r, 50));
      if (Date.now() - start > 8000) throw new Error("Leaflet not loaded");
    }

    dashboardLeafletMap = L.map("farmMap", {
      center: [20.5937, 78.9629],
      zoom: 5,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(dashboardLeafletMap);

    return dashboardLeafletMap;
  }

  function clearLeafletPolygons() {
    if (!dashboardLeafletMap) return;
    dashboardPolygonLayers.forEach((layer) => {
      try {
        dashboardLeafletMap.removeLayer(layer);
      } catch (e) {}
    });
    dashboardPolygonLayers = [];
  }

  function normalizeCoords(coords) {
    if (!Array.isArray(coords)) return [];
    return coords
      .map((p) => {
        const lat = Number(p?.lat);
        const lng = Number(p?.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
        return [lat, lng];
      })
      .filter(Boolean);
  }

  async function loadAndRenderFarmsLeaflet() {
    const map = await ensureLeafletMapInitialized();
    if (!map) return;

    setTimeout(() => {
      try {
        map.invalidateSize();
      } catch (e) {}
    }, 60);

    const cropTypeSelect = $("cropTypeSelect");
    const cropType = cropTypeSelect ? cropTypeSelect.value : "";

    const url = cropType
      ? `/farmer/dashboard/api/farms?cropType=${encodeURIComponent(cropType)}`
      : `/farmer/dashboard/api/farms`;

    let out;
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      out = await res.json();
    } catch (e) {
      console.error("❌ farms api fetch failed:", e);
      return;
    }

    clearLeafletPolygons();

    if (!out?.ok || !Array.isArray(out.farms) || out.farms.length === 0) {
      map.setView([20.5937, 78.9629], 5);
      return;
    }

    const allBounds = [];

    out.farms.forEach((farm) => {
      const coords = normalizeCoords(farm.coordinates);
      if (coords.length < 3) return;

      const polygon = L.polygon(coords, {
        color: "#0f913d",
        weight: 2,
        fillColor: "#0f913d",
        fillOpacity: 0.3,
      }).addTo(map);

      dashboardPolygonLayers.push(polygon);

      const infoHtml = `
        <div style="font-size:13px;">
          <strong>${escapeHtml(farm.cropType || "Crop")}</strong><br/>
          Crop ID: ${escapeHtml(farm.crop_id || "-")}<br/>
          Area: ${escapeHtml(farm.area_size || "-")} acres<br/>
          Planted: ${escapeHtml(farm.date_planted || "-")}
        </div>
      `;
      polygon.bindPopup(infoHtml);

      coords.forEach((c) => allBounds.push(c));
    });

    if (allBounds.length) {
      map.fitBounds(allBounds, { padding: [20, 20] });
    }
  }

  async function openCropStatusAndRenderMap() {
    const farmMapEl = $("farmMap");
    if (!farmMapEl) return;

    setActiveTab("status");
    await waitForVisible(farmMapEl, 8000);

    await ensureLeafletMapInitialized();

    setTimeout(() => {
      try {
        dashboardLeafletMap.invalidateSize();
      } catch (e) {}
    }, 80);

    await loadAndRenderFarmsLeaflet();
  }

  window.initFarmMap = function initFarmMap() {};

  /* -----------------------------
     BOOT
  ----------------------------- */
  document.addEventListener("DOMContentLoaded", async () => {
    injectChartLoadingCSS();

    initSoilChart();
    initSoilSelectors();

    initOrderDonut();

    // ✅ Shipment + Manufacturer (working + numbers)
    await initShipBars();
    initManufacturerPieAndNumbers();

    initDateFilters();
    initWeatherUI();

    // If weather is default active, render combo
    if ($("tab-weather")?.classList.contains("active")) {
      raf2(async () => {
        await loadCleanWeatherCard();
        await loadWeatherComboChart();
      });
    }

    try {
      if (typeof window.applyDashboardEmptyStates === "function") {
        window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
      }
    } catch (e) {}
  });
})();
