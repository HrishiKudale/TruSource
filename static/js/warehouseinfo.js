// static/js/warehouseinfo.js
// Features added:
// 1) Auto-select first crop + preload right panel
// 2) Highlight active crop in list
// 3) Search within stored crops list
// 4) Smooth switch animation
// 5) "Your Batches Here" count auto-update (if element exists)
// 6) Download / Export inventory JSON (client-side)
// 7) Robust image path support: /static/images/crops/<filename>

(function () {
  // ---------- Helpers ----------
  function $(id) {
    return document.getElementById(id);
  }

  function safeJsonParse(str) {
    try {
      return JSON.parse(str);
    } catch (e) {
      return null;
    }
  }

  function sectionText(obj) {
    const section = obj.section || obj.storage_section || obj.rack || "";
    const rack = obj.rack || obj.storage_rack || "";
    const slot = obj.slot || obj.storage_slot || "";
    const parts = [];
    if (section) parts.push(section);
    if (rack) parts.push(rack);
    if (slot) parts.push(slot);
    return parts.length ? parts.join(" — ") : "-";
  }

  function resolveImage(obj) {
    // Full URL/path already
    if (obj.imageUrl) return obj.imageUrl;
    if (obj.image_url) return obj.image_url;

    // Filename-only stored
    if (obj.image) return `/static/images/crops/${obj.image}`;
    if (obj.image_name) return `/static/images/crops/${obj.image_name}`;
    if (obj.cropImage) return `/static/images/crops/${obj.cropImage}`;

    return "/static/img/icon-placeholder.svg";
  }

  function normalizeCrop(obj) {
    // Make sure we can read consistent keys in UI
    return {
      raw: obj,
      cropId: obj.cropId || obj.crop_id || obj.cropID || "-",
      cropType: obj.cropType || obj.crop_type || obj.cropName || obj.crop_name || "-",
      storedOn: obj.storedOn || obj.stored_on || obj.stored_date || obj.storageDate || "-",
      quantityKg:
        obj.quantityKg ??
        obj.quantity_kg ??
        obj.quantity ??
        obj.stored_quantity ??
        obj.storedQuantity ??
        "-",
      linkedOrder: obj.linkedOrder || obj.linked_order_id || obj.order_id || obj.orderId || "-",
      linkedShipment:
        obj.linkedShipment || obj.linked_shipment_id || obj.shipment_id || obj.shipmentId || "-",
      image: resolveImage(obj),
      section: sectionText(obj),
    };
  }

  function downloadJson(filename, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // ---------- DOM ----------
  const cropItemsWrap = $("cropItems");      // list container
  const cropDetail = $("cropDetail");        // detail container

  // detail fields
  const dCropId = $("dCropId");
  const dCropType = $("dCropType");
  const dStoredOn = $("dStoredOn");
  const dSection = $("dSection");
  const dQty = $("dQty");
  const dOrder = $("dOrder");
  const dShipment = $("dShipment");

  // optional if you add an <img id="dImg"> in right panel later
  const dImg = $("dImg");

  // optional if you add these in HTML
  const batchesCountEl = $("batchesActiveCount"); // e.g. <span id="batchesActiveCount">0</span>
  const searchInput = $("cropSearch");            // e.g. <input id="cropSearch" ...>
  const exportBtn = $("exportInventoryBtn");      // e.g. <button id="exportInventoryBtn">

  if (!cropItemsWrap) return;

  // ---------- State ----------
  let crops = [];
  let activeIndex = -1;

  // Build crops list from DOM buttons
  const buttons = Array.from(cropItemsWrap.querySelectorAll(".crop-item"));

  crops = buttons
    .map((btn) => {
      const json = btn.getAttribute("data-crop");
      const obj = safeJsonParse(json);
      if (!obj) return null;
      return { btn, item: normalizeCrop(obj) };
    })
    .filter(Boolean);

  // ---------- UI Actions ----------
  function setActive(index) {
    if (index < 0 || index >= crops.length) return;

    // remove old
    if (activeIndex >= 0 && crops[activeIndex]) {
      crops[activeIndex].btn.classList.remove("active");
    }

    activeIndex = index;
    const { btn, item } = crops[index];
    btn.classList.add("active");

    render(item);

    // ensure active item visible in scroll list
    btn.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function render(item) {
    if (!item) return;

    // smooth fade animation
    if (cropDetail) {
      cropDetail.classList.remove("fade-in");
      // force reflow
      void cropDetail.offsetWidth;
      cropDetail.classList.add("fade-in");
    }

    if (dImg) dImg.src = item.image;

    if (dCropId) dCropId.textContent = item.cropId;
    if (dCropType) dCropType.textContent = item.cropType;
    if (dStoredOn) dStoredOn.textContent = item.storedOn;
    if (dSection) dSection.textContent = item.section;
    if (dQty) dQty.textContent = `${item.quantityKg} kg`;
    if (dOrder) dOrder.textContent = item.linkedOrder;
    if (dShipment) dShipment.textContent = item.linkedShipment;
  }

  function updateBatchesCount() {
    // “Your Batches Here” should be number of stored crop entries shown
    if (!batchesCountEl) return;

    // count only visible rows after search filter
    const visible = crops.filter(({ btn }) => btn.style.display !== "none").length;
    batchesCountEl.textContent = String(visible);
  }

  function applySearchFilter(q) {
    const query = (q || "").trim().toLowerCase();
    crops.forEach(({ btn, item }) => {
      const hay = `${item.cropId} ${item.cropType} ${item.linkedOrder} ${item.linkedShipment}`.toLowerCase();
      btn.style.display = !query || hay.includes(query) ? "" : "none";
    });

    updateBatchesCount();

    // if active item is hidden, select first visible
    if (activeIndex >= 0 && crops[activeIndex] && crops[activeIndex].btn.style.display === "none") {
      const firstVisible = crops.findIndex(({ btn }) => btn.style.display !== "none");
      if (firstVisible >= 0) setActive(firstVisible);
    }

    // if nothing active yet, select first visible
    if (activeIndex === -1) {
      const firstVisible = crops.findIndex(({ btn }) => btn.style.display !== "none");
      if (firstVisible >= 0) setActive(firstVisible);
    }
  }

  // ---------- Wire events ----------
  crops.forEach(({ btn }, idx) => {
    btn.addEventListener("click", () => setActive(idx));
  });

  // Add search support
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      applySearchFilter(e.target.value);
    });
  }

  // Add export support (downloads the currently visible crops)
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const visibleItems = crops
        .filter(({ btn }) => btn.style.display !== "none")
        .map(({ item }) => item.raw);

      const fileName = `warehouse_inventory_${new Date().toISOString().slice(0, 10)}.json`;
      downloadJson(fileName, { items: visibleItems });
    });
  }

  // ---------- Initial load ----------
  // If no crops, ensure batches count is 0
  if (!crops.length) {
    updateBatchesCount();
    return;
  }

  // Update count and auto-select first visible crop
  updateBatchesCount();
  const firstVisible = crops.findIndex(({ btn }) => btn.style.display !== "none");
  if (firstVisible >= 0) setActive(firstVisible);

  // In case you want the search filter to run on initial value (e.g. preserved input)
  if (searchInput && searchInput.value) {
    applySearchFilter(searchInput.value);
  }

})();
