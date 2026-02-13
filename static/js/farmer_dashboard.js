(function () {
  "use strict";

  const data = window.__DASHBOARD__ || {};
  const $ = (id) => document.getElementById(id);

  /* -------------------------------------------------------
     Utils
  ------------------------------------------------------- */
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

  function setText(id, val) {
    const el = $(id);
    if (!el) return;
    el.textContent = val === undefined || val === null ? "0" : String(val);
  }

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

  // Add/remove loading shimmer class
  function withLoading(elOrId, on) {
    const el = typeof elOrId === "string" ? $(elOrId) : elOrId;
    if (!el) return;
    el.classList.toggle("is-loading", !!on);
  }

  // Chart animation
  function chartAnimStagger(delayBase = 30) {
    return {
      duration: 850,
      easing: "easeOutQuart",
      delay: (ctx) => (ctx.type === "data" ? ctx.dataIndex * delayBase : 0),
    };
  }

  /* -------------------------------------------------------
     Tabs: Soil / Weather / Status
  ------------------------------------------------------- */
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
        raf2(() => loadWeatherAll()); // ✅ ensures weather loads every time
      }

      if (tab === "soil") {
        raf2(() => {
          if (soilChart) soilChart.resize();
        });
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

  /* -------------------------------------------------------
     Charts
  ------------------------------------------------------- */
  let soilChart = null;
  let orderChart = null;
  let warehousePie = null;
  let mfgPie = null;
  let weatherBarChart = null;

  /* -----------------------------
     SOIL CHART
  ----------------------------- */
  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas || typeof Chart === "undefined") return;

    const wrap = canvas.closest(".chart-wrap") || canvas.parentElement;
    withLoading(wrap, true);

    const ctx = canvas.getContext("2d");
    const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, "rgba(124, 58, 237, 0.55)");
    gradient.addColorStop(0.6, "rgba(124, 58, 237, 0.20)");
    gradient.addColorStop(1, "rgba(124, 58, 237, 0.02)");

    if (soilChart) soilChart.destroy();

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
        animation: chartAnimStagger(25),
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { display: false }, ticks: { display: false } },
        },
      },
    });

    setTimeout(() => withLoading(wrap, false), 850);
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
    });
  }

  /* -----------------------------
     ORDER DONUT (rounded segments + spacing)
  ----------------------------- */
  function initOrderDonut() {
    const canvas = $("orderDonutChart");
    if (!canvas || typeof Chart === "undefined") return;
    const wrap = canvas.closest(".donut-wrap") || canvas.parentElement;

    const ctx = canvas.getContext("2d");
    const o = data.orders || {};

    const values = [
      safeNum(o.requested),
      safeNum(o.in_transit),
      safeNum(o.completed),
      safeNum(o.payment_received),
    ];

    const total = values.reduce((a, b) => a + b, 0);
    setText("orderTotal", total);
    setText("oRequested", values[0]);
    setText("oInTransit", values[1]);
    setText("oCompleted", values[2]);
    setText("oPaid", values[3]);

    withLoading(wrap, true);

    if (orderChart) orderChart.destroy();

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In transit", "Completed", "Payment Received"],
        datasets: [
          {
            data: values,
            borderWidth: 0,
            backgroundColor: ["#FDE68A", "#60A5FA", "#86EFAC", "#C4B5FD"],
            borderRadius: 14,  // ✅ rounded edges like “previous”
            spacing: 5,        // ✅ gaps like old UI
            hoverOffset: 6,
          },
        ],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } },
        animation: chartAnimStagger(22),
      },
    });

    setTimeout(() => withLoading(wrap, false), 850);
  }

  /* -------------------------------------------------------
     ✅ SHIPMENTS (DIV BASED, NOT Chart.js)
     Uses your: #shipBars + legend IDs
  ------------------------------------------------------- */
 async function renderShipmentBars() {
  const container = $("shipBars");
  if (!container) return;

  // ✅ Wait until card is visible (important because your empty-state toggles/hide/show)
  await waitForVisible(container.closest("#shipmentOverviewCard") || container, 2500);

  const s = data.shipments || {};
  const values = {
    requested: safeNum(s.requested),
    pending: safeNum(s.pending),
    in_transit: safeNum(s.in_transit),
    delivered: safeNum(s.delivered),
    payment: safeNum(s.payment),
  };

  setText("sRequested", values.requested);
  setText("sPending", values.pending);
  setText("sInTransit", values.in_transit);
  setText("sDelivered", values.delivered);
  setText("sPayment", values.payment);

  const total =
    values.requested +
    values.pending +
    values.in_transit +
    values.delivered +
    values.payment;

  const emptyEl = $("emptyShipmentCard");
  const contentEl = $("shipmentCardContent");

  if (total <= 0) {
    if (emptyEl) emptyEl.style.display = "flex";
    if (contentEl) contentEl.style.display = "none";
    container.innerHTML = "";
    return;
  }

  if (emptyEl) emptyEl.style.display = "none";
  if (contentEl) contentEl.style.display = "block";

  // ✅ Use max value for proper comparison width
  const max = Math.max(
    1,
    values.requested,
    values.pending,
    values.in_transit,
    values.delivered,
    values.payment
  );

  const rows = [
    { key: "requested", label: "Requested", cls: "req" },
    { key: "pending", label: "Pending", cls: "pending" },
    { key: "in_transit", label: "In transit", cls: "transit" },
    { key: "delivered", label: "Delivered", cls: "del" },
    { key: "payment", label: "Payment", cls: "pay" },
  ];

  container.innerHTML = rows
    .map(
      (r) => `
        <div class="ship-row">
          <div class="ship-label">${escapeHtml(r.label)}</div>
          <div class="ship-track">
            <div class="ship-fill ${r.cls}" data-key="${r.key}" style="width:0%"></div>
          </div>
        </div>
      `
    )
    .join("");

  raf2(() => {
    container.querySelectorAll(".ship-fill").forEach((fill) => {
      const key = fill.getAttribute("data-key");
      const pct = Math.round((values[key] / max) * 100);
      fill.style.width = pct + "%";
    });
  });
}


  /* -------------------------------------------------------
     Warehouse + Manufacturer (pie charts)
  ------------------------------------------------------- */
  function countByStatus(items) {
    const out = {};
    (items || []).forEach((it) => {
      const s = String(it?.status || it?.request_status || it?.state || "")
        .toLowerCase()
        .trim();
      if (!s) return;
      out[s] = (out[s] || 0) + 1;
    });
    return out;
  }

  function initWarehousePie() {
    const canvas = $("warehousePieChart");
    const wrap = $("warehousePieWrap");
    const emptyEl = $("emptyWarehouseCard");
    const list = Array.isArray(data.warehouse_requests) ? data.warehouse_requests : [];
    const summary = data.warehouse_summary || data.warehouse || null;

    const fromList = countByStatus(list);

    // Try best mapping:
    const requested = safeNum(summary?.requested ?? fromList.requested ?? fromList["request"] ?? 0);
    const stored = safeNum(summary?.stored ?? fromList.stored ?? fromList.accepted ?? 0);
    const pendingPay = safeNum(
      summary?.pending_payment ??
        fromList["pending payment"] ??
        fromList.pending_payment ??
        fromList.pendingpay ??
        0
    );

    setText("whRequested", requested);
    setText("whStored", stored);
    setText("whPendingPay", pendingPay);

    const total = requested + stored + pendingPay;

    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "block";
      if (warehousePie) {
        warehousePie.destroy();
        warehousePie = null;
      }
      return;
    } else {
      if (emptyEl) emptyEl.style.display = "none";
      if (wrap) wrap.style.display = "flex";
    }

    if (!canvas || typeof Chart === "undefined") return;

    withLoading(wrap, true);

    const ctx = canvas.getContext("2d");
    if (warehousePie) warehousePie.destroy();

    warehousePie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Stored", "Pending payment"],
        datasets: [
          {
            data: [requested, stored, pendingPay],
            borderWidth: 0,
            backgroundColor: ["#FDE68A", "#6366F1", "#60A5FA"],
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        animation: chartAnimStagger(35),
      },
    });

    setTimeout(() => withLoading(wrap, false), 850);
  }

  function initManufacturerPie() {
    const canvas = $("mfgPieChart");
    const wrap = $("mfgPieWrap");
    const emptyEl = $("emptyManufacturerCard");
    const list = Array.isArray(data.manufacturer_requests) ? data.manufacturer_requests : [];
    const summary = data.manufacturer_summary || data.manufacturer || null;

    const fromList = countByStatus(list);

    // Try best mapping:
    const requested = safeNum(summary?.requested ?? fromList.requested ?? 0);
    const processing = safeNum(summary?.processing ?? fromList.processing ?? fromList["in process"] ?? 0);
    const pendingPay = safeNum(
      summary?.pending_payment ??
        fromList["pending payment"] ??
        fromList.pending_payment ??
        0
    );

    setText("mfgRequested", requested);
    setText("mfgProcessing", processing);
    setText("mfgPendingPay", pendingPay);

    const total = requested + processing + pendingPay;

    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "block";
      if (mfgPie) {
        mfgPie.destroy();
        mfgPie = null;
      }
      return;
    } else {
      if (emptyEl) emptyEl.style.display = "none";
      if (wrap) wrap.style.display = "flex";
    }

    if (!canvas || typeof Chart === "undefined") return;

    withLoading(wrap, true);

    const ctx = canvas.getContext("2d");
    if (mfgPie) mfgPie.destroy();

    mfgPie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Processing", "Pending payment"],
        datasets: [
          {
            data: [requested, processing, pendingPay],
            borderWidth: 0,
            backgroundColor: ["#60A5FA", "#F59E0B", "#6366F1"],
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        animation: chartAnimStagger(35),
      },
    });

    setTimeout(() => withLoading(wrap, false), 850);
  }

  /* -------------------------------------------------------
     Right lists (Pending Tasks / Warehouse list / Manufacturer list)
  ------------------------------------------------------- */
  function renderList(containerId, items, selectedDate) {
    const el = $(containerId);
    if (!el) return;

    el.innerHTML = "";
    const filtered = (items || []).filter((x) => withinTill(x.due_at || x.created_at, selectedDate));
    if (!filtered.length) return;

    filtered.forEach((it) => {
      const title = it.title || it.task || it.name || "Task";
      const sub = it.sub || it.subtitle || it.meta || it.description || "";
      const status = (it.status || it.state || "").toLowerCase();
      const dateLabel = fmtDate(toDate(it.due_at || it.created_at || it.updated_at));

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

      // empty-state helper re-run (your existing function)
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

  /* -------------------------------------------------------
     WEATHER (Your EXACT HTML IDs)
     - Updates KPI row: wxTempKpi wxHumidityKpi wxWindKpi wxWindDirKpi
     - Renders Chart.js bar chart on #weatherBarChart (no line)
     - Uses Open-Meteo with humidity support
  ------------------------------------------------------- */
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
      return { lat, lng };
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
      return { lat, lng, address: geo?.address || "" };
    }
    return null;
  }

  async function wxFetchForecast(lat, lng) {
    // NOTE: include humidity + hourly windspeed_10m + winddirection_10m
    const url =
      `https://api.open-meteo.com/v1/forecast` +
      `?latitude=${encodeURIComponent(lat)}` +
      `&longitude=${encodeURIComponent(lng)}` +
      `&current_weather=true` +
      `&hourly=temperature_2m,relativehumidity_2m,windspeed_10m,winddirection_10m` +
      `&forecast_days=2` +
      `&timezone=auto`;

    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`Weather API failed (${res.status})`);
    return res.json();
  }

  function nearestHourlyIndex(times) {
    const now = Date.now();
    let best = 0;
    for (let i = 0; i < times.length; i++) {
      const t = new Date(times[i]).getTime();
      if (t >= now) return i;
      best = i;
    }
    return best;
  }

  function degToDir(deg) {
    const d = Number(deg);
    if (!Number.isFinite(d)) return "—";
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(d / 45) % 8] + ` (${Math.round(d)}°)`;
  }

  function extractNext12Hours(apiData) {
    const times = apiData?.hourly?.time || [];
    const temps = apiData?.hourly?.temperature_2m || [];
    if (!times.length || !temps.length) return { labels: [], values: [] };

    const startIdx = nearestHourlyIndex(times);
    const labels = [];
    const values = [];

    for (let k = 0; k < 12; k++) {
      const i = startIdx + k;
      if (!times[i]) break;
      const d = new Date(times[i]);
      labels.push(d.toLocaleTimeString([], { hour: "numeric" }).replace(" ", ""));
      values.push(Number(temps[i] ?? 0));
    }
    return { labels, values };
  }

  function renderWeatherBars(labels, values) {
    const canvas = $("weatherBarChart");
    if (!canvas || typeof Chart === "undefined") return;

    const wrap = canvas.closest(".chart-wrap") || canvas.parentElement;
    withLoading(wrap, true);

    const ctx = canvas.getContext("2d");
    if (weatherBarChart) weatherBarChart.destroy();

    weatherBarChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Temp °C",
            data: values,
            backgroundColor: "rgba(99, 102, 241, 0.22)",
            borderColor: "#6366F1",
            borderWidth: 1,
            borderRadius: 6,
            barThickness: 36,
            maxBarThickness: 42,
            categoryPercentage: 0.9,
            barPercentage: 0.9,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: chartAnimStagger(20),
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
              title: () => "Temperature",
              label: (ctx) => `${Number(ctx.raw).toFixed(1)} °C`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#6b7280", font: { size: 11 } } },
          y: { grid: { display: false }, ticks: { color: "#6b7280", font: { size: 11 } } },
        },
      },
    });

    setTimeout(() => withLoading(wrap, false), 850);
  }

  function setWeatherKpis(apiData) {
    const cur = apiData?.current_weather;
    const times = apiData?.hourly?.time || [];
    const hum = apiData?.hourly?.relativehumidity_2m || [];
    const ws = apiData?.hourly?.windspeed_10m || [];
    const wd = apiData?.hourly?.winddirection_10m || [];

    // Temperature KPI from current_weather
    if (cur && Number.isFinite(Number(cur.temperature))) {
      setText("wxTempKpi", `${Number(cur.temperature).toFixed(1)}°C`);
    } else {
      setText("wxTempKpi", "—");
    }

    // Humidity/Wind from nearest hourly
    if (times.length) {
      const i = nearestHourlyIndex(times);
      const h = Number(hum[i]);
      const w = Number(ws[i]);
      const d = Number(wd[i]);

      setText("wxHumidityKpi", Number.isFinite(h) ? `${Math.round(h)}%` : "—");
      setText("wxWindKpi", Number.isFinite(w) ? `${w.toFixed(1)} km/h` : "—");
      setText("wxWindDirKpi", degToDir(d));
    } else {
      setText("wxHumidityKpi", "—");
      setText("wxWindKpi", "—");
      setText("wxWindDirKpi", "—");
    }
  }

  async function wxLoadUsing(lat, lng, label) {
    if ($("wxLocText")) $("wxLocText").textContent = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;

    // show loading on chart area
    const wxCanvas = $("weatherBarChart");
    if (wxCanvas) {
      const wrap = wxCanvas.closest(".chart-wrap") || wxCanvas.parentElement;
      withLoading(wrap, true);
    }

    try {
      const apiData = await wxFetchForecast(lat, lng);
      setWeatherKpis(apiData);

      const { labels, values } = extractNext12Hours(apiData);
      if (labels.length && values.length) renderWeatherBars(labels, values);

      // ensure loading removed if chart didn't render
      if (wxCanvas) {
        const wrap = wxCanvas.closest(".chart-wrap") || wxCanvas.parentElement;
        setTimeout(() => withLoading(wrap, false), 900);
      }
    } catch (e) {
      console.error("Weather fetch failed:", e);
      setText("wxTempKpi", "—");
      setText("wxHumidityKpi", "—");
      setText("wxWindKpi", "—");
      setText("wxWindDirKpi", "—");
      if ($("wxLocText")) $("wxLocText").textContent = "Weather failed to load";
      if (wxCanvas) {
        const wrap = wxCanvas.closest(".chart-wrap") || wxCanvas.parentElement;
        withLoading(wrap, false);
      }
    }
  }

  async function loadWeatherAll() {
    // Weather tab is active by default. But still ensure canvas is visible.
    const weatherPanel = $("tab-weather");
    if (weatherPanel) await waitForVisible(weatherPanel, 2500);

    const live = wxGetSavedCoords();
    if (live) return wxLoadUsing(live.lat, live.lng, "Live location");

    const dash = wxGetDashboardCoords();
    if (dash) {
      const label = (dash.address || "").trim() || `${dash.lat.toFixed(4)}, ${dash.lng.toFixed(4)}`;
      return wxLoadUsing(dash.lat, dash.lng, label);
    }

    // No coords found -> keep UI clean
    setText("wxTempKpi", "—");
    setText("wxHumidityKpi", "—");
    setText("wxWindKpi", "—");
    setText("wxWindDirKpi", "—");
    if ($("wxLocText")) $("wxLocText").textContent = "Location not available";
  }

  async function requestLiveLocationAndLoad() {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported in this browser.");
      return;
    }

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
        wxLoadUsing(lat, lng, "Live location");
      },
      (err) => {
        console.warn("Geolocation denied/failed:", err);
        wxCloseModal();
        loadWeatherAll();
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
      useMyLocBtn.addEventListener("click", wxOpenModal);
    }

    const refreshBtn = $("weatherRefreshBtn");
    if (refreshBtn && !refreshBtn.__bound) {
      refreshBtn.__bound = true;
      refreshBtn.addEventListener("click", loadWeatherAll);
    }
  }

  /* -------------------------------------------------------
     Leaflet Crop Status Map (same as before)
  ------------------------------------------------------- */
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
      const hint = $("mapHint");
      if (hint) hint.style.display = "block";
      return;
    } else {
      const hint = $("mapHint");
      if (hint) hint.style.display = "none";
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

      polygon.bindPopup(`
        <div style="font-size:13px;">
          <strong>${escapeHtml(farm.cropType || "Crop")}</strong><br/>
          Crop ID: ${escapeHtml(farm.crop_id || "-")}<br/>
          Area: ${escapeHtml(farm.area_size || "-")} acres<br/>
          Planted: ${escapeHtml(farm.date_planted || "-")}
        </div>
      `);

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

  // keep compatibility
  window.initFarmMap = function initFarmMap() {};

  /* -------------------------------------------------------
     BOOT
  ------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", async () => {
  setActiveTab("weather");

  initSoilChart();
  initSoilSelectors();
  initOrderDonut();

  // ✅ warehouse + manufacturer
  initWarehousePie();
  initManufacturerPie();

  initDateFilters();
  initWeatherUI();

  // ✅ weather
  loadWeatherAll();

  // ✅ recalc empty states FIRST
  try {
    if (typeof window.applyDashboardEmptyStates === "function") {
      window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
    }
  } catch (e) {}

  // ✅ then shipment bars (so container is visible correctly)
  await renderShipmentBars();
});

})();
