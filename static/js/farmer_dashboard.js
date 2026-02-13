(function () {
  const data = window.__DASHBOARD__ || {};
  const $ = (id) => document.getElementById(id);

  // ---------------------------
  // Helpers
  // ---------------------------
  function safeNum(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : 0;
  }

  function toDate(val) {
    if (!val) return null;
    const d = new Date(val);
    return isNaN(d.getTime()) ? null : d;
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

  // ---------------------------
  // Tabs (Soil / Weather / Status)
  // ---------------------------
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
        requestAnimationFrame(() => loadWeatherPanel());
      }
    });
  });

  // crop type change -> refresh polygons only if status tab is active
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

  // ---------------------------
  // Charts
  // ---------------------------
  let soilChart = null;
  let orderChart = null;
  let weatherChart = null;
  let warehousePie = null;
  let mfgPie = null;

function initSoilChart() {
  const canvas = $("soilLineChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const labels = data.soil?.labels || ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  const points = data.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

  // ✅ Gradient fill like your previous code
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
          fill: true,                 // ✅ important
          borderColor: "#7C3AED",
          backgroundColor: gradient,   // ✅ gradient
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
        x: { grid: { display: false } },
        y: { grid: { display: false }, ticks: { display: false } },
      },
    },
  });
}


  function initOrderDonut() {
    const canvas = $("orderDonutChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const o = data.orders || {};
    const values = [
      safeNum(o.requested),
      safeNum(o.in_transit),
      safeNum(o.completed),
      safeNum(o.payment_received),
    ];

    const total = values.reduce((a, b) => a + b, 0);
    $("orderTotal").textContent = String(total);
    $("oRequested").textContent = String(values[0]);
    $("oInTransit").textContent = String(values[1]);
    $("oCompleted").textContent = String(values[2]);
    $("oPaid").textContent = String(values[3]);

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In transit", "Completed", "Payment Received"],
        datasets: [{
          data: values,
          borderWidth: 0,
          backgroundColor: ["#ead8b1", "#86b7ff", "#bff3c7", "#c9c3ff"],
        }],
      },
      options: {
        cutout: "70%",
        plugins: { legend: { display: false } },
      },
    });
  }

  function renderShipmentBars() {
    const s = data.shipments || {};
    const values = {
      requested: safeNum(s.requested),
      pending: safeNum(s.pending),
      in_transit: safeNum(s.in_transit),
      delivered: safeNum(s.delivered),
      payment: safeNum(s.payment),
    };

    $("sRequested").textContent = String(values.requested);
    $("sPending").textContent = String(values.pending);
    $("sInTransit").textContent = String(values.in_transit);
    $("sDelivered").textContent = String(values.delivered);
    $("sPayment").textContent = String(values.payment);

    const max = Math.max(1, values.requested, values.pending, values.in_transit, values.delivered, values.payment);

    const rows = [
      { key: "requested", label: "Requested", cls: "req" },
      { key: "pending", label: "Pending", cls: "pending" },
      { key: "in_transit", label: "In transit", cls: "transit" },
      { key: "delivered", label: "Delivered", cls: "del" },
      { key: "payment", label: "Payment", cls: "pay" },
    ];

    const container = $("shipBars");
    if (!container) return;
    container.innerHTML = rows.map(r => {
      const v = values[r.key];
      const pct = Math.round((v / max) * 100);
      return `
        <div class="ship-row">
          <div class="ship-label">${r.label}</div>
          <div class="ship-track">
            <div class="ship-fill ${r.cls}" style="width:${pct}%"></div>
          </div>
        </div>
      `;
    }).join("");
  }

  function countByStatus(items, statusKey = "status") {
    const out = {};
    (items || []).forEach((it) => {
      const s = String(it?.[statusKey] || "").toLowerCase().trim();
      if (!s) return;
      out[s] = (out[s] || 0) + 1;
    });
    return out;
  }

  function initWarehousePie() {
    // Prefer summary object if backend provides
    const w = data.warehouse || data.warehouse_summary || null;

    // Or derive from list
    const fromList = countByStatus(data.warehouse_requests);

    const requested = safeNum(w?.requested ?? fromList.requested ?? 0);
    const stored = safeNum(w?.stored ?? fromList.stored ?? 0);
    const pendingPay = safeNum(w?.pending_payment ?? fromList["pending payment"] ?? fromList.pending_payment ?? 0);

    const total = requested + stored + pendingPay;

    const emptyEl = $("emptyWarehouseCard");
    const wrap = $("warehousePieWrap");

    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "flex";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";
    if (wrap) wrap.style.display = "block";

    $("whRequested").textContent = String(requested);
    $("whStored").textContent = String(stored);
    $("whPendingPay").textContent = String(pendingPay);

    const canvas = $("warehousePieChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (warehousePie) warehousePie.destroy();

    warehousePie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Stored", "Pending payment"],
        datasets: [{
          data: [requested, stored, pendingPay],
          borderWidth: 0,
          backgroundColor: ["#fde68a", "#6366f1", "#60a5fa"],
        }],
      },
      options: { plugins: { legend: { display: false } } },
    });
  }

  function initManufacturerPie() {
    const m = data.manufacturer || data.manufacturer_summary || null;
    const fromList = countByStatus(data.manufacturer_requests);

    const requested = safeNum(m?.requested ?? fromList.requested ?? 0);
    const processing = safeNum(m?.processing ?? fromList.processing ?? 0);
    const pendingPay = safeNum(m?.pending_payment ?? fromList["pending payment"] ?? fromList.pending_payment ?? 0);

    const total = requested + processing + pendingPay;

    const emptyEl = $("emptyManufacturerCard");
    const wrap = $("mfgPieWrap");

    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "flex";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";
    if (wrap) wrap.style.display = "block";

    $("mfgRequested").textContent = String(requested);
    $("mfgProcessing").textContent = String(processing);
    $("mfgPendingPay").textContent = String(pendingPay);

    const canvas = $("mfgPieChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (mfgPie) mfgPie.destroy();

    mfgPie = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Requested", "Processing", "Pending payment"],
        datasets: [{
          data: [requested, processing, pendingPay],
          borderWidth: 0,
          backgroundColor: ["#60a5fa", "#f59e0b", "#6366f1"],
        }],
      },
      options: { plugins: { legend: { display: false } } },
    });
  }


    async function refreshManufacturerDataAndRender() {
    try {
      // ✅ Use the same endpoint you were using earlier
      // Replace URL below with your actual existing one if different
      const res = await fetch("/farmer/dashboard/api/manufacturer", {
        headers: { Accept: "application/json" },
      });
      const out = await res.json();

      // Expecting: { ok:true, summary:{...} } OR { ok:true, requests:[...] }
      if (!out?.ok) return;

      // Merge into existing dashboard object so rest of logic keeps working
      if (out.summary) data.manufacturer_summary = out.summary;
      if (Array.isArray(out.requests)) data.manufacturer_requests = out.requests;

      // ✅ Re-render pie
      initManufacturerPie();

      // ✅ also re-run empty state if you use it
      try {
        if (typeof window.applyDashboardEmptyStates === "function") {
          window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
        }
      } catch (e) {}
    } catch (e) {
      console.warn("Manufacturer refresh failed:", e);
    }
  }

  // ---------------------------
  // Right lists (Pending Tasks)
  // ---------------------------
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

      el.insertAdjacentHTML(
        "beforeend",
        `
        <div class="task-item">
          <div class="task-ico" aria-hidden="true">
            <i class="mdi mdi-checkbox-blank-circle-outline"></i>
          </div>
          <div style="flex:1;">
            <div class="task-title">${escapeHtml(title)}</div>
            <div class="task-sub">${escapeHtml(sub)}</div>
            ${status ? `<div class="task-sub">${escapeHtml(cap(status))}</div>` : ""}
          </div>
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

      // Empty state for tasks (same logic you already had)
      const tasksEmpty = !(Array.isArray(data?.pending_tasks) && data.pending_tasks.length > 0);
      const emptyTasks = $("emptyTasksCard");
      if (emptyTasks) emptyTasks.style.display = tasksEmpty ? "flex" : "none";
    }

    tasksDate.addEventListener("change", refreshAll);
    warehouseDate.addEventListener("change", refreshAll);
    mfgDate.addEventListener("change", refreshAll);

    refreshAll();
  }

  // ---------------------------
  // Soil selector
  // ---------------------------
  function initSoilSelectors() {
    const metricSel = $("soilMetricSelect");
    if (!metricSel) return;

    metricSel.addEventListener("change", () => {
      const key = metricSel.value;
      const labels = data.soil?.labels || ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
      const series = data.soil?.[key] || data.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

      if (!soilChart) return;
      soilChart.data.labels = labels;
      soilChart.data.datasets[0].data = series;
      soilChart.update();
    });
  }

  // ---------------------------
  // Weather (Open-Meteo) -> screenshot layout
  // ---------------------------
  function wxWindDirText(deg) {
    const d = Number(deg);
    if (!Number.isFinite(d)) return "—";
    const dirs = ["North","North East","East","South East","South","South West","West","North West"];
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
    if (!times.length || !temps.length) return { labels: [], values: [] };

    const now = new Date();
    let startIdx = 0;
    for (let i = 0; i < times.length; i++) {
      const t = new Date(times[i]);
      if (t.getTime() >= now.getTime()) { startIdx = i; break; }
    }

    const labels = [];
    const values = [];
    for (let k = 0; k < 12; k++) {
      const i = startIdx + k;
      if (!times[i]) break;
      const d = new Date(times[i]);
      const lbl = d.toLocaleTimeString([], { hour: "numeric" }).replace(" ", "");
      labels.push(lbl);
      values.push(Number(temps[i] ?? 0));
    }
    return { labels, values, startIdx };
  }

  function pickCurrentHumidity(apiData, startIdx) {
    const hum = apiData?.hourly?.relative_humidity_2m || [];
    if (!Array.isArray(hum) || hum.length === 0) return null;
    const v = hum[startIdx] ?? hum[0];
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function ensureWeatherChart(labels, values) {
    const canvas = $("weatherBarChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (weatherChart) {
      weatherChart.data.labels = labels;
      weatherChart.data.datasets[0].data = values;
      weatherChart.update();
      return;
    }

    weatherChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Temperature",
          data: values,
          backgroundColor: "rgba(99,102,241,0.20)",
          borderColor: "#6366F1",
          borderWidth: 2,
          borderRadius: 10,

          // ✅ Make bars thicker
          barThickness: 34,
          maxBarThickness: 40,
          categoryPercentage: 0.9,
          barPercentage: 0.9,
        }],
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
              title: (ctx) => "Temperature",
              label: (ctx) => `${Number(ctx.raw).toFixed(1)} °C`,
            },
          },
        },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: "#6b7280", font: { size: 11 } },
              offset: true
            },
            y: {
              grid: { display: false },
              ticks: { color: "#6b7280", font: { size: 11 } },
            },
          },
      },
    });
  }

  async function loadWeatherUsing(lat, lng, label) {
    if ($("wxLocText")) $("wxLocText").textContent = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;

    // skeleton values
    if ($("wxTempKpi")) $("wxTempKpi").textContent = "—";
    if ($("wxHumidityKpi")) $("wxHumidityKpi").textContent = "—";
    if ($("wxWindKpi")) $("wxWindKpi").textContent = "—";
    if ($("wxWindDirKpi")) $("wxWindDirKpi").textContent = "—";

    const apiData = await wxFetchForecast(lat, lng);

    // KPIs
    const cur = apiData?.current_weather || {};
    const t = Number(cur.temperature);
    const ws = Number(cur.windspeed);
    const wd = Number(cur.winddirection);

    const { labels, values, startIdx } = buildHourlySeries(apiData);
    const hum = pickCurrentHumidity(apiData, startIdx);

    if ($("wxTempKpi")) $("wxTempKpi").textContent = Number.isFinite(t) ? `${t.toFixed(1)}°C` : "—";
    if ($("wxHumidityKpi")) $("wxHumidityKpi").textContent = (hum != null) ? `${hum.toFixed(0)}` : "—";
    if ($("wxWindKpi")) $("wxWindKpi").textContent = Number.isFinite(ws) ? `${ws.toFixed(1)} km/h` : "—";
    if ($("wxWindDirKpi")) $("wxWindDirKpi").textContent = wxWindDirText(wd);

    ensureWeatherChart(labels, values);
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
        try {
          await loadWeatherUsing(lat, lng, "Live location");
        } catch (e) {
          console.error("Weather error:", e);
        }
      },
      (err) => {
        console.warn("Geolocation denied/failed:", err);
        wxCloseModal();
        loadWeatherPanel();
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 600000 }
    );
  }

  async function loadWeatherPanel() {
    try {
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

      if ($("wxLocText")) $("wxLocText").textContent = "—";
    } catch (e) {
      console.error("Weather load failed:", e);
    }
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
      refreshBtn.addEventListener("click", () => loadWeatherPanel());
    }

    // active by default in HTML
    requestAnimationFrame(() => loadWeatherPanel());
  }

  // ---------------------------
  // Boot
  // ---------------------------
  document.addEventListener("DOMContentLoaded", () => {
    // Default tab = weather (screenshot)
    setActiveTab("weather");

    initSoilChart();
    initOrderDonut();
    renderShipmentBars();

    initWarehousePie();
    initManufacturerPie();
    refreshManufacturerDataAndRender(); // ✅ ensures chart appears like before

    initDateFilters();
    initSoilSelectors();
    initWeatherUI();

    // trigger empty-state recalculation
    try {
      if (typeof window.applyDashboardEmptyStates === "function") {
        window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
      }
    } catch (e) {}
  });

  // ---------------------------
  // Leaflet Crop Status Map (your existing logic kept)
  // ---------------------------
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
      try { dashboardLeafletMap.removeLayer(layer); } catch (e) {}
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
      try { map.invalidateSize(); } catch (e) {}
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
      try { dashboardLeafletMap.invalidateSize(); } catch (e) {}
    }, 80);

    await loadAndRenderFarmsLeaflet();
  }

  window.initFarmMap = function initFarmMap() {
    // keep compatibility
  };
})();
