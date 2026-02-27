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
  const sumTotalAmount = document.getElementById("sumTotalAmount"); // modal total

  // Amount field
  const amountInput = document.getElementById("amount");
  const approxAmountDisplay = document.getElementById("approxAmount");

  // In-memory rows
  let rows = [];

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

  function setEmptyState() {
    if (!emptyState) return;
    emptyState.style.display = rows.length ? "none" : "flex";
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

  function formatMulti(list) {
    const cleaned = list.filter(Boolean);
    if (!cleaned.length) return "-";
    if (cleaned.length === 1) return cleaned[0];
    return `${cleaned[0]}.....+${cleaned.length - 1}`;
  }

  function formatDateReadable(iso) {
    if (!iso || typeof iso !== "string" || iso.length < 10) return "-";
    const [y, m, d] = iso.split("-");
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${d} ${monthNames[Number(m)-1] || m} ${y}`;
  }

  // ---------- Warehouse ID sync ----------
  function syncWarehouseId() {
    const opt = warehouseSelect?.selectedOptions?.[0];
    if (!opt) return;
    const id = opt.dataset.id || "";
    warehouseIdInput.value = id;
    warehouseSelect.dataset.selectedId = id;
    updateApproxAmountForInput();
  }

  // ---------- Crop sync ----------
  function syncFromId() {
    if (!cropIdSelect || !cropNameSelect) return;
    const opt = cropIdSelect.selectedOptions[0];
    const name = opt?.dataset?.name;
    if (!name) return;
    [...cropNameSelect.options].forEach(o => o.selected = o.value === name);
    updateApproxAmountForInput();
  }

  function syncFromName() {
    if (!cropIdSelect || !cropNameSelect) return;
    const opt = cropNameSelect.selectedOptions[0];
    const id = opt?.dataset?.id;
    if (!id) return;
    [...cropIdSelect.options].forEach(o => o.selected = o.value === id);
    updateApproxAmountForInput();
  }

  // ---------- Calculate per-crop amount ----------
  function calculateCropAmount(qty) {
    const warehouseId = warehouseSelect?.dataset?.selectedId;
    const duration = Number(storageDuration?.value || 0);
    if (!window.warehouses || !Array.isArray(window.warehouses)) return 0;
    if (!warehouseId || duration <= 0 || !qty) return 0;

    const warehouse = window.warehouses.find(
      w => String(w.userId) === String(warehouseId) || String(w.warehouseId) === String(warehouseId)
    );
    if (!warehouse || !warehouse.storage_services || warehouse.storage_services.length === 0) return 0;
    const rate = parseFloat(warehouse.storage_services[0].rate_per_kg_day || 0);
    return (qty * duration * rate).toFixed(2);
  }

  // ---------- Calculate total amount ----------
  function calculateApproxAmount() {
    let total = 0;
    rows.forEach(r => total += Number(calculateCropAmount(r.quantity)) || 0);
    return total.toFixed(2);
  }

  function updateApproxAmountForInput() {
    const qty = Number(cropQty?.value || 0);
    const amount = calculateCropAmount(qty);
    if (approxAmountDisplay) approxAmountDisplay.textContent = amount ? `₹ ${amount}` : "-";
    if (amountInput) amountInput.value = amount || "";
  }

  // ---------- Render table ----------
// ---------- Render table with total ----------
function renderTable() {
  if (!tbody) return;
  tbody.innerHTML = "";

  let total = 0;
  rows.forEach((r, idx) => {
    const cropAmount = calculateCropAmount(r.quantity);
    total += Number(cropAmount) || 0;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.cropId)}</td>
      <td>${escapeHtml(r.cropName)}</td>
      <td>${escapeHtml(String(r.quantity))} kg</td>
      <td>${escapeHtml(r.packaging)}</td>
      <td>₹ ${cropAmount}</td>
      <td>
        <button type="button" class="row-delete-btn" data-idx="${idx}">Remove</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Add total row at bottom of table
  const totalTr = document.createElement("tr");
  totalTr.innerHTML = `
    <td colspan="4" style="text-align:right; font-weight:bold;">Total Amount</td>
    <td colspan="2" style="font-weight:bold;">₹ ${total.toFixed(2)}</td>
  `;
  tbody.appendChild(totalTr);

  if (sumTotalAmount) sumTotalAmount.textContent = total ? `₹ ${total.toFixed(2)}` : "-";

  tbody.querySelectorAll(".row-delete-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const i = Number(btn.dataset.idx);
      if (!Number.isNaN(i)) {
        rows.splice(i, 1);
        rebuildHiddenInputs();
        renderTable();
        setEmptyState();
        updateApproxAmountForInput();
      }
    });
  });
}

  // ---------- Hidden inputs ----------
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

    rows.push({ cropId: cid, cropName: cname, quantity: qty, packaging: pack, bags, moisture });
    rebuildHiddenInputs();
    renderTable();
    setEmptyState();

    cropQty.value = "";
    bagCount.value = "";
    moisture.value = "";

    updateApproxAmountForInput();
    return { ok: true };
  }

  // ---------- Build Summary ----------
function buildSummary() {
  const wname = warehouseSelect?.value || "";
  const wid = warehouseIdInput?.value || "";
  const dateVal = storageDate?.value || "";
  const durVal = storageDuration?.value || "";

  if (!wid || !wname) return { ok: false, error: "Please select a warehouse." };
  if (!dateVal) return { ok: false, error: "Please select a date." };
  if (!durVal) return { ok: false, error: "Please select storage duration." };
  if (rows.length === 0) return { ok: false, error: "Please click 'Add Crop to Storage' before submitting." };

  const cropNames = rows.map(r => r.cropName);
  const packTypes = rows.map(r => r.packaging);

  sumWarehouse.textContent = wname;
  sumCrop.textContent = formatMulti(cropNames);
  sumPackaging.textContent = formatMulti(packTypes);
  sumDate.textContent = formatDateReadable(dateVal);

  // Show duration like "7+10" if multiple crops
  const durations = rows.map(_ => durVal); // assuming all crops use same storageDuration input
  sumDuration.textContent = durations.join("+");

  // Total amount
  const totalAmount = calculateApproxAmount();
  if (sumTotalAmount) sumTotalAmount.textContent = totalAmount ? `₹ ${totalAmount}` : "-";

  return { ok: true };
}

  // ---------- Event listeners ----------
  document.addEventListener("DOMContentLoaded", () => {
    setEmptyState();
    syncWarehouseId();
  });

  if (warehouseSelect) warehouseSelect.addEventListener("change", () => { syncWarehouseId(); updateApproxAmountForInput(); });
  if (storageDuration) storageDuration.addEventListener("change", updateApproxAmountForInput);
  if (cropQty) cropQty.addEventListener("input", updateApproxAmountForInput);
  if (cropIdSelect) cropIdSelect.addEventListener("change", syncFromId);
  if (cropNameSelect) cropNameSelect.addEventListener("change", syncFromName);

  if (btnAdd) btnAdd.addEventListener("click", () => {
    const res = addRowFromInputs();
    if (!res.ok) alert(res.error);
  });

  if (btnOpenSummary) btnOpenSummary.addEventListener("click", () => {
    clearError();
    const res = buildSummary();
    if (!res.ok) {
      showError(res.error);
      return;
    }
    openModal();
  });

  if (btnEdit) btnEdit.addEventListener("click", closeModal);
  if (backdrop) backdrop.addEventListener("click", closeModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal?.classList.contains("open")) closeModal();
  });

  if (btnConfirm) btnConfirm.addEventListener("click", async (e) => {
    e.preventDefault();
    clearError();
    rebuildHiddenInputs();

    try {
      const formData = new FormData(form);
      const res = await fetch(form.action, { method: "POST", body: formData });
      if (!res.ok) {
        showError("Failed to save: please check your data.");
        return;
      }

      closeModal();

      const successState = document.getElementById("storageSummarySuccess");
      if (successState) successState.style.display = "block";
    } catch (err) {
      showError("Unable to submit form. Please try again.");
      console.error(err);
    }
  });
})();