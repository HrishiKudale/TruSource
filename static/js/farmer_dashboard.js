(function () {
  // ============================================================
  // STATE
  // ============================================================
  const $ = (id) => document.getElementById(id);
  let data = window.__DASHBOARD__ || {};

  // ============================================================
  // HELPERS
  // ============================================================
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

  function cap(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  function toDate(val) {
    if (!val) return null;
    if (val instanceof Date) return val;
    const d = new Date(val);
    return Number.isFinite(d.getTime()) ? d : null;
  }

  function fmtDate(d) {
    if (!d) return "-";
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  function withinTill(itemDate, selectedDate) {
    if (!selectedDate) return true;
    const d1 = toDate(itemDate);
    const d2 = toDate(selectedDate);
    if (!d1 || !d2) return true;
    d2.setHours(23, 59, 59, 999);
    return d1.getTime() <= d2.getTime();
  }


  function raf2(cb) {
  requestAnimationFrame(() => requestAnimationFrame(cb));
}

// Chart.js: nice staggered animation
function chartAnimStagger(delayBase = 45) {
  return {
    duration: 900,
    easing: "easeOutQuart",
    delay: (ctx) => {
      // ctx.type can be "data" for dataset items
      if (ctx.type === "data") return ctx.dataIndex * delayBase;
      return 0;
    },
  };
}

// Render charts only when canvas is visible (fixes “chart not loading” if hidden/0 size)
function whenCanvasReady(canvas, timeoutMs = 2500) {
  return new Promise((resolve) => {
    if (!canvas) return resolve(false);

    const start = Date.now();
    const tick = () => {
      const rect = canvas.getBoundingClientRect();
      const ok = rect.width > 20 && rect.height > 20 && canvas.offsetParent !== null;
      if (ok) return resolve(true);
      if (Date.now() - start > timeoutMs) return resolve(false);
      raf2(tick);
    };
    tick();
  });
}

  // ============================================================
  // TABS (Soil / Weather / Status)
  // ============================================================
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

  function getActiveTabKey() {
    const active = document.querySelector(".seg-btn.active");
    return active?.dataset?.tab || "soil";
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
        // Build weather UI once (inject KPI+Chart) then load
        ensureWeatherUIInjected();
        requestAnimationFrame(() => loadWeatherPanel().catch(console.error));
      }
    });
  });

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

  // ============================================================
  // CHARTS (Chart.js)
  // ============================================================
  let soilChart = null;
  let orderChart = null;
  let shipChart = null;
  let weatherChart = null;
  let whPie = null;
  let mfgPie = null;

  // ---------- SOIL LINE (WITH GRADIENT) ----------
  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas || typeof Chart === "undefined") return;

    const ctx = canvas.getContext("2d");
    const labels = data?.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data?.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

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
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#6b7280", font: { size: 11 } } },
          y: { grid: { display: false }, ticks: { display: false } },
        },
      },
    });
  }

  // ---------- ORDER DONUT ----------
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

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In transit", "Completed", "Payment Received"],
        datasets: [
          {
            data: values,
            borderWidth: 0,
            backgroundColor: ["#FDE68A", "#60A5FA", "#86EFAC", "#C4B5FD"],
            borderRadius: 10,
            spacing: 2,
          },
        ],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } },
      },
    });
  }

  // ---------- SHIPMENT HORIZONTAL BAR (fix gaps + radius) ----------
async function initShipBars() {
  if (typeof Chart === "undefined") return;

  // ✅ fallback ids (one of these must exist)
  const canvas =
    $("shipBarChart") ||
    $("shipmentBarChart") ||
    $("shipmentsBarChart") ||
    $("shipOverviewChart");

  if (!canvas) return;

  // ✅ wait for layout to be ready (prevents blank chart)
  await whenCanvasReady(canvas, 2500);

  const ctx = canvas.getContext("2d");
  const s = data.shipments || {};

  const values = [
    safeNum(s.requested),
    safeNum(s.pending),
    safeNum(s.in_transit),
    safeNum(s.delivered),
    safeNum(s.payment),
  ];

  if ($("sRequested")) $("sRequested").textContent = String(values[0]);
  if ($("sPending")) $("sPending").textContent = String(values[1]);
  if ($("sInTransit")) $("sInTransit").textContent = String(values[2]);
  if ($("sDelivered")) $("sDelivered").textContent = String(values[3]);
  if ($("sPayment")) $("sPayment").textContent = String(values[4]);

  if (shipChart) shipChart.destroy();

  shipChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Requested", "Pending", "In transit", "Delivered", "Payment"],
      datasets: [
        {
          data: values,
          backgroundColor: ["#FDE68A", "#FCD34D", "#60A5FA", "#86EFAC", "#C4B5FD"],
          borderWidth: 0,
          borderRadius: 8,
          barThickness: 16,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      animation: chartAnimStagger(55),
      layout: { padding: { left: 2, right: 8, top: 0, bottom: 0 } },
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


  // ============================================================
  // RIGHT SIDE: MANUFACTURER + WAREHOUSE PIE CHARTS (AUTO INJECT)
  // Uses dashboard.warehouse_requests / dashboard.manufacturer_requests
  // ============================================================
  function countStatuses(list) {
    const out = {};
    (list || []).forEach((it) => {
      const s = String(it?.status || "").toLowerCase().trim();
      if (!s) return;
      out[s] = (out[s] || 0) + 1;
    });
    return out;
  }

  function ensureRightPieInjected(cardId, wrapId, canvasId, legendId) {
    const card = $(cardId);
    if (!card) return;

    // insert into .card-body
    const body = card.querySelector(".card-body") || card;
    let wrap = $(wrapId);

    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = wrapId;
      wrap.style.display = "none";
      wrap.style.padding = "8px 10px 14px";
      wrap.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:center; padding:6px 0 2px;">
          <canvas id="${canvasId}" width="180" height="180"></canvas>
        </div>
        <div id="${legendId}" style="margin-top:10px; display:grid; gap:8px;"></div>
      `;
      body.appendChild(wrap);
    }
  }

  function renderPieLegend(legendEl, items) {
    if (!legendEl) return;
    legendEl.innerHTML = items
      .map(
        (it) => `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; font-size:12px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="width:10px;height:10px;border-radius:999px;background:${it.color};display:inline-block;"></span>
          <span style="color:#111827;font-weight:600;">${escapeHtml(it.label)}</span>
        </div>
        <span style="color:#6b7280;font-weight:700;">${it.value}</span>
      </div>
    `
      )
      .join("");
  }

  function initWarehousePie() {
    if (typeof Chart === "undefined") return;

    ensureRightPieInjected("warehouseCard", "warehousePieWrap", "warehousePieChart", "warehousePieLegend");
    const wrap = $("warehousePieWrap");
    const canvas = $("warehousePieChart");
    const legend = $("warehousePieLegend");
    const empty = $("emptyWarehouseCard");

    const counts = countStatuses(data.warehouse_requests);
    const requested = safeNum(counts.requested || counts["create storage shipment"] || 0);
    const stored = safeNum(counts.stored || 0);
    const pending = safeNum(counts["pending payment"] || counts.pending_payment || counts.pending || 0);
    const total = requested + stored + pending;

    if (!canvas) return;

    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (empty) empty.style.display = "flex";
      return;
    }

    if (empty) empty.style.display = "none";
    if (wrap) wrap.style.display = "block";

    const ctx = canvas.getContext("2d");
    if (whPie) whPie.destroy();

    whPie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Stored", "Pending payment"],
        datasets: [
          {
            data: [requested, stored, pending],
            borderWidth: 0,
            backgroundColor: ["#FDE68A", "#6366F1", "#60A5FA"],
          },
        ],
      },
      options: { plugins: { legend: { display: false } } },
    });

    renderPieLegend(legend, [
      { label: "Requested", value: requested, color: "#FDE68A" },
      { label: "Stored", value: stored, color: "#6366F1" },
      { label: "Pending payment", value: pending, color: "#60A5FA" },
    ]);
  }

function initWarehousePie() {
  if (typeof Chart === "undefined") return;

  ensureRightPieInjected("warehouseCard", "warehousePieWrap", "warehousePieChart", "warehousePieLegend");
  const wrap = $("warehousePieWrap");
  const canvas = $("warehousePieChart");
  const legend = $("warehousePieLegend");
  const empty = $("emptyWarehouseCard");

  const counts = countStatuses(data.warehouse_requests);

  const requested = safeNum(counts.requested || counts["create storage shipment"] || 0);
  const stored = safeNum(counts.stored || 0);
  const pending = safeNum(counts["pending payment"] || counts.pending_payment || counts.pending || 0);
  const total = requested + stored + pending;

  // ✅ Populate numbers if your HTML has these IDs
  if ($("whRequested")) $("whRequested").textContent = String(requested);
  if ($("whStored")) $("whStored").textContent = String(stored);
  if ($("whPendingPay")) $("whPendingPay").textContent = String(pending);

  if (!canvas) return;

  if (total <= 0) {
    if (wrap) wrap.style.display = "none";
    if (empty) empty.style.display = "flex";
    return;
  }

  if (empty) empty.style.display = "none";
  if (wrap) wrap.style.display = "block";

  const ctx = canvas.getContext("2d");
  if (whPie) whPie.destroy();

  whPie = new Chart(ctx, {
    type: "pie",
    data: {
      labels: ["Requested", "Stored", "Pending payment"],
      datasets: [
        {
          data: [requested, stored, pending],
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

  renderPieLegend(legend, [
    { label: "Requested", value: requested, color: "#FDE68A" },
    { label: "Stored", value: stored, color: "#6366F1" },
    { label: "Pending payment", value: pending, color: "#60A5FA" },
  ]);
}


  // ============================================================
  // LISTS (Pending Tasks / Warehouse List / Manufacturer List)
  // (kept working; charts are separate)
  // ============================================================
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

      // toggle empty states based on dashboard data
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

  // ============================================================
  // SOIL SELECTOR (updates soilChart dataset + keeps gradient)
  // ============================================================
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

  // ============================================================
  // WEATHER (KPI + BAR CHART) - INJECT INTO EXISTING WEATHER TAB
  // ============================================================
  function wxWindDirText(deg) {
    const d = Number(deg);
    if (!Number.isFinite(d)) return "—";
    const dirs = ["North", "North East", "East", "South East", "South", "South West", "West", "North West"];
    return dirs[Math.round(d / 45) % 8];
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
    if (Number.isFinite(lat) && Number.isFinite(lng)) return { lat, lng, address: geo?.address || "" };
    return null;
  }

  async function wxFetchForecast(lat, lng) {
    const url =
      `https://api.open-meteo.com/v1/forecast` +
      `?latitude=${encodeURIComponent(lat)}` +
      `&longitude=${encodeURIComponent(lng)}` +
      `&current_weather=true` +
      `&hourly=temperature_2m,relative_humidity_2m` +
      `&forecast_days=2` +
      `&timezone=auto`;

    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`Weather API failed (${res.status})`);
    return res.json();
  }

  function buildHourlySeries(apiData) {
    const times = apiData?.hourly?.time || [];
    const temps = apiData?.hourly?.temperature_2m || [];
    if (!times.length || !temps.length) return { labels: [], values: [], startIdx: 0 };

    const now = new Date();
    let startIdx = 0;
    for (let i = 0; i < times.length; i++) {
      const t = new Date(times[i]);
      if (t.getTime() >= now.getTime()) {
        startIdx = i;
        break;
      }
    }

    const labels = [];
    const values = [];
    for (let k = 0; k < 12; k++) {
      const i = startIdx + k;
      if (!times[i]) break;
      const d = new Date(times[i]);
      labels.push(d.toLocaleTimeString([], { hour: "numeric" }).replace(" ", ""));
      values.push(Number(temps[i] ?? 0));
    }

    return { labels, values, startIdx };
  }

  function pickHumidity(apiData, idx) {
    const hum = apiData?.hourly?.relative_humidity_2m || [];
    const v = hum[idx] ?? hum[0];
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function ensureWeatherUIInjected() {
    const panel = $("tab-weather");
    if (!panel) return;

    // already injected?
    if ($("wxKpiRow") && $("weatherBarChart")) return;

    // Put UI after "Location: ..." line if present
    const locLine = panel.querySelector(".muted");
    const anchor = locLine ? locLine.parentElement : panel;

    const wrap = document.createElement("div");
    wrap.id = "wxKpiRow";
    wrap.style.marginTop = "12px";
    wrap.innerHTML = `
    `;

    // Insert wrap at the top of weather content
    if (anchor) {
      // insert after locLine if exists, else just append
      if (locLine && locLine.nextSibling) {
        locLine.parentElement.insertBefore(wrap, locLine.nextSibling);
      } else {
        anchor.appendChild(wrap);
      }
    } else {
      panel.appendChild(wrap);
    }
  }

  function ensureWeatherChart(labels, values) {
    const canvas = $("weatherBarChart");
    if (!canvas || typeof Chart === "undefined") return;
    const ctx = canvas.getContext("2d");

    if (weatherChart) weatherChart.destroy();

    weatherChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Temperature",
            data: values,
            backgroundColor: "rgba(99,102,241,0.22)",
            borderColor: "#6366F1",
            borderWidth: 2,
            borderRadius: 6,        // ✅ not too round
            categoryPercentage: 0.98, // ✅ removes huge gaps
            barPercentage: 0.92,
            maxBarThickness: 28,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
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
          x: {
            grid: { display: false },
            ticks: { color: "#6b7280", font: { size: 11 } },
          },
          y: {
            grid: { display: false },
            ticks: { display: false },
          },
        },
      },
    });
  }

  async function loadWeatherUsing(lat, lng, label) {
    if ($("wxLocText")) $("wxLocText").textContent = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;

    // KPI placeholders
    if ($("wxTempKpi")) $("wxTempKpi").textContent = "—";
    if ($("wxHumidityKpi")) $("wxHumidityKpi").textContent = "—";
    if ($("wxWindKpi")) $("wxWindKpi").textContent = "—";
    if ($("wxWindDirKpi")) $("wxWindDirKpi").textContent = "—";

    const apiData = await wxFetchForecast(lat, lng);
    const cur = apiData?.current_weather || {};

    const t = Number(cur.temperature);
    const ws = Number(cur.windspeed);
    const wd = Number(cur.winddirection);

    const { labels: xlabels, values, startIdx } = buildHourlySeries(apiData);
    const hum = pickHumidity(apiData, startIdx);

    if ($("wxTempKpi")) $("wxTempKpi").textContent = Number.isFinite(t) ? `${t.toFixed(1)}°C` : "—";
    if ($("wxHumidityKpi")) $("wxHumidityKpi").textContent = hum != null ? `${hum.toFixed(0)}` : "—";
    if ($("wxWindKpi")) $("wxWindKpi").textContent = Number.isFinite(ws) ? `${ws.toFixed(1)} km/h` : "—";
    if ($("wxWindDirKpi")) $("wxWindDirKpi").textContent = wxWindDirText(wd);

    ensureWeatherChart(xlabels, values);
  }

  function wxOpenModal() {
    const m = $("wxLocModal");
    if (m) m.style.display = "block";
  }
  function wxCloseModal() {
    const m = $("wxLocModal");
    if (m) m.style.display = "none";
  }

  async function requestLiveLocationAndLoad() {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported in this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos?.coords?.latitude);
        const lng = Number(pos?.coords?.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          wxCloseModal();
          return;
        }
        wxSaveCoords(lat, lng);
        wxCloseModal();
        await loadWeatherUsing(lat, lng, "Live location");
      },
      async () => {
        wxCloseModal();
        await loadWeatherPanel();
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 600000 }
    );
  }

  async function loadWeatherPanel() {
    const live = wxGetSavedCoords();
    if (live) {
      await loadWeatherUsing(live.lat, live.lng, "Live location");
      return;
    }

    const dash = wxGetDashboardCoords();
    if (dash) {
      const label = (dash.address || "").trim() || `${dash.lat.toFixed(4)}, ${dash.lng.toFixed(4)}`;
      await loadWeatherUsing(dash.lat, dash.lng, label);
      return;
    }
  }

  function initWeatherUI() {
    // modal close
    const modal = $("wxLocModal");
    if (modal && !modal.__bound) {
      modal.__bound = true;
      modal.addEventListener("click", (e) => {
        const t = e.target;
        if (t && t.getAttribute && t.getAttribute("data-close") === "1") wxCloseModal();
      });
    }

    // allow button
    const allowBtn = $("wxAllowBtn");
    if (allowBtn && !allowBtn.__bound) {
      allowBtn.__bound = true;
      allowBtn.addEventListener("click", requestLiveLocationAndLoad);
    }

    // use my location + refresh
    const useMyLocBtn = $("weatherUseMyLocationBtn");
    if (useMyLocBtn && !useMyLocBtn.__bound) {
      useMyLocBtn.__bound = true;
      useMyLocBtn.addEventListener("click", () => wxOpenModal());
    }

    const refreshBtn = $("weatherRefreshBtn");
    if (refreshBtn && !refreshBtn.__bound) {
      refreshBtn.__bound = true;
      refreshBtn.addEventListener("click", () => loadWeatherPanel().catch(console.error));
    }
  }

  // ============================================================
  // LEAFLET MAP (Status tab) - unchanged behavior
  // ============================================================
  let dashboardLeafletMap = null;
  let dashboardPolygonLayers = [];

  function isLeafletReady() {
    return typeof L !== "undefined";
  }

  function waitForVisible(el, timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      const t = setInterval(() => {
        const style = el ? getComputedStyle(el) : null;
        const visible =
          !!el &&
          style &&
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          el.offsetWidth > 0 &&
          el.offsetHeight > 0 &&
          el.offsetParent !== null;

        if (visible) {
          clearInterval(t);
          resolve(true);
        } else if (Date.now() - start > timeoutMs) {
          clearInterval(t);
          reject(new Error("Map container never became visible"));
        }
      }, 120);
    });
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

  window.initFarmMap = function initFarmMap() {
    // compatibility; map renders only when status tab clicked
  };

  // ============================================================
  // BOOT
  // ============================================================
  document.addEventListener("DOMContentLoaded", () => {
    // Keep whatever tab HTML marks active by default
    const activeTab = getActiveTabKey();

    initSoilChart();
    initOrderDonut();
    initShipBars();

    initDateFilters();
    initSoilSelectors();

    // Right card pies (uses list data, no extra API)
    initWarehousePie();
    initManufacturerPie();

    // Weather only if user opens it OR it's active already
    initWeatherUI();
    if (activeTab === "weather") {
      ensureWeatherUIInjected();
      requestAnimationFrame(() => loadWeatherPanel().catch(console.error));
    }

    // run empty-state checks (your existing helper)
    try {
      if (typeof window.applyDashboardEmptyStates === "function") {
        window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
      }
    } catch (e) {}
  });

})();
