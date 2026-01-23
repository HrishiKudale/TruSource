/* ================================
   addcrop.js  (NO <script> tags here)
   - Supports BOTH:
     1) Blank page -> register crop
     2) Prefilled crop -> register harvest
   - RFID modal:
     ✅ Keyboard-wedge EPC scanning (24 HEX)
     ✅ Auto-add EPC into table until Total Bags reached
     ✅ Duplicate suppression (fast double scans)
     ✅ Keeps focus and continues scanning
=================================== */

(function () {
  "use strict";

  /* -------------------------------------------------
     Helpers
  ------------------------------------------------- */
  function safeJSONParse(v, fallback) {
    try {
      return JSON.parse(v);
    } catch (e) {
      return fallback;
    }
  }

  function qs(id) {
    return document.getElementById(id);
  }

  /* -------------------------------------------------
     Detect prefilled mode
  ------------------------------------------------- */
  const IS_PREFILLED =
    window.__IS_PREFILLED__ === true || window.__IS_PREFILLED__ === "true";

  /* =========================
     Crop ID auto-generation
     - Only when NOT prefilled
  ========================== */
  function cropPrefixFromName(name) {
    if (!name) return "CRP";
    const n = name.trim().toLowerCase();
    const mapping = {
      wheat: "WHT",
      rice: "RIC",
      paddy: "PAD",
      maize: "MAZ",
      corn: "CRN",
      soybean: "SBN",
      soyabean: "SBN",
      cotton: "CTN",
      sugarcane: "SGC",
    };
    if (mapping[n]) return mapping[n];
    const cleaned = n.replace(/[^a-z0-9]/g, "");
    if (!cleaned) return "CRP";
    return cleaned.slice(0, 3).toUpperCase();
  }

  function updateCropId() {
    if (IS_PREFILLED) return; // do not change if prefilled harvest mode

    const cropNameEl = qs("cropName");
    const dateEl = qs("datePlanted");
    const idEl = qs("cropId");
    if (!cropNameEl || !dateEl || !idEl) return;

    const cropName = (cropNameEl.value || "").trim();
    const dateStr = (dateEl.value || "").trim();

    if (!cropName || !dateStr) {
      idEl.value = "";
      return;
    }

    const prefix = cropPrefixFromName(cropName);
    const datePart = dateStr.replace(/-/g, "");

    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    const ss = String(now.getSeconds()).padStart(2, "0");

    idEl.value = prefix + datePart + hh + mm + ss;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const cropNameEl = qs("cropName");
    const dateEl = qs("datePlanted");

    if (!IS_PREFILLED) {
      if (cropNameEl) cropNameEl.addEventListener("change", updateCropId);
      if (dateEl) dateEl.addEventListener("change", updateCropId);
    }
  });

    /* =========================
     Map + polygon logic
  ========================== */
  let polygonMap;
  let drawingManager;
  let polygonOverlay;
  let polygonCoords = [];

  let locationPreviewMap;
  let locationPreviewPolygon;
  window.initPolygonMap = function initPolygonMap() {
    const mapEl = qs("farm-map-modal");
    if (!mapEl || !window.google) return;

    if (polygonMap) {
      google.maps.event.trigger(polygonMap, "resize");
      return;
    }

    polygonMap = new google.maps.Map(mapEl, {
      center: { lat: 20.5937, lng: 78.9629 },
      zoom: 15,
      mapTypeId: "roadmap",
    });


    // Search box (Places)
    const searchInput = qs("map-search-input");
    if (searchInput && google.maps.places) {
      const searchBox = new google.maps.places.SearchBox(searchInput);

      searchBox.addListener("places_changed", () => {
        const places = searchBox.getPlaces();
        if (!places || places.length === 0) return;

        const bounds = new google.maps.LatLngBounds();
        places.forEach((place) => {
          if (!place.geometry) return;
          if (place.geometry.viewport) bounds.union(place.geometry.viewport);
          else bounds.extend(place.geometry.location);
        });
        polygonMap.fitBounds(bounds);
      });
    }

    // Locate me
    const locateBtn = qs("locate-me-btn");
    if (locateBtn) {
      locateBtn.addEventListener("click", () => {
        if (!navigator.geolocation) {
          alert("Geolocation is not supported in this browser.");
          return;
        }
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const userPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
            polygonMap.setCenter(userPos);
            polygonMap.setZoom(17);

            new google.maps.Marker({
              position: userPos,
              map: polygonMap,
              title: "Your Location",
            });
          },
          () => alert("Enable location permission to center the map.")
        );
      });
    }

    // Drawing manager (requires drawing library)
    if (!google.maps.drawing) {
      console.warn(
        "Google Maps drawing library not loaded. Add libraries=drawing,places,geometry"
      );
      return;
    }

    drawingManager = new google.maps.drawing.DrawingManager({
      drawingMode: google.maps.drawing.OverlayType.POLYGON,
      drawingControl: true,
      drawingControlOptions: {
        position: google.maps.ControlPosition.TOP_CENTER,
        drawingModes: [google.maps.drawing.OverlayType.POLYGON],
      },
      polygonOptions: {
        fillColor: "#81c784",
        fillOpacity: 0.6,
        strokeColor: "#388e3c",
        strokeWeight: 2,
      },
    });

    drawingManager.setMap(polygonMap);

    google.maps.event.addListener(drawingManager, "overlaycomplete", (event) => {
      if (polygonOverlay) polygonOverlay.setMap(null);
      polygonOverlay = event.overlay;

      polygonCoords = polygonOverlay
        .getPath()
        .getArray()
        .map((p) => ({ lat: p.lat(), lng: p.lng() }));

      updateModalSummary();
    });
  };

  function calculatePolygonAreaAcres(coords) {
    if (!coords || coords.length < 3 || !window.google || !google.maps.geometry) return 0;
    const path = coords.map((p) => new google.maps.LatLng(p.lat, p.lng));
    const areaSqM = google.maps.geometry.spherical.computeArea(path);
    return areaSqM / 4046.86;
  }

  function updateModalSummary() {
    const areaEl = qs("map-modal-area");
    const latlngEl = qs("map-modal-latlng");

    if (!polygonCoords || polygonCoords.length < 3) {
      if (areaEl) areaEl.textContent = "Draw polygon to calculate";
      if (latlngEl) latlngEl.textContent = "—";
      return;
    }

    const acres = calculatePolygonAreaAcres(polygonCoords);
    if (areaEl) areaEl.textContent = acres.toFixed(2) + " acres";

    let latSum = 0,
      lngSum = 0;
    polygonCoords.forEach((p) => {
      latSum += p.lat;
      lngSum += p.lng;
    });

    const centroidLat = latSum / polygonCoords.length;
    const centroidLng = lngSum / polygonCoords.length;

    if (latlngEl) {
      latlngEl.textContent = centroidLat.toFixed(4) + "° N, " + centroidLng.toFixed(4) + "° E";
    }
  }
function openMapModal() {
  const modal = document.getElementById("map-modal");
  if (!modal) return;

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");

  if (polygonMap && window.google) {
    google.maps.event.trigger(polygonMap, "resize");
  }
}

window.closeMapModal = function closeMapModal() {
    const modal = qs("map-modal");
    if (!modal) return;
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  };

  function renderLocationMap(coords) {
    const mapContainer = qs("location-map");
    if (!mapContainer || !coords || !coords.length || !window.google) return;

    if (!locationPreviewMap) {
      locationPreviewMap = new google.maps.Map(mapContainer, {
        center: coords[0],
        zoom: 15,
        mapTypeId: "satellite",
        disableDefaultUI: true,
      });
    }

    if (locationPreviewPolygon) locationPreviewPolygon.setMap(null);

    locationPreviewPolygon = new google.maps.Polygon({
      paths: coords,
      strokeColor: "#388e3c",
      strokeOpacity: 1,
      strokeWeight: 2,
      fillColor: "#81c784",
      fillOpacity: 0.55,
      map: locationPreviewMap,
    });

    const bounds = new google.maps.LatLngBounds();
    coords.forEach((p) => bounds.extend(new google.maps.LatLng(p.lat, p.lng)));
    locationPreviewMap.fitBounds(bounds);
  }

  function applyLocationSummary(coords) {
    const areaEl = qs("location-area");
    const latLngEl = qs("location-latlng");

    const acres = calculatePolygonAreaAcres(coords);
    if (areaEl) areaEl.textContent = acres.toFixed(2) + " acres";

    let latSum = 0,
      lngSum = 0;
    coords.forEach((p) => {
      latSum += p.lat;
      lngSum += p.lng;
    });

    const centroidLat = latSum / coords.length;
    const centroidLng = lngSum / coords.length;

    if (latLngEl) {
      latLngEl.textContent = centroidLat.toFixed(4) + "° N, " + centroidLng.toFixed(4) + "° E";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const openBtn = qs("open-map-modal");
    const resetBtn = qs("map-modal-reset");
    const continueBtn = qs("map-modal-continue");

    if (openBtn) {
      openBtn.addEventListener("click", (e) => {
        e.preventDefault();
        openMapModal();
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        if (polygonOverlay) {
          polygonOverlay.setMap(null);
          polygonOverlay = null;
        }
        polygonCoords = [];
        updateModalSummary();
      });
    }

    if (continueBtn) {
      continueBtn.addEventListener("click", () => {
        const cropId = (qs("cropId")?.value || "").trim();
        const cropName = (qs("cropName")?.value || "").trim();
        const datePlanted = (qs("datePlanted")?.value || "").trim();

        if (!polygonCoords.length || polygonCoords.length < 3) {
          alert("Draw your farm area first.");
          return;
        }
        if (!cropId || !cropName || !datePlanted) {
          alert("Please fill Crop Name, Crop ID and Date Planted first.");
          return;
        }

        // Close polygon
        const pc = [...polygonCoords];
        if (pc[0].lat !== pc[pc.length - 1].lat || pc[0].lng !== pc[pc.length - 1].lng) {
          pc.push(pc[0]);
        }

        const areaStr = calculatePolygonAreaAcres(pc).toFixed(2);

        // Save hidden fields for main form submit
        const areaInput = qs("areaSize");
        const coordsField = qs("coordsField");
        if (areaInput) areaInput.value = areaStr;
        if (coordsField) coordsField.value = JSON.stringify(pc);

        // Live update preview box
        applyLocationSummary(pc);
        renderLocationMap(pc);

        // Optional: save polygon to backend (requires jQuery in your base template)
        if (window.$) {
          $.ajax({
            url: "/farmer/save_farm_coordinates",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({
              coordinates: pc,
              crop_id: cropId,
              cropId: cropId,
              crop_type: cropName,
              cropType: cropName,
              area_size: areaStr,
              areaSize: areaStr,
              date_planted: datePlanted,
              datePlanted: datePlanted,
            }),
          });
        }

        window.closeMapModal();
      });
    }

    // If coords already exist in hidden input, render preview immediately
    const coordsField = qs("coordsField");
    if (coordsField && coordsField.value) {
      const coords = safeJSONParse(coordsField.value, []);
      if (Array.isArray(coords) && coords.length >= 3) {
        renderLocationMap(coords);
        applyLocationSummary(coords);
      }
    }
  });

  /* =========================
     Fetch & render existing coords (optional)
  ========================== */
  function fetchAndRenderCropCoordinates(cropId) {
    if (!cropId || !window.$) return;

    $.ajax({
      url: "/farmer/get_farm_coordinates",
      method: "GET",
      success: function (response) {
        if (!response || response.ok !== true || !Array.isArray(response.data)) return;

        const row = response.data.find((x) => x.crop_id === cropId || x.cropId === cropId);
        const coordsRaw = row?.coordinates || [];
        const coords = coordsRaw.map((p) => ({
          lat: parseFloat(p.lat),
          lng: parseFloat(p.lng),
        }));

        if (coords.length >= 3) {
          const coordsField = qs("coordsField");
          if (coordsField) coordsField.value = JSON.stringify(coords);

          renderLocationMap(coords);
          applyLocationSummary(coords);
        }
      },
      error: function () {
        console.error("Failed to fetch coordinates for crop:", cropId);
      },
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const cropIdEl = qs("cropId");
    if (cropIdEl && cropIdEl.value && IS_PREFILLED) {
      fetchAndRenderCropCoordinates(cropIdEl.value);
    }
  });


  /* =========================
     Summary modal (review -> save -> success)
  ========================== */
  (function () {
    const form = qs("add-crop-form");
    if (!form) return;

    const modal = qs("cropSummaryModal");
    const backdrop = qs("cropSummaryBackdrop");

    const btnOpen = qs("openSummaryModalBtn");
    const btnEdit = qs("btnEditBack");
    const btnConfirm = qs("btnConfirmSave");

    const stateReview = qs("summaryStateReview");
    const stateSuccess = qs("summaryStateSuccess");
    const errEl = qs("summaryError");

    function openModal() {
      if (!modal) return;
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
    }
    function closeModal() {
      if (!modal) return;
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
    }

    function getValue(id) {
      const el = qs(id);
      return el ? (el.value ?? "").toString().trim() : "";
    }

    function getSelectText(id) {
      const el = qs(id);
      if (!el) return "";
      const opt = el.selectedOptions && el.selectedOptions[0];
      return opt
        ? (opt.textContent ?? "").toString().trim()
        : (el.value ?? "").toString().trim();
    }

    function setText(id, val) {
      const el = qs(id);
      if (el) el.textContent = val && String(val).trim() ? val : "-";
    }

    function showError(msg) {
      if (!errEl) return;
      errEl.style.display = "block";
      errEl.textContent = msg || "Something went wrong.";
    }

    function clearError() {
      if (!errEl) return;
      errEl.style.display = "none";
      errEl.textContent = "";
    }

    function fillSummary() {
      const cropName = getValue("cropName");
      const seedType = getSelectText("seedType");
      const farmingType = getSelectText("farmingType");

      const areaSize = getValue("areaSize");
      const datePlanted = getValue("datePlanted");

      const harvestDate = getValue("harvestDate");
      const hQty = getValue("harvestQuantity");
      const hUnit = getSelectText("harvestQtyUnit");
      const qtyText = hQty ? `${hQty} ${hUnit || ""}`.trim() : "-";

      setText("sumCropType", cropName);
      setText("sumSeedType", seedType);
      setText("sumFarmingType", farmingType);
      setText("sumAreaSize", areaSize ? `${areaSize} acres` : "-");
      setText("sumDatePlanted", datePlanted);
      setText("sumHarvestDate", harvestDate);
      setText("sumHarvestQty", qtyText);
    }

    if (btnOpen) {
      btnOpen.addEventListener("click", () => {
        clearError();

        if (!form.checkValidity()) {
          form.reportValidity();
          return;
        }

        const coords = getValue("coordsField");
        const area = getValue("areaSize");

        fillSummary();
        if (stateReview) stateReview.style.display = "block";
        if (stateSuccess) stateSuccess.style.display = "none";

        if (!coords || !area) {
          showError("Please plot farm area (coordinates) before saving.");
        }

        openModal();
      });
    }

    if (btnEdit) btnEdit.addEventListener("click", closeModal);
    if (backdrop) backdrop.addEventListener("click", closeModal);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal && modal.classList.contains("is-open")) closeModal();
    });

    if (btnConfirm) {
      btnConfirm.addEventListener("click", async () => {
        clearError();

        if (IS_PREFILLED) {
          const hDate = getValue("harvestDate");
          const hQty = getValue("harvestQuantity");
          if (!hDate || !hQty) {
            showError("Please fill Harvest Date and Quantity.");
            return;
          }
        }

        btnConfirm.disabled = true;
        const originalText = btnConfirm.textContent;
        btnConfirm.textContent = "Saving...";

        try {
          const actionUrl = form.getAttribute("action");
          const fd = new FormData(form);

          const res = await fetch(actionUrl, { method: "POST", body: fd });

          if (!res.ok) {
            let msg = IS_PREFILLED ? "Failed to save harvest." : "Failed to save crop.";
            const contentType = res.headers.get("content-type") || "";
            if (contentType.includes("application/json")) {
              const j = await res.json().catch(() => ({}));
              msg = j.error || j.message || msg;
            }
            throw new Error(msg);
          }

          if (stateReview) stateReview.style.display = "none";
          if (stateSuccess) stateSuccess.style.display = "block";
        } catch (err) {
          showError(err.message);
        } finally {
          btnConfirm.disabled = false;
          btnConfirm.textContent = originalText;
        }
      });
    }
  })();
})();
/* =========================================================
   RFID MODAL (Keyboard wedge -> table)
   - Fixed EPC length: 24 HEX chars
   - Auto-add at 24 (even if scanner doesn't send Enter)
   - Enter/Tab also adds
   - Stops when Total Bags reached
========================================================= */
(function () {
  "use strict";

  // ---- Read page data safely ----
  let PAGE = {};
  try {
    PAGE = JSON.parse(document.getElementById("pageData")?.textContent || "{}");
  } catch (e) {
    PAGE = {};
  }

  const showRfidBtn = !!PAGE.showRfidBtn;
  const crop = PAGE.crop || {};
  const session = PAGE.session || {};
  const urls = PAGE.urls || {};

  const btnGenerate = document.getElementById("btnGenerateRFID");
  const modal = document.getElementById("rfidModal");
  if (!showRfidBtn || !btnGenerate || !modal) return;

  const backdrop = document.getElementById("rfidBackdrop");
  const closeBtn = document.getElementById("rfidCloseBtn");

  const toggleScanBtn = document.getElementById("rfidToggleScanBtn");
  const listEl = document.getElementById("rfidList");
  const emptyEl = document.getElementById("rfidEmptyState");
  const countEl = document.getElementById("rfidCount");
  const registerBtn = document.getElementById("rfidRegisterBtn");

  const packDateEl = document.getElementById("rfidPackagingDate");
  const expiryEl = document.getElementById("rfidExpiryDate");
  const bagCapEl = document.getElementById("rfidBagCapacity");
  const totalBagsEl = document.getElementById("rfidTotalBags");

  const scanInput = document.getElementById("rfidScanInput"); // ✅ USE VISIBLE INPUT
  const errEl = document.getElementById("rfidError");
  const okEl = document.getElementById("rfidSuccess");

  const hiddenEpcs = document.getElementById("rfidEpcs");

  // EPC rule
  const EXACT = 24;

  let scanning = false;
  let epcs = [];

  // debounce auto-add when reaches 24
  let autoAddTimer = null;

  // suppress very fast duplicate scans
  let lastEpc = "";
  let lastEpcTs = 0;

  function hideMsg() {
    if (errEl) errEl.style.display = "none";
    if (okEl) okEl.style.display = "none";
  }

  function showError(msg) {
    if (!errEl) return;
    errEl.textContent = msg || "Something went wrong.";
    errEl.style.display = "block";
    if (okEl) okEl.style.display = "none";
  }

  function showSuccess(msg) {
    if (!okEl) return;
    okEl.textContent = msg || "Success.";
    okEl.style.display = "block";
    if (errEl) errEl.style.display = "none";
  }

  function expectedCount() {
    const n = parseInt((totalBagsEl?.value || "").toString(), 10);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  function hexClean(v) {
    // keep ONLY 0-9A-F, UPPERCASE, and cut to EXACT
    return (v || "")
      .toString()
      .toUpperCase()
      .replace(/[^0-9A-F]/g, "")
      .slice(0, EXACT);
  }

  function setScan(on) {
    scanning = !!on;
    hideMsg();

    if (toggleScanBtn) {
      toggleScanBtn.textContent = scanning ? "Scanning: ON (Stop)" : "Start Scanning";
    }

    if (scanInput) {
      scanInput.value = "";
      scanInput.readOnly = !scanning;
      if (scanning) scanInput.focus({ preventScroll: true });
      else scanInput.blur();
    }
  }

  function setCountUI() {
    if (countEl) countEl.textContent = "Scanned " + epcs.length;
    if (registerBtn) registerBtn.disabled = epcs.length === 0;
    if (hiddenEpcs) hiddenEpcs.value = JSON.stringify(epcs);
  }

  function render() {
    // clear existing rows (keep empty state node)
    const rows = listEl.querySelectorAll(".rfid-table-row");
    rows.forEach((r) => r.remove());

    if (!epcs.length) {
      if (emptyEl) emptyEl.style.display = "block";
      setCountUI();
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";

    epcs.forEach((epc) => {
      const row = document.createElement("div");
      row.className = "rfid-table-row";
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.alignItems = "center";
      row.style.padding = "10px 0";
      row.style.borderTop = "1px solid rgba(0,0,0,0.06)";

      const left = document.createElement("div");
      left.textContent = epc;
      left.style.fontFamily = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace";
      left.style.fontSize = "13px";

      const right = document.createElement("div");
      right.className = "right";
      right.style.display = "flex";
      right.style.gap = "10px";
      right.style.justifyContent = "flex-end";

      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "🗑";
      del.title = "Delete";
      del.style.width = "36px";
      del.style.height = "36px";
      del.style.borderRadius = "10px";
      del.style.border = "1px solid rgba(0,0,0,0.12)";
      del.style.background = "#fff";
      del.style.cursor = "pointer";

      del.addEventListener("click", () => {
        epcs = epcs.filter((x) => x !== epc);
        hideMsg();
        render();
        if (scanning) scanInput?.focus({ preventScroll: true });
      });

      right.appendChild(del);

      row.appendChild(left);
      row.appendChild(right);

      listEl.appendChild(row);
    });

    setCountUI();
  }

  function finalizeAddFromInput() {
    if (!scanning || !scanInput) return;

    const cleaned = hexClean(scanInput.value);
    scanInput.value = cleaned; // enforce fixed length view

    if (cleaned.length !== EXACT) return;

    const exp = expectedCount();
    if (exp > 0 && epcs.length >= exp) {
      showError(`Already scanned ${exp} EPC(s).`);
      scanInput.value = "";
      return;
    }

    // suppress fast duplicates
    const now = Date.now();
    if (cleaned === lastEpc && now - lastEpcTs < 1200) {
      scanInput.value = "";
      return;
    }
    lastEpc = cleaned;
    lastEpcTs = now;

    if (epcs.includes(cleaned)) {
      showError("EPC already scanned.");
      scanInput.value = "";
      return;
    }

    epcs.push(cleaned);
    hideMsg();
    render();

    scanInput.value = "";
    scanInput.focus({ preventScroll: true });

    if (exp > 0 && epcs.length === exp) {
      showSuccess(`All ${exp} EPC(s) scanned. Now click Register.`);
      setScan(false);
    }
  }

  function onScanInput(e) {
    if (!scanning || !scanInput) return;

    // always keep fixed length + hex
    const cleaned = hexClean(scanInput.value);
    if (cleaned !== scanInput.value) scanInput.value = cleaned;

    // stop extra characters beyond 24
    if (scanInput.value.length >= EXACT) {
      scanInput.value = scanInput.value.slice(0, EXACT);
    }

    // auto-add when reaches 24 (scanner may not send Enter)
    if (scanInput.value.length === EXACT) {
      if (autoAddTimer) clearTimeout(autoAddTimer);
      autoAddTimer = setTimeout(() => {
        finalizeAddFromInput();
      }, 30);
    }
  }

  function onScanKeyDown(e) {
    if (!scanning) return;

    // Enter/Tab add immediately
    if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      if (autoAddTimer) clearTimeout(autoAddTimer);
      finalizeAddFromInput();
      return;
    }

    // prevent typing beyond 24 if already full (but allow Backspace/Delete)
    if (
      scanInput &&
      scanInput.value.length >= EXACT &&
      e.key.length === 1 &&
      e.key !== "Backspace" &&
      e.key !== "Delete"
    ) {
      e.preventDefault();
    }
  }

  async function registerAll() {
    hideMsg();

    const payload = {
      userId: session.userId || "",
      username:
      (document.getElementById("farmerName")?.value || "").trim() ||
      (crop.farmerName || "").trim() ||
      (session.userName || "").trim() ||   // harmless fallback if later added
      "",

      cropType: crop.cropType || "",
      cropId: crop.id || "",
      packagingDate: (packDateEl?.value || "").trim(),
      expiryDate: (expiryEl?.value || "").trim(),
      bagCapacity: (bagCapEl?.value || "").trim(),
      totalBags: (totalBagsEl?.value || "").trim(),
      epcs: epcs,
    };

    if (!payload.cropId) return showError("Missing cropId.");
    if (!payload.packagingDate) return showError("Packaging date required.");
    if (!payload.expiryDate) return showError("Expiry date required.");
    if (!payload.bagCapacity) return showError("Bag capacity required.");
    if (!payload.totalBags) return showError("Total bags required.");
    if (!payload.epcs.length) return showError("Scan at least 1 EPC.");

    const exp = expectedCount();
    if (exp > 0 && epcs.length !== exp) {
      return showError(`Scan exactly ${exp} EPC(s). Currently: ${epcs.length}`);
    }

    if (!urls.rfidRegister) return showError("RFID API URL not set in template.");

    try {
      registerBtn.disabled = true;
      const old = registerBtn.textContent;
      registerBtn.textContent = "Registering...";

      const res = await fetch(urls.rfidRegister, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });

      const out = await res.json().catch(() => ({}));
      if (!res.ok || out.ok === false) throw new Error(out.message || "Registration failed.");

      showSuccess(out.message || "RFID registered successfully.");
      registerBtn.textContent = old;
    } catch (err) {
      showError(err.message || "Registration failed.");
    } finally {
      registerBtn.disabled = epcs.length === 0;
      registerBtn.textContent = "Register";
    }
  }

  function openModal() {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");

    // reset scan session
    epcs = [];
    render();
    hideMsg();

    // set scan input constraints
    if (scanInput) {
      scanInput.setAttribute("maxlength", String(EXACT));
      scanInput.autocomplete = "off";
      scanInput.spellcheck = false;
      scanInput.value = "";
    }

    // start scanning immediately (best UX)
    setScan(true);
  }

  function closeModal() {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    setScan(false);
  }

  // Wire up modal
  btnGenerate.addEventListener("click", openModal);
  backdrop?.addEventListener("click", closeModal);
  closeBtn?.addEventListener("click", closeModal);

  toggleScanBtn?.addEventListener("click", () => setScan(!scanning));
  registerBtn?.addEventListener("click", registerAll);

  // Bind wedge input events ✅ (this is the main fix)
  if (scanInput) {
    scanInput.addEventListener("input", onScanInput);
    scanInput.addEventListener("keydown", onScanKeyDown);
  }

  // keep focus while scanning if user clicks inside modal
  modal.addEventListener("mousedown", () => {
    if (scanning) scanInput?.focus({ preventScroll: true });
  });

  // Escape closes
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) closeModal();
  });

  render();
})();
