(function () {
  const data = window.__DASHBOARD__ || {};

  // ---------- Helpers ----------
  const $ = (id) => document.getElementById(id);

  function toDate(val) {
    // supports ISO string or Date
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
    // show items with date <= selectedDate
    if (!selectedDate) return true;
    const d1 = toDate(itemDate);
    const d2 = toDate(selectedDate);
    if (!d1 || !d2) return true;
    // compare by day end
    d2.setHours(23, 59, 59, 999);
    return d1.getTime() <= d2.getTime();
  }

  function safeNum(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : 0;
  }

  // ---------- Tabs (Soil / Weather / Status) ----------
  function showPanel(panelName) {
  // hide/show your panels here...
  document.getElementById("cropStatusPanel").style.display = panelName === "crop" ? "block" : "none";

  if (panelName === "crop") {
    // wait until maps script is ready
    const t = setInterval(() => {
      if (isMapsReady()) {
        clearInterval(t);
        loadAndRenderFarms();
      }
    }, 150);
  }
}
document.addEventListener("DOMContentLoaded", () => {
  const cropTypeSelect = document.getElementById("cropTypeSelect");
  if (cropTypeSelect) {
    cropTypeSelect.addEventListener("change", () => {
      // only refresh if crop status is active
      const cropPanel = document.getElementById("cropStatusPanel");
      if (cropPanel && cropPanel.style.display !== "none") {
        loadAndRenderFarms();
      }
    });
  }
});

  const tabBtns = document.querySelectorAll(".seg-btn");
  const panels = {
    soil: $("tab-soil"),
    weather: $("tab-weather"),
    status: $("tab-status"),
  };

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const tab = btn.dataset.tab;
      Object.keys(panels).forEach((k) => panels[k].classList.toggle("active", k === tab));
    });
  });

  // ---------- Charts ----------
  let soilChart, orderChart, shipChart;

  function initSoilChart() {
    const ctx = $("soilLineChart").getContext("2d");

    const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data.soil?.soil_temp || [5.6, 5.7, 5.65, 5.9, 6.0, 6.35, 5.8];

    // ✅ create vertical gradient (top → bottom)
    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, "rgba(124, 58, 237, 0.55)"); // dark violet
    gradient.addColorStop(0.6, "rgba(124, 58, 237, 0.20)");
    gradient.addColorStop(1, "rgba(124, 58, 237, 0.02)"); // almost transparent

    soilChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Soil Temperature",
          data: points,
          tension: 0.35,
          pointRadius: 4,
          pointHoverRadius: 5,
          fill: true,

          // 🎨 colors
          borderColor: "#7C3AED",
          backgroundColor: gradient,
          pointBackgroundColor: "#7C3AED",
          pointBorderColor: "#fff",
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            grid: { display: false },
            ticks: { display: false }
          }
        }
      }
    });
  }


  function initOrderDonut() {
    const ctx = $("orderDonutChart").getContext("2d");
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
        datasets: [{ data: values, borderWidth: 0 }]
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } }
      }
    });

    const total = values.reduce((a, b) => a + b, 0);
    $("orderTotal").textContent = String(total);
    $("oRequested").textContent = String(values[0]);
    $("oInTransit").textContent = String(values[1]);
    $("oCompleted").textContent = String(values[2]);
    $("oPaid").textContent = String(values[3]);
  }

  function initShipBars() {
    const ctx = $("shipBarChart").getContext("2d");
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
        datasets: [{ data: values, borderWidth: 1 }]
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { display: false } }
        }
      }
    });

    $("sRequested").textContent = String(values[0]);
    $("sPending").textContent = String(values[1]);
    $("sInTransit").textContent = String(values[2]);
    $("sDelivered").textContent = String(values[3]);
    $("sPayment").textContent = String(values[4]);
  }

  // ---------- Lists (Pending Tasks / Warehouse / Manufacturer) ----------
  function renderList(containerId, items, selectedDate) {
    const el = $(containerId);
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
        status === "requested" ? "requested" :
        status === "approved" ? "approved" :
        status === "paid" ? "paid" :
        status === "pending" ? "pending" :
        status === "stored" ? "stored" : "";

      const dateLabel = fmtDate(toDate(it.due_at || it.created_at));

      el.insertAdjacentHTML("beforeend", `
        <div class="task-item">
          <div class="task-ico" aria-hidden="true">⚙️</div>
          <div style="flex:1;">
            <div class="task-title">${escapeHtml(title)}</div>
            <div class="task-sub">${escapeHtml(sub)} ${dateLabel !== "-" ? "• " + dateLabel : ""}</div>
            ${status ? `<div class="pill ${pillClass}">${escapeHtml(cap(status))}</div>` : ""}
          </div>
          <div style="color:#9ca3af; padding-top:2px;">›</div>
        </div>
      `);
    });
  }

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

  function initDateFilters() {
    const todayISO = new Date().toISOString().slice(0, 10);

    const tasksDate = $("tasksDate");
    const warehouseDate = $("warehouseDate");
    const mfgDate = $("mfgDate");

    // default to today
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

  // ---------- Soil metric switching ----------
  function initSoilSelectors() {
    const metricSel = $("soilMetricSelect");
    if (!metricSel) return;

    metricSel.addEventListener("change", () => {
      const key = metricSel.value;
      const labels = (data.soil?.labels) || ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
      const series = (data.soil?.[key]) || (data.soil?.soil_temp) || [5.6,5.7,5.65,5.9,6.0,6.35,5.8];

      soilChart.data.labels = labels;
      soilChart.data.datasets[0].data = series;
      soilChart.data.datasets[0].label =
        key === "soil_moisture" ? "Soil Moisture" :
        key === "ph" ? "pH" :
        key === "npk" ? "NPK Level" : "Soil Temperature";
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
  });

})();


let farmMap = null;
let farmPolygons = [];

function isMapsReady() {
  return typeof google !== "undefined" && google.maps;
}

function clearFarmPolygons() {
  farmPolygons.forEach(p => p.setMap(null));
  farmPolygons = [];
}

function fitMapToPolygons(polys) {
  const bounds = new google.maps.LatLngBounds();
  let any = false;

  polys.forEach(poly => {
    const path = poly.getPath();
    for (let i = 0; i < path.getLength(); i++) {
      bounds.extend(path.getAt(i));
      any = true;
    }
  });

  if (any) farmMap.fitBounds(bounds);
}

function ensureMapInitialized() {
  if (farmMap || !isMapsReady()) return;

  const el = document.getElementById("farmMap");
  if (!el) return;

  farmMap = new google.maps.Map(el, {
    center: { lat: 20.5937, lng: 78.9629 }, // India fallback
    zoom: 5,
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false
  });
}

async function loadAndRenderFarms() {
  ensureMapInitialized();
  if (!farmMap) return;

  // read crop type from your dropdown (update ID as per your HTML)
  const cropTypeSelect = document.getElementById("cropTypeSelect");
  const cropType = cropTypeSelect ? cropTypeSelect.value : "";

  const url = cropType
    ? `/farmer/dashboard/api/farms?cropType=${encodeURIComponent(cropType)}`
    : `/farmer/dashboard/api/farms`;

  const res = await fetch(url, { headers: { "Accept": "application/json" } });
  const data = await res.json();

  clearFarmPolygons();

  if (!data.ok || !Array.isArray(data.farms) || data.farms.length === 0) {
    // no farms -> just reset view
    farmMap.setCenter({ lat: 20.5937, lng: 78.9629 });
    farmMap.setZoom(5);
    return;
  }

  data.farms.forEach((farm) => {
    const coords = (farm.coordinates || []).filter(p => p && typeof p.lat === "number" && typeof p.lng === "number");
    if (coords.length < 3) return;

    const poly = new google.maps.Polygon({
      paths: coords,
      strokeColor: "#16a34a",
      strokeOpacity: 1,
      strokeWeight: 2,
      fillColor: "#16a34a",
      fillOpacity: 0.18
    });

    poly.setMap(farmMap);
    farmPolygons.push(poly);

    // Optional: click tooltip (basic)
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
        position: e.latLng
      });
      info.open(farmMap);
    });
  });

  fitMapToPolygons(farmPolygons);
}



function initDashboardFarmMap() {
  ensureMapInitialized();

  // If Crop Status is currently active, render immediately
  const cropPanel = document.getElementById("cropStatusPanel");
  if (cropPanel && cropPanel.style.display !== "none") {
    loadAndRenderFarms();
  }
}
