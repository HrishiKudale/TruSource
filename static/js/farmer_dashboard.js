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

  function isStatusTabActive() {
    const statusPanel = $("tab-status");
    return !!(statusPanel && statusPanel.classList.contains("active"));
  }

  // ✅ Called when user opens "Crop Status" tab
  function openCropStatusAndRenderMap() {
    // Ensure panel is visible (your HTML already keeps it visible, but safe)
    const cropStatusPanel = $("cropStatusPanel");
    if (cropStatusPanel) cropStatusPanel.style.display = "block";

    // Wait for the tab to be displayed (layout must exist)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        // Ask map module to init+render (global function defined below)
        if (typeof window.openDashboardStatusMap === "function") {
          window.openDashboardStatusMap();
        }
      });
    });
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const tab = btn.dataset.tab;
      Object.keys(panels).forEach((k) => panels[k].classList.toggle("active", k === tab));

      if (tab === "status") {
        openCropStatusAndRenderMap();
      }
    });
  });

  // crop type change -> refresh polygons only if status tab is active
  document.addEventListener("DOMContentLoaded", () => {
    const cropTypeSelect = $("cropTypeSelect");
    if (cropTypeSelect) {
      cropTypeSelect.addEventListener("change", () => {
        if (isStatusTabActive()) {
          openCropStatusAndRenderMap();
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
      el.innerHTML = `<div class="muted small" style="padding:10px;">No items</div>`;
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

    // If user refreshes while Status tab is already active
    if (isStatusTabActive()) openCropStatusAndRenderMap();
  });
})();
/* ================================
   Dashboard Map + Polygons (FINAL FIX)
   ================================ */

// IMPORTANT: <div id="farmMap"> creates window.farmMap (HTMLDivElement).
// Never use variable name "farmMap" in JS.
let dashboardFarmMap = null;
let farmPolygons = [];
let mapInitializedOnce = false;

function isMapsReady() {
  return !!window.__MAPS_READY__ && typeof google !== "undefined" && !!google.maps;
}

function clearFarmPolygons() {
  farmPolygons.forEach((p) => p.setMap(null));
  farmPolygons = [];
}

function ensureMapInitialized() {
  if (dashboardFarmMap || !isMapsReady()) return;

  const el = document.getElementById("farmMap");
  if (!el) {
    console.warn("❌ #farmMap element not found");
    return;
  }

  dashboardFarmMap = new google.maps.Map(el, {
    center: { lat: 20.5937, lng: 78.9629 },
    zoom: 5,
    mapTypeId: "roadmap",
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
  });

  mapInitializedOnce = true;
}

function forceMapResize() {
  if (!dashboardFarmMap || !google?.maps?.event) return;
  setTimeout(() => {
    google.maps.event.trigger(dashboardFarmMap, "resize");
  }, 100);
}

function fitPolygons() {
  if (!dashboardFarmMap || !isMapsReady()) return;

  const bounds = new google.maps.LatLngBounds();
  let any = false;

  farmPolygons.forEach((poly) => {
    const path = poly.getPath();
    for (let i = 0; i < path.getLength(); i++) {
      bounds.extend(path.getAt(i));
      any = true;
    }
  });

  if (any) dashboardFarmMap.fitBounds(bounds);
}

async function loadAndRenderFarms() {
  ensureMapInitialized();
  if (!dashboardFarmMap) return;

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

  clearFarmPolygons();

  if (!out?.ok || !Array.isArray(out.farms) || out.farms.length === 0) {
    dashboardFarmMap.setCenter({ lat: 20.5937, lng: 78.9629 });
    dashboardFarmMap.setZoom(5);
    return;
  }

  out.farms.forEach((farm) => {
    // Safety: always convert to Number (prevents "lat not a number")
    const coords = (farm.coordinates || [])
      .map((p) => {
        const lat = Number(p?.lat);
        const lng = Number(p?.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
        return { lat, lng };
      })
      .filter(Boolean);

    if (coords.length < 3) return;

    const poly = new google.maps.Polygon({
      paths: coords,
      strokeColor: "#388e3c",
      strokeOpacity: 1,
      strokeWeight: 2,
      fillColor: "#81c784",
      fillOpacity: 0.55,
      map: dashboardFarmMap,
    });

    farmPolygons.push(poly);

    poly.addListener("click", (e) => {
      const info = new google.maps.InfoWindow({
        content: `
          <div style="font-size:13px">
            <b>${farm.cropType || "Farm"}</b><br/>
            Crop ID: ${farm.crop_id || "-"}<br/>
            Area: ${farm.area_size || "-"} acres<br/>
            Planted: ${farm.date_planted || "-"}
          </div>
        `,
        position: e.latLng,
      });
      info.open(dashboardFarmMap);
    });
  });

  fitPolygons();
}

/**
 * This is called when user opens "Crop Status" tab.
 * It guarantees:
 * 1) tab is visible
 * 2) map is initialized
 * 3) resize is triggered
 * 4) polygons drawn
 */
window.openDashboardStatusMap = function openDashboardStatusMap() {
  const statusPanel = document.getElementById("tab-status");
  const wrapper = document.getElementById("weatherCardContent");

  // If empty state hid the entire card, map can never render.
  if (wrapper && wrapper.style.display === "none") {
    console.warn("⚠️ weatherCardContent is hidden by empty-state logic. Map cannot render.");
    return;
  }

  const start = Date.now();
  const t = setInterval(() => {
    if (isMapsReady()) {
      clearInterval(t);

      ensureMapInitialized();
      forceMapResize();

      // draw polygons AFTER resize
      setTimeout(() => {
        loadAndRenderFarms();
      }, 150);
    }

    if (Date.now() - start > 8000) {
      clearInterval(t);
      console.warn("⚠️ Google Maps not ready. Check API key referer & script callback.");
    }
  }, 150);
};

/**
 * Optional hook called by initFarmMap callback (when google script loads)
 */
window.onDashboardMapsReady = function () {
  // if user is already on status tab and refreshed
  const isStatusActive = document.getElementById("tab-status")?.classList.contains("active");
  if (isStatusActive) window.openDashboardStatusMap();
};
