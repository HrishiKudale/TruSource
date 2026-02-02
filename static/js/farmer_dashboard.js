(function () {
  const data = window.__DASHBOARD__ || {};

  // ---------- Helpers ----------
  const $ = (id) => document.getElementById(id);

  function toDate(val) {
    if (!val) return null;
    if (val instanceof Date) return val;
    const d = new Date(val);
    return isNaN(d.getTime()) ? null : d;
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

  function safeNum(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : 0;
  }

  // ---------- Tabs (Soil / Weather / Status) ----------
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

  // ✅ When user opens Crop Status tab: wait for visible, then render polygons
  async function openCropStatusAndRenderMap() {
    const farmMapEl = $("farmMap");
    if (!farmMapEl) return;

    // Make sure Status tab is actually active (otherwise height may be 0)
    setActiveTab("status");

    // Wait for tab panel to become visible
    await waitForVisible(farmMapEl, 8000);

    // Init leaflet map (only when visible)
    await ensureLeafletMapInitialized();

    // Refresh size (critical when map was hidden)
    setTimeout(() => {
      try {
        dashboardLeafletMap.invalidateSize();
      } catch (e) {}
    }, 80);

    // Draw polygons
    await loadAndRenderFarmsLeaflet();
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      setActiveTab(tab);

    if (tab === "status") {
      openCropStatusAndRenderMap().catch((e) => console.warn("Map render failed:", e));
    }

    if (tab === "weather") {
      loadAndRenderWeather();
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

  // ---------- Charts ----------
  let soilChart, orderChart, shipChart;

  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data.soil?.soil_temp || [5.6, 5.7, 5.65, 5.9, 6.0, 6.35, 5.8];

    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, "rgba(124, 58, 237, 0.55)");
    gradient.addColorStop(0.6, "rgba(124, 58, 237, 0.20)");
    gradient.addColorStop(1, "rgba(124, 58, 237, 0.02)");

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

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In transit", "Completed", "Payment Received"],
        datasets: [{ data: values, borderWidth: 0 }],
      },
      options: { cutout: "72%", plugins: { legend: { display: false } } },
    });

    const total = values.reduce((a, b) => a + b, 0);
    $("orderTotal").textContent = String(total);
    $("oRequested").textContent = String(values[0]);
    $("oInTransit").textContent = String(values[1]);
    $("oCompleted").textContent = String(values[2]);
    $("oPaid").textContent = String(values[3]);
  }

  function initShipBars() {
    const canvas = $("shipBarChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const s = data.shipments || {};
    const values = [
      safeNum(s.requested),
      safeNum(s.pending),
      safeNum(s.in_transit),
      safeNum(s.delivered),
      safeNum(s.payment),
    ];

    shipChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Requested", "Pending", "In transit", "Delivered", "Payment"],
        datasets: [{ data: values, borderWidth: 1 }],
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { display: false } },
        },
      },
    });

    $("sRequested").textContent = String(values[0]);
    $("sPending").textContent = String(values[1]);
    $("sInTransit").textContent = String(values[2]);
    $("sDelivered").textContent = String(values[3]);
    $("sPayment").textContent = String(values[4]);
  }

  // ---------- Lists ----------
  function cap(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderList(containerId, items, selectedDate) {
    const el = $(containerId);
    if (!el) return;

    el.innerHTML = "";
    const filtered = (items || []).filter((x) => withinTill(x.due_at || x.created_at, selectedDate));

    if (!filtered.length) {
      // Leave empty - empty-state illustration will handle UI
      return;
}


    filtered.forEach((it) => {
      const title = it.title || it.task || "Task";
      const sub = it.sub || it.subtitle || it.meta || "";
      const status = (it.status || "").toLowerCase();
      const pillClass =
        status === "requested"
          ? "requested"
          : status === "approved"
          ? "approved"
          : status === "paid"
          ? "paid"
          : status === "pending"
          ? "pending"
          : status === "stored"
          ? "stored"
          : "";

      const dateLabel = fmtDate(toDate(it.due_at || it.created_at));

      el.insertAdjacentHTML(
        "beforeend",
        `
        <div class="task-item">
          <div class="task-ico" aria-hidden="true">⚙️</div>
          <div style="flex:1;">
            <div class="task-title">${escapeHtml(title)}</div>
            <div class="task-sub">${escapeHtml(sub)} ${dateLabel !== "-" ? "• " + dateLabel : ""}</div>
            ${status ? `<div class="pill ${pillClass}">${escapeHtml(cap(status))}</div>` : ""}
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

      // 🔥 Update empty states after lists are rendered (so illustrations show/hide correctly)
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

  // ---------- Boot ----------
  document.addEventListener("DOMContentLoaded", () => {
    initSoilChart();
    initOrderDonut();
    initShipBars();
    initDateFilters();
    initSoilSelectors();

    // Do not auto-init map. Only on Status tab.
  });
})();


/* =========================
   Weather Card (Open-Meteo)
   ========================= */

function getWeatherIconAndTheme(code) {
  // Web version using MDI icons + theme colors
  if ([0, 1].includes(code)) return { icon: "mdi-weather-sunny", color: "#facc15" };
  if ([2, 3].includes(code)) return { icon: "mdi-weather-partly-cloudy", color: "#94a3b8" };
  if ([45, 48].includes(code)) return { icon: "mdi-weather-fog", color: "#64748b" };
  if ([51, 53, 55, 56, 57, 61, 63, 65].includes(code)) return { icon: "mdi-weather-rainy", color: "#38bdf8" };
  if ([66, 67, 71, 73, 75, 77, 85, 86].includes(code)) return { icon: "mdi-weather-snowy", color: "#bae6fd" };
  if ([95, 96, 99].includes(code)) return { icon: "mdi-weather-lightning-rainy", color: "#fbbf24" };
  return { icon: "mdi-weather-cloudy", color: "#94a3b8" };
}

function setWeatherCardLoading() {
  const card = document.getElementById("weatherProCard");
  if (!card) return;
  card.innerHTML = `
    <div class="wcard-loading">
      <div class="wspin" aria-hidden="true"></div>
      <div class="wloading-text">Fetching weather...</div>
    </div>
  `;
}

function setWeatherCardError(msg) {
  const card = document.getElementById("weatherProCard");
  if (!card) return;
  card.innerHTML = `
    <div class="wmuted">Weather data unavailable</div>
    <div class="werror">${msg || "Unable to fetch weather right now."}</div>
  `;
}

function renderWeatherCard(weather) {
  const card = document.getElementById("weatherProCard");
  if (!card) return;

  const code = Number(weather?.code ?? 0);
  const temp = Number(weather?.temp ?? 0);
  const wind = Number(weather?.wind ?? 0);
  const rain = Number(weather?.rain ?? 0);

  const theme = getWeatherIconAndTheme(code);
  const bg = `${theme.color}33`; // alpha bg like RN

  card.innerHTML = `
    <div class="wcard-head">
      <div class="wicon-circle" style="background:${bg};">
        <i class="mdi ${theme.icon} wicon" style="color:${theme.color};"></i>
      </div>
      <div>
        <div class="wtitle">Current Weather</div>
        <div class="wsubtitle">${temp.toFixed(1)}°C • Feels like field conditions</div>
      </div>
    </div>

    <div class="wgrid">
      <div class="witem">
        <i class="mdi mdi-weather-rainy" style="color:#0ea5e9;"></i>
        <div class="wlabel">Rain</div>
        <div class="wvalue">${rain.toFixed(1)} mm</div>
      </div>

      <div class="witem">
        <i class="mdi mdi-weather-windy" style="color:#22c55e;"></i>
        <div class="wlabel">Wind</div>
        <div class="wvalue">${wind.toFixed(1)} km/h</div>
      </div>

      <div class="witem">
        <i class="mdi mdi-thermometer" style="color:#f97316;"></i>
        <div class="wlabel">Temp</div>
        <div class="wvalue">${temp.toFixed(1)}°C</div>
      </div>
    </div>
  `;
}

async function fetchOpenMeteoCurrentWeather(lat, lng) {
  // Open-Meteo current_weather=true
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lng)}&current_weather=true`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Weather API failed: ${res.status}`);
  const data = await res.json();
  const cur = data?.current_weather;

  if (!cur) return null;

  // Open-Meteo current_weather usually has temperature, windspeed, weathercode
  // precipitation may not be present in current_weather depending on API fields.
  // We'll fallback to 0 if missing.
  return {
    temp: cur.temperature ?? 0,
    wind: cur.windspeed ?? 0,
    rain: cur.precipitation ?? 0,
    code: cur.weathercode ?? 0,
  };
}

async function loadAndRenderWeather() {
  const d = window.__DASHBOARD__ || {};
  const geo = d?.geo || {};

  const lat = Number(geo?.lat);
  const lng = Number(geo?.lng);

  // fallback if dashboard geo missing
  const latOk = Number.isFinite(lat);
  const lngOk = Number.isFinite(lng);

  if (!latOk || !lngOk) {
    setWeatherCardError("No geo-location found. Please add a farm or enable location for your crop.");
    return;
  }

  setWeatherCardLoading();

  try {
    const w = await fetchOpenMeteoCurrentWeather(lat, lng);
    if (!w) {
      setWeatherCardError("Weather data not available for this location.");
      return;
    }
    renderWeatherCard(w);
  } catch (e) {
    console.error("Weather fetch failed:", e);
    setWeatherCardError(e?.message || "Weather fetch failed.");
  }
}



/* ================================
   Leaflet Farm Map + Polygons (Dashboard)
   ================================ */

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

  const el = document.getElementById("farmMap");
  if (!el) return null;

  await waitForVisible(el, 8000);

  // Wait until Leaflet script loads (defer)
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

  window.dashboardLeafletMap = dashboardLeafletMap; // debug

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

  // Fix size after hidden->visible
  setTimeout(() => {
    try {
      map.invalidateSize();
    } catch (e) {}
  }, 60);

  const cropTypeSelect = document.getElementById("cropTypeSelect");
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
        <strong>${farm.cropType || "Crop"}</strong><br/>
        Crop ID: ${farm.crop_id || "-"}<br/>
        Area: ${farm.area_size || "-"} acres<br/>
        Planted: ${farm.date_planted || "-"}
      </div>
    `;

    polygon.bindPopup(infoHtml);

    coords.forEach((c) => allBounds.push(c));
  });

  if (allBounds.length) {
    map.fitBounds(allBounds, { padding: [20, 20] });
  }
}

/**
 * Keeping this so your existing HTML callback won't break
 * (even if you removed Google Maps script, no issue)
 */
window.initFarmMap = function initFarmMap() {
  // For Leaflet dashboard we do nothing here.
  // Rendering will happen when user opens Status tab.
};
