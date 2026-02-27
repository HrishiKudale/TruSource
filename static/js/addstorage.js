(function () {
  const form = document.getElementById("storeForm");

  // Warehouse
  const warehouseSelect = document.getElementById("warehouseSelect");
  const warehouseIdInput = document.getElementById("warehouseIdInput");

  // Crop inputs
  const cropIdSelect = document.getElementById("cropIdSelect");
  const cropNameSelect = document.getElementById("cropNameSelect");
  const cropQty = document.getElementById("cropQty");
  const packagingType = document.getElementById("packagingType");
  const bagCount = document.getElementById("bagCount");
  const moisture = document.getElementById("moisture");

  // Warehouse fields for summary
  const storageDate = document.getElementById("storageDate");
  const storageDuration = document.getElementById("storageDuration");

  // Table
  const tbody = document.getElementById("storageTbody");
  const emptyState = document.getElementById("storageEmptyState");
  const hiddenRows = document.getElementById("storageHiddenRows");

  // Buttons
  const btnAdd = document.getElementById("btnAddCropRow");
  const btnOpenSummary = document.getElementById("btnOpenStorageSummary");

  // Modal
  const modal = document.getElementById("storageSummaryModal");
  const backdrop = document.getElementById("storageSummaryBackdrop");
  const btnEdit = document.getElementById("btnStorageEdit");
  const btnConfirm = document.getElementById("btnStorageConfirm");
  const summaryError = document.getElementById("storageSummaryError");

  // Summary values
  const sumWarehouse = document.getElementById("sumWarehouse");
  const sumCrop = document.getElementById("sumCrop");
  const sumPackaging = document.getElementById("sumPackaging");
  const sumDate = document.getElementById("sumDate");
  const sumDuration = document.getElementById("sumDuration");

  // In-memory rows
  let rows = [];

  function setEmptyState() {
    if (!emptyState) return;
    emptyState.style.display = rows.length ? "none" : "flex";
  }

  // ---------- Warehouse auto ID ----------
  function syncWarehouseId() {
    const opt = warehouseSelect?.selectedOptions?.[0];
    if (warehouseIdInput) {
      warehouseIdInput.value = opt ? (opt.dataset.id || "") : "";
    }
  }

  // ---------- Crop sync ----------
  function syncFromId() {
    if (!cropIdSelect || !cropNameSelect) return;
    const opt = cropIdSelect.selectedOptions[0];
    const name = opt?.dataset?.name;
    if (!name) return;

    [...cropNameSelect.options].forEach(o => {
      if (o.value === name) o.selected = true;
    });
  }

  function syncFromName() {
    if (!cropIdSelect || !cropNameSelect) return;
    const opt = cropNameSelect.selectedOptions[0];
    const id = opt?.dataset?.id;
    if (!id) return;

    [...cropIdSelect.options].forEach(o => {
      if (o.value === id) o.selected = true;
    });
  }

  // ---------- Render table ----------
  function renderTable() {
    if (!tbody) return;
    tbody.innerHTML = "";

    rows.forEach((r, idx) => {
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td>${escapeHtml(r.cropId)}</td>
        <td>${escapeHtml(r.cropName)}</td>
        <td>${escapeHtml(String(r.quantity))} kg</td>
        <td>${escapeHtml(r.packaging)}</td>
        <td>
          <button type="button" class="row-delete-btn" data-idx="${idx}">Remove</button>
        </td>
      `;

      tbody.appendChild(tr);
    });

    // bind remove
    tbody.querySelectorAll(".row-delete-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const i = Number(btn.dataset.idx);
        if (!Number.isNaN(i)) {
          rows.splice(i, 1);
          rebuildHiddenInputs();
          renderTable();
          setEmptyState();
        }
      });
    });
  }

  // ---------- Hidden inputs for backend ----------
  function rebuildHiddenInputs() {
    if (!hiddenRows) return;
    hiddenRows.innerHTML = "";

    rows.forEach(r => {
      hiddenRows.insertAdjacentHTML("beforeend", `
        <input type="hidden" name="items_crop_id[]" value="${escapeAttr(r.cropId)}">
        <input type="hidden" name="items_crop_name[]" value="${escapeAttr(r.cropName)}">
        <input type="hidden" name="items_quantity[]" value="${escapeAttr(String(r.quantity))}">
        <input type="hidden" name="items_packaging_type[]" value="${escapeAttr(r.packaging)}">
        <input type="hidden" name="items_bags[]" value="${escapeAttr(String(r.bags || ""))}">
        <input type="hidden" name="items_moisture[]" value="${escapeAttr(String(r.moisture || ""))}">
      `);
    });
  }

  // ---------- Add row ----------
  function addRowFromInputs() {
    const cid = cropIdSelect?.value || "";
    const cname = cropNameSelect?.value || "";
    const qty = Number(cropQty?.value || 0);
    const pack = packagingType?.value || "";

    const bags = bagCount?.value || "";
    const moist = moisture?.value || "";

    if (!cid || !cname || !qty || qty <= 0 || !pack) {
      return { ok: false, error: "Please select Crop ID, Crop, Quantity and Packaging Type before adding." };
    }

    rows.push({
      cropId: cid,
      cropName: cname,
      quantity: qty,
      packaging: pack,
      bags,
      moisture: moist
    });

    rebuildHiddenInputs();
    renderTable();
    setEmptyState();

    // optional: reset crop inputs after add
    if (cropQty) cropQty.value = "";
    if (bagCount) bagCount.value = "";
    if (moisture) moisture.value = "";

    return { ok: true };
  }

  // ---------- Summary helpers ----------
  function formatMulti(list) {
    const cleaned = list.filter(Boolean);
    if (!cleaned.length) return "-";
    if (cleaned.length === 1) return cleaned[0];
    return `${cleaned[0]}.....+${cleaned.length - 1}`;
  }

  function formatDateReadable(iso) {
    // ISO yyyy-mm-dd -> dd Mon yyyy
    if (!iso || typeof iso !== "string" || iso.length < 10) return "-";
    const [y, m, d] = iso.split("-");
    if (!y || !m || !d) return iso;
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const mi = Number(m) - 1;
    const mn = monthNames[mi] || m;
    return `${d} ${mn} ${y}`;
  }

  function showError(msg) {
    if (!summaryError) return;
    summaryError.textContent = msg;
    summaryError.style.display = "block";
  }

  function clearError() {
    if (!summaryError) return;
    summaryError.textContent = "";
    summaryError.style.display = "none";
  }

  function openModal() {
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    clearError();
  }

  // ---------- Validate + Populate Summary ----------
function buildSummary() {
  const wname = warehouseSelect?.value || "";
  const wid = warehouseIdInput?.value || "";
  const dateVal = storageDate?.value || "";
  const durVal = storageDuration?.value || "";

  if (!wid || !wname) return { ok: false, error: "Please select a warehouse." };
  if (!dateVal) return { ok: false, error: "Please select a date." };
  if (!durVal) return { ok: false, error: "Please select storage duration." };

  // ✅ Require at least one crop row
  if (rows.length === 0) {
    return { ok: false, error: "Please click 'Add Crop to Storage' before submitting." };
  }

  const cropNames = rows.map(r => r.cropName);
  const packTypes = rows.map(r => r.packaging);

  sumWarehouse.textContent = wname;
  sumCrop.textContent = formatMulti(cropNames);
  sumPackaging.textContent = formatMulti(packTypes);
  sumDate.textContent = formatDateReadable(dateVal);
  sumDuration.textContent = durVal;

  return { ok: true };
}

  // ---------- Events ----------
  document.addEventListener("DOMContentLoaded", () => {
    setEmptyState();
    syncWarehouseId();
  });

  if (warehouseSelect) warehouseSelect.addEventListener("change", syncWarehouseId);
  if (cropIdSelect) cropIdSelect.addEventListener("change", syncFromId);
  if (cropNameSelect) cropNameSelect.addEventListener("change", syncFromName);

  if (btnAdd) {
    btnAdd.addEventListener("click", () => {
      const res = addRowFromInputs();
      if (!res.ok) {
        // light feedback; you can replace with toast
        alert(res.error);
      }
    });
  }

  if (btnOpenSummary) {
    btnOpenSummary.addEventListener("click", () => {
      clearError();
      const res = buildSummary();
      if (!res.ok) {
        // show error near modal, but also open modal so user sees context
        openModal();
        showError(res.error);
        return;
      }
      openModal();
    });
  }

  if (btnEdit) btnEdit.addEventListener("click", closeModal);
  if (backdrop) backdrop.addEventListener("click", closeModal);

  // ESC closes modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal?.classList.contains("open")) closeModal();
  });

  if (btnConfirm) {
    btnConfirm.addEventListener("click", () => {
      clearError();

      // Final sanity: ensure hidden inputs exist
      rebuildHiddenInputs();

      // Submit form
      try {
        form.submit();
      } catch (err) {
        showError("Unable to submit form. Please try again.");
      }
    });
  }

  // ---------- Utils ----------
  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replaceAll("`", "&#096;");
  }
})();
