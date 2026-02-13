(function () {
  "use strict";

  // IMPORTANT: do not reassign data reference (template uses this object)
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
    el.textContent = val == null ? "0" : String(val);
  }

  // double raf: helps charts render after layout
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

  /* -------------------------------------------------------
     Loading shimmer helper (JS toggles)
     Add CSS once in your stylesheet:

     .is-loading { position: relative; overflow: hidden; }
     .is-loading::after {
       content:"";
       position:absolute; inset:0;
       background: linear-gradient(90deg,
          rgba(255,255,255,0) 0%,
          rgba(255,255,255,.55) 50%,
          rgba(255,255,255,0) 100%);
       transform: translateX(-100%);
       animation: shimmer 1.1s infinite;
       pointer-events:none;
     }
     @keyframes shimmer { to { transform: translateX(100%); } }
  ------------------------------------------------------- */
  function withLoading(elOrId, on) {
    const el = typeof elOrId === "string" ? $(elOrId) : elOrId;
    if (!el) return;
    el.classList.toggle("is-loading", !!on);
  }

  function chartAnimStagger(delayBase = 35) {
    return {
      duration: 850,
      easing: "easeOutQuart",
      delay: (ctx) => (ctx.type === "data" ? ctx.dataIndex * delayBase : 0),
    };
  }

  /* -------------------------------------------------------
     Tabs
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
        raf2(() => loadWeatherAll()); // always reload
      }

      if (tab === "soil") {
        raf2(() => {
          if (soilChart) soilChart.resize();
        });
      }
    });
  });

  // crop type change -> refresh polygons only if status tab active
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

  // ---------------- SOIL LINE ----------------
  function initSoilChart() {
    const canvas = $("soilLineChart");
    if (!canvas || typeof Chart === "undefined") return;

    const ctx = canvas.getContext("2d");
    const labels = data.soil?.labels || ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const points = data.soil?.soil_temp || [25.6, 25.7, 25.65, 25.9, 26.0, 26.35, 25.8];

    withLoading(canvas.closest(".card-body") || canvas.parentElement, true);

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

    setTimeout(() => withLoading(canvas.closest(".card-body") || canvas.parentElement, false), 900);
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

  // ---------------- ORDER DONUT (rounded segments) ----------------
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

    setText("orderTotal", total);
    setText("oRequested", values[0]);
    setText("oInTransit", values[1]);
    setText("oCompleted", values[2]);
    setText("oPaid", values[3]);

    withLoading(canvas.closest(".card-body") || canvas.parentElement, true);

    if (orderChart) orderChart.destroy();

    orderChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Requested", "In transit", "Completed", "Payment Received"],
        datasets: [
          {
            data: values,
            backgroundColor: ["#FDE68A", "#60A5FA", "#86EFAC", "#C4B5FD"],
            borderWidth: 0,
            borderRadius: 14,  // ✅ rounded ends
            spacing: 4,        // ✅ small gap between segments
            hoverOffset: 6,
          },
        ],
      },
      options: {
        cutout: "72%",
        plugins: { legend: { display: false } },
        animation: chartAnimStagger(30),
      },
    });

    setTimeout(() => withLoading(canvas.closest(".card-body") || canvas.parentElement, false), 800);
  }

  /* -------------------------------------------------------
     ✅ SHIPMENTS (YOUR HTML IS NOT CANVAS)
     Uses #shipBars div and legend IDs.
  ------------------------------------------------------- */
  function renderShipmentBars() {
    const container = $("shipBars");
    if (!container) return;

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
    } else {
      if (emptyEl) emptyEl.style.display = "none";
      if (contentEl) contentEl.style.display = "block";
    }

    withLoading(container.closest(".card-body") || container.parentElement, true);

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
      .map((r) => {
        return `
          <div class="ship-row">
            <div class="ship-label">${escapeHtml(r.label)}</div>
            <div class="ship-track">
              <div class="ship-fill ${r.cls}" style="width:0%"></div>
            </div>
          </div>
        `;
      })
      .join("");

    raf2(() => {
      const fills = container.querySelectorAll(".ship-fill");
      fills.forEach((fill, idx) => {
        const key = rows[idx].key;
        const pct = Math.round((values[key] / max) * 100);
        fill.style.width = pct + "%";
      });
      setTimeout(() => withLoading(container.closest(".card-body") || container.parentElement, false), 400);
    });
  }

  /* -------------------------------------------------------
     Warehouse Pie (summary OR derived from warehouse_requests)
     Required IDs if you want the pie:
       - canvas#warehousePieChart
       - wrap#warehousePieWrap  (optional)
       - empty#emptyWarehouseCard (optional)
       - counters: whRequested, whStored, whPendingPay
  ------------------------------------------------------- */
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
    const canvas = $("warehousePieChart");
    if (!canvas || typeof Chart === "undefined") {
      // still set numbers if counters exist
      const fromList = countByStatus(data.warehouse_requests);
      const requested = safeNum(fromList.requested ?? 0);
      const stored = safeNum(fromList.stored ?? fromList.accepted ?? 0);
      const pendingPay = safeNum(fromList["pending payment"] ?? fromList.pending_payment ?? 0);
      setText("whRequested", requested);
      setText("whStored", stored);
      setText("whPendingPay", pendingPay);
      return;
    }

    const summary = data.warehouse_summary || data.warehouse || null;
    const fromList = countByStatus(data.warehouse_requests);

    const requested = safeNum(summary?.requested ?? fromList.requested ?? 0);
    const stored = safeNum(summary?.stored ?? fromList.stored ?? fromList.accepted ?? 0);
    const pendingPay = safeNum(
      summary?.pending_payment ??
        fromList["pending payment"] ??
        fromList.pending_payment ??
        0
    );

    setText("whRequested", requested);
    setText("whStored", stored);
    setText("whPendingPay", pendingPay);

    const total = requested + stored + pendingPay;

    const emptyEl = $("emptyWarehouseCard");
    const wrap = $("warehousePieWrap");
    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "flex";
      return;
    } else {
      if (emptyEl) emptyEl.style.display = "none";
      if (wrap) wrap.style.display = "block";
    }

    withLoading(canvas.closest(".card-body") || canvas.parentElement, true);

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
        animation: chartAnimStagger(40),
      },
    });

    setTimeout(() => withLoading(canvas.closest(".card-body") || canvas.parentElement, false), 850);
  }

  /* -------------------------------------------------------
     Manufacturer Pie + Numbers (always computed)
     IDs:
       mfgRequested, mfgProcessing, mfgPendingPay
       canvas#mfgPieChart (optional)
       wrap#mfgPieWrap (optional)
       empty#emptyManufacturerCard (optional)
  ------------------------------------------------------- */
  function initManufacturerCard() {
    const list = Array.isArray(data.manufacturer_requests) ? data.manufacturer_requests : [];
    const summary = data.manufacturer_summary || data.manufacturer || null;
    const fromList = countByStatus(list);

    const requested = safeNum(summary?.requested ?? fromList.requested ?? 0);
    const processing = safeNum(summary?.processing ?? fromList.processing ?? 0);
    const pendingPay = safeNum(
      summary?.pending_payment ??
        fromList["pending payment"] ??
        fromList.pending_payment ??
        0
    );

    setText("mfgRequested", requested);
    setText("mfgProcessing", processing);
    setText("mfgPendingPay", pendingPay);

    const canvas = $("mfgPieChart");
    if (!canvas || typeof Chart === "undefined") return;

    const total = requested + processing + pendingPay;

    const emptyEl = $("emptyManufacturerCard");
    const wrap = $("mfgPieWrap");
    if (total <= 0) {
      if (wrap) wrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "flex";
      return;
    } else {
      if (emptyEl) emptyEl.style.display = "none";
      if (wrap) wrap.style.display = "block";
    }

    withLoading(canvas.closest(".card-body") || canvas.parentElement, true);

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
        animation: chartAnimStagger(40),
      },
    });

    setTimeout(() => withLoading(canvas.closest(".card-body") || canvas.parentElement, false), 850);
  }

  /* -------------------------------------------------------
     Weather (NO LINE, NO COMBO)
     - Always loads when page loads
     - Loads again when weather tab opened
     - If you have a weather bar canvas, it will render bars only.
     - Also supports weather_image_url if you use image based weather.
  ------------------------------------------------------- */
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
    const cloud = `
      <svg class="wx-anim-float" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <path d="M16 34h18a8 8 0 0 0 0-16 10 10 0 0 0-19-3A7 7 0 0 0 16 34Z" ${common}></path>
      </svg>
    `;
    const sun = `
      <svg class="wx-anim-float" width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="24" r="7" ${common}></circle>
        <path d="M24 4v6" ${common}></path><path d="M24 38v6" ${common}></path>
        <path d="M4 24h6" ${common}></path><path d="M38 24h6" ${common}></path>
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
    const c = Number(code || 0);
    if ([0, 1].includes(c)) return sun;
    if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(c)) return rain;
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

    if (!cur) return;

    const t = Number(cur.temperature);
    const ws = Number(cur.windspeed);
    const wd = Number(cur.winddirection);
    const code = Number(cur.weathercode);

    if (nowTemp) nowTemp.textContent = Number.isFinite(t) ? `${t.toFixed(1)}°C` : "—";
    if (nowIcon) nowIcon.innerHTML = wxSvgIcon(code);
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
      if (t.getTime() >= now.getTime()) { startIdx = i; break; }
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

  function extractNext12Hours(apiData) {
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
      labels.push(d.toLocaleTimeString([], { hour: "numeric" }).replace(" ", ""));
      values.push(Number(temps[i] ?? 0));
    }
    return { labels, values };
  }

  // Weather chart bars only (NO LINE)
  function renderWeatherBarsOnly(labels, values) {
    const canvas = $("weatherBarChart") || $("weatherComboChart");
    if (!canvas || typeof Chart === "undefined") return;
    if (!labels.length || !values.length) return;

    withLoading(canvas.closest(".card-body") || canvas.parentElement, true);

    const ctx = canvas.getContext("2d");
    if (weatherBarChart) weatherBarChart.destroy();

    weatherBarChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Temperature",
            data: values,
            backgroundColor: "rgba(99,102,241,0.20)",
            borderColor: "#6366F1",
            borderWidth: 2,
            borderRadius: 10,
            barThickness: 28,
            maxBarThickness: 34,
            categoryPercentage: 0.9,
            barPercentage: 0.9,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: chartAnimStagger(25),
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

    setTimeout(() => withLoading(canvas.closest(".card-body") || canvas.parentElement, false), 850);
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

  async function wxLoadUsing(lat, lng, label) {
    if ($("wxLocText")) $("wxLocText").textContent = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    wxSetStripSkeleton($("wxHourlyRow"));
    wxSetStripSkeleton($("wxWeeklyRow"));

    try {
      const apiData = await wxFetchForecast(lat, lng);
      wxRenderCurrent(apiData);
      wxRenderHourly(apiData);
      wxRenderWeekly(apiData);

      const { labels, values } = extractNext12Hours(apiData);
      renderWeatherBarsOnly(labels, values);
    } catch (e) {
      console.error("Weather fetch failed:", e);
      wxSetStripError($("wxHourlyRow"), "Weather unavailable right now.");
      wxSetStripError($("wxWeeklyRow"), "Weather unavailable right now.");
      if ($("wxLocText")) $("wxLocText").textContent = "Weather: failed to load";
    }
  }

  async function loadWeatherAll() {
    // if you have image-based weather, apply it too
    // (only if your HTML has an <img id="weatherImage">)
    if (data.weather_image_url && $("weatherImage")) {
      $("weatherImage").src = data.weather_image_url;
    }

    // Try live coords -> dashboard coords -> show error
    const live = wxGetSavedCoords();
    if (live) return wxLoadUsing(live.lat, live.lng, "Live location");

    const dash = wxGetDashboardCoords();
    if (dash) {
      const label = (dash.address || "").trim() || `${dash.lat.toFixed(4)}, ${dash.lng.toFixed(4)}`;
      return wxLoadUsing(dash.lat, dash.lng, label);
    }

    // If no coords, show helpful error
    wxSetStripError($("wxHourlyRow"), "No location found (lat/lng missing).");
    wxSetStripError($("wxWeeklyRow"), "No location found (lat/lng missing).");
    if ($("wxLocText")) $("wxLocText").textContent = "Location not available";
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
     Right side lists + date filters
  ------------------------------------------------------- */
  function fmtDate(d) {
    if (!d) return "-";
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

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

  /* -------------------------------------------------------
     Leaflet Crop Status Map (kept from your code)
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

    setTimeout(() => { try { map.invalidateSize(); } catch (e) {} }, 60);

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

    if (allBounds.length) map.fitBounds(allBounds, { padding: [20, 20] });
  }

  async function openCropStatusAndRenderMap() {
    const farmMapEl = $("farmMap");
    if (!farmMapEl) return;

    setActiveTab("status");
    await waitForVisible(farmMapEl, 8000);

    await ensureLeafletMapInitialized();

    setTimeout(() => { try { dashboardLeafletMap.invalidateSize(); } catch (e) {} }, 80);
    await loadAndRenderFarmsLeaflet();
  }

  window.initFarmMap = function initFarmMap() {};

  /* -------------------------------------------------------
     BOOT (everything in correct order)
  ------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    // Soil + Orders
    initSoilChart();
    initSoilSelectors();
    initOrderDonut();

    // Shipment (div-based)
    renderShipmentBars();

    // Warehouse + Manufacturer
    initWarehousePie();
    initManufacturerCard();

    // Right lists
    initDateFilters();

    // Weather UI + Auto-load weather once
    initWeatherUI();
    loadWeatherAll(); // ✅ loads even if user never clicks Weather tab

    // empty-state recalculation (your helper)
    try {
      if (typeof window.applyDashboardEmptyStates === "function") {
        window.applyDashboardEmptyStates(window.__DASHBOARD__ || {});
      }
    } catch (e) {}
  });
})();
