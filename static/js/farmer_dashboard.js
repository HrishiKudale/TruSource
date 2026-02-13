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
      duration: 850,
      easing: "easeOutQuart",
      delay: (ctx) => {
        if (ctx.type === "data") return ctx.dataIndex * delayBase;
        return 0;
      },
    };
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
        // ✅ ensure weather loads every time weather tab is opened
        raf2(() => loadCleanWeatherCard());
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

  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas || typeof Chart === "undefined") return;
    const ctx = canvas.getContext("2d");

    const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

    // ✅ Gradient like your old style
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
        animation: chartAnimStagger(35),
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
          },
        ],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } },
        animation: chartAnimStagger(35),
      },
    });
  }

  async function initShipBars() {
    const canvas = $("shipBarChart");
    if (!canvas || typeof Chart === "undefined") return;

    // ✅ Fix: chart won’t render if canvas area is 0 during first paint
    await waitForVisible(canvas, 2500);

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
        animation: chartAnimStagger(60),
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { display: false }, border: { display: false } },
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
            <div class="task-sub">${escapeHtml(sub)} ${
          dateLabel !== "-" ? "• " + dateLabel : ""
        }</div>
            ${
              status
                ? `<div class="pill">${escapeHtml(cap(status))}</div>`
                : ""
            }
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

      // If you have empty-state JS on page, re-run it safely
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

  /* ============================================================
     WEATHER TAB (your HTML: Current / Next Hours / Next 7 Days)
     Uses Open-Meteo + your IDs:
     wxLocText, wxNowTemp, wxNowIcon, wxNowMeta, wxWind, wxWindDir, wxCode,
     wxHourlyRow, wxWeeklyRow, wxHourlyMeta, wxWeeklyMeta,
     wxLocModal, wxAllowBtn, weatherUseMyLocationBtn, weatherRefreshBtn
  ============================================================ */

  // Small skeleton for strips
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

  async function wxLoadWeatherUsing(lat, lng, label) {
    if ($("wxLocText")) $("wxLocText").textContent = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;

    // Skeleton while loading
    wxSetStripSkeleton($("wxHourlyRow"));
    wxSetStripSkeleton($("wxWeeklyRow"));

    try {
      const apiData = await wxFetchForecast(lat, lng);
      wxRenderCurrent(apiData);
      wxRenderHourly(apiData);
      wxRenderWeekly(apiData);
    } catch (e) {
      console.error("Weather fetch failed:", e);
      wxSetStripError($("wxHourlyRow"), "Weather unavailable right now.");
      wxSetStripError($("wxWeeklyRow"), "Weather unavailable right now.");
    }
  }

  async function loadCleanWeatherCard() {
    // ✅ Weather card may be hidden until tab opens. Ensure visible first.
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
      refreshBtn.addEventListener("click", () => loadCleanWeatherCard());
    }

    // ✅ If weather tab is active on load, render immediately
    if ($("tab-weather")?.classList.contains("active")) {
      raf2(() => loadCleanWeatherCard());
    }
  }

  // Expose for safety (your earlier tab code may call it)
  window.loadCleanWeatherCard = loadCleanWeatherCard;

  /* -----------------------------
     Leaflet Crop Status Map
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

  // keep compatibility
  window.initFarmMap = function initFarmMap() {};

  /* -----------------------------
     BOOT
  ----------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    // Keep your HTML default active tab.
    // If you want weather default, uncomment:
    // setActiveTab("weather");

    initSoilChart();
    initSoilSelectors();

    initOrderDonut();
    initShipBars(); // ✅ now renders reliably

    initDateFilters();
    initWeatherUI();

    // empty-state recalculation (if present)
    try {
      if (typeof window.applyDashboardEmptyStates === "function") {
        window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
      }
    } catch (e) {}
  });
})();
