// static/addshipment.js

document.addEventListener("DOMContentLoaded", () => {

  // =========================================================
  // 0) TEXTAREA AUTOGROW
  // =========================================================
  document.querySelectorAll("textarea").forEach(txt => {
    const resize = () => {
      txt.style.height = "auto";
      txt.style.height = txt.scrollHeight + "px";
    };
    txt.addEventListener("input", resize);
    resize();
  });

  // =========================================================
  // 1) TRANSPORTER MODE TOGGLE
  // =========================================================
  const transporterRadios = document.querySelectorAll("input[name='transporter_mode']");
  const platformOnlyBlock = document.querySelector(".transporter-platform-only");
  const personalOnlyBlock = document.querySelector(".transporter-personal-only");

  function updateTransporterMode() {
    let mode = "platform";
    transporterRadios.forEach(r => { if (r.checked) mode = r.value; });

    if (mode === "platform") {
      platformOnlyBlock?.classList.remove("hidden");
      personalOnlyBlock?.classList.add("hidden");
    } else {
      platformOnlyBlock?.classList.add("hidden");
      personalOnlyBlock?.classList.remove("hidden");
    }
  }
  transporterRadios.forEach(r => r.addEventListener("change", updateTransporterMode));
  updateTransporterMode();

  // =========================================================
  // 2) INSURANCE TOGGLE
  // =========================================================
  const insuranceToggle = document.getElementById("insuranceToggle");
  const insuranceFields = document.getElementById("insuranceFields");

  function updateInsuranceFields() {
    if (!insuranceToggle || !insuranceFields) return;
    if (insuranceToggle.checked) insuranceFields.classList.remove("hidden");
    else insuranceFields.classList.add("hidden");
  }
  if (insuranceToggle && insuranceFields) {
    insuranceToggle.addEventListener("change", updateInsuranceFields);
    updateInsuranceFields();
  }

  // =========================================================
  // 3) MAIN SHIPMENT TABLE HELPERS
  // =========================================================
  const shipmentTableBody = document.getElementById("shipmentItemsTableBody");
  const shipmentEmptyRow  = document.getElementById("shipmentItemsEmptyRow");

  // prevent duplicates for orders (optional but recommended)
  const addedOrderIds = new Set();

  function ensureShipmentEmptyState() {
    if (!shipmentTableBody || !shipmentEmptyRow) return;
    const realRows = Array.from(shipmentTableBody.querySelectorAll("tr"))
      .filter(tr => tr.id !== "shipmentItemsEmptyRow");
    if (realRows.length === 0 && shipmentEmptyRow.parentNode !== shipmentTableBody) {
      shipmentTableBody.appendChild(shipmentEmptyRow);
    }
  }

  function removeEmptyRowIfPresent() {
    if (shipmentEmptyRow && shipmentEmptyRow.parentNode === shipmentTableBody) {
      shipmentEmptyRow.remove();
    }
  }

  // ✅ single source of truth for adding rows
  function addShipmentRow({ orderId="", orderDate="", cropId="", cropName="", quantity="" }) {
    if (!shipmentTableBody) return;

    removeEmptyRowIfPresent();

    const tr = document.createElement("tr");

    // display values
    const showOrderId = orderId || "-";
    const showOrderDate = orderDate || "-";
    const showCropName = cropName || "-";
    const showQty = quantity || "-";

    tr.innerHTML = `
      <td>
        ${showOrderId}
        <input type="hidden" name="items_order_id[]" value="${orderId}">
      </td>
      <td>
        ${showOrderDate}
        <input type="hidden" name="items_order_date[]" value="${orderDate}">
      </td>
      <td>
        ${showCropName}
        <input type="hidden" name="items_crop_id[]" value="${cropId}">
        <input type="hidden" name="items_crop_name[]" value="${cropName}">
      </td>
      <td>
        ${showQty}
        <input type="hidden" name="items_quantity[]" value="${quantity}">
      </td>
      <td>
        <button type="button" class="table-action-btn table-remove-row">Remove</button>
      </td>
    `;

    shipmentTableBody.appendChild(tr);
  }

  // Remove row
  if (shipmentTableBody) {
    shipmentTableBody.addEventListener("click", (e) => {
      const btn = e.target.closest(".table-remove-row");
      if (!btn) return;

      const row = btn.closest("tr");
      if (!row) return;

      // if it was an order row, remove from duplicate set
      const hiddenOrder = row.querySelector('input[name="items_order_id[]"]');
      if (hiddenOrder?.value) addedOrderIds.delete(hiddenOrder.value);

      row.remove();
      ensureShipmentEmptyState();
    });
  }

  // =========================================================
  // 4) MODAL OPEN + TABS + ADD BUTTONS
  // =========================================================
  const modal         = document.getElementById("addShipmentModal");
  const modalBackdrop = modal?.querySelector(".shipment-modal-backdrop");
  const modalCloseBtn = document.getElementById("closeShipmentModal");
  const modalDoneBtn  = document.getElementById("modalDoneBtn");
  const modalResetBtn = document.getElementById("modalResetBtn");
  const openModalBtn  = document.getElementById("openShipmentModalBtn");

  function openModal()  { modal?.classList.add("open"); }
  function closeModal() { modal?.classList.remove("open"); }

  if (modal) openModal(); // open on page load

  openModalBtn?.addEventListener("click", openModal);
  modalBackdrop?.addEventListener("click", closeModal);
  modalCloseBtn?.addEventListener("click", closeModal);
  modalDoneBtn?.addEventListener("click", closeModal);

  modalResetBtn?.addEventListener("click", () => {
    if (!modal) return;

    modal.querySelectorAll("select").forEach(sel => sel.selectedIndex = 0);
    modal.querySelectorAll("input").forEach(inp => {
      if (!["button","submit","checkbox","radio"].includes(inp.type)) inp.value = "";
    });

    const orderBody  = document.getElementById("modalOrderTableBody");
    const cropBody   = document.getElementById("modalCropTableBody");
    const orderEmpty = document.getElementById("modalOrderEmptyRow");
    const cropEmpty  = document.getElementById("modalCropEmptyRow");

    if (orderBody && orderEmpty) { orderBody.innerHTML = ""; orderBody.appendChild(orderEmpty); }
    if (cropBody  && cropEmpty)  { cropBody.innerHTML  = ""; cropBody.appendChild(cropEmpty); }
  });

  // Tabs
  const modalTabButtons = document.querySelectorAll(".shipment-modal-tab");
  const modalTabPanels  = document.querySelectorAll(".shipment-modal-tabpanel");

  function activateTab(tabId) {
    modalTabButtons.forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tabId));
    modalTabPanels.forEach(panel => panel.classList.toggle("active", panel.id === tabId));
  }
  modalTabButtons.forEach(btn => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));

  // =========================
  // ORDER TAB ADD
  // =========================
  const modalOrderSelect   = document.getElementById("modalOrderSelect");
  const modalAddOrderBtn   = document.getElementById("modalAddOrderBtn");
  const modalOrderBody     = document.getElementById("modalOrderTableBody");
  const modalOrderEmptyRow = document.getElementById("modalOrderEmptyRow");

  modalAddOrderBtn?.addEventListener("click", () => {
    if (!modalOrderSelect || !modalOrderBody) return;
    const opt = modalOrderSelect.options[modalOrderSelect.selectedIndex];
    if (!opt || !opt.value) return alert("Please select an order first.");

    const orderId   = opt.value;
    const cropName  = opt.getAttribute("data-crop") || "-";
    const cropId    = opt.getAttribute("data-crop-id") || "";
    const quantity  = opt.getAttribute("data-quantity") || "-";
    const orderDate = opt.getAttribute("data-date") || "-";

    // ✅ prevent duplicate orders
    if (addedOrderIds.has(orderId)) {
      return alert("This order is already added in the shipment table.");
    }
    addedOrderIds.add(orderId);

    // add row to modal preview table
    if (modalOrderEmptyRow && modalOrderEmptyRow.parentNode === modalOrderBody) {
      modalOrderEmptyRow.remove();
    }
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${orderId}</td><td>${cropName}</td><td>${quantity}</td>`;
    modalOrderBody.appendChild(tr);

    // ✅ add row to MAIN table (correct mapping)
    addShipmentRow({
      orderId,
      orderDate,
      cropId,
      cropName,
      quantity
    });

    ensureShipmentEmptyState();
  });

  // =========================
  // CROP TAB ADD
  // =========================
  const modalCropIdSelect      = document.getElementById("modalCropIdSelect");
  const modalCropQtyInput      = document.getElementById("modalCropQuantityInput");
  const modalCropAvailableHint = document.getElementById("modalCropAvailableHint");
  const modalAddCropBtn        = document.getElementById("modalAddCropBtn");
  const modalCropBody          = document.getElementById("modalCropTableBody");
  const modalCropEmptyRow      = document.getElementById("modalCropEmptyRow");

  modalCropIdSelect?.addEventListener("change", () => {
    if (!modalCropAvailableHint || !modalCropIdSelect) return;
    const opt = modalCropIdSelect.options[modalCropIdSelect.selectedIndex];
    if (!opt || !opt.value) return (modalCropAvailableHint.textContent = "");
    const available = opt.getAttribute("data-available");
    const name      = opt.getAttribute("data-name") || "";
    modalCropAvailableHint.textContent = available ? `Available: ${available} kg for ${name}` : "";
  });

  modalAddCropBtn?.addEventListener("click", () => {
    if (!modalCropIdSelect || !modalCropQtyInput || !modalCropBody) return;
    const opt = modalCropIdSelect.options[modalCropIdSelect.selectedIndex];
    if (!opt || !opt.value) return alert("Please select a crop ID first.");

    const cropId   = opt.value;
    const cropName = opt.getAttribute("data-name") || "-";
    const qtyRaw   = (modalCropQtyInput.value || "").trim();

    if (!qtyRaw) return alert("Please enter quantity.");
    const qty = Number(qtyRaw);
    if (Number.isNaN(qty) || qty <= 0) return alert("Quantity must be a valid number greater than 0.");

    // add row to modal preview table
    if (modalCropEmptyRow && modalCropEmptyRow.parentNode === modalCropBody) {
      modalCropEmptyRow.remove();
    }
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${cropId}</td><td>${cropName}</td><td>${qty}</td>`;
    modalCropBody.appendChild(tr);

    // ✅ add row to MAIN table (order fields empty, crop fields filled)
    addShipmentRow({
      orderId: "",
      orderDate: "",
      cropId,
      cropName,
      quantity: String(qty)
    });

    modalCropQtyInput.value = "";
    ensureShipmentEmptyState();
  });


  // =========================================================
  // 5) CUSTOM SEARCHABLE DROPDOWN (.sd)
  // =========================================================
  function closeAllDropdowns(except = null) {
    document.querySelectorAll(".sd.open").forEach(sd => {
      if (sd !== except) {
        sd.classList.remove("open");
        sd.querySelector(".sd-control")?.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.querySelectorAll(".sd").forEach(sd => {
    const control  = sd.querySelector(".sd-control");
    const search   = sd.querySelector(".sd-search-input");
    const hidden   = sd.querySelector(".sd-hidden");
    const hiddenId = sd.querySelector(".sd-hidden-id");
    const label    = sd.querySelector(".sd-placeholder");
    const options  = Array.from(sd.querySelectorAll(".sd-option"));

    if (!control || !hidden || !label) return;

    control.addEventListener("click", (e) => {
      e.preventDefault();
      const willOpen = !sd.classList.contains("open");
      closeAllDropdowns(sd);

      sd.classList.toggle("open", willOpen);
      control.setAttribute("aria-expanded", willOpen ? "true" : "false");

      if (willOpen && search) {
        search.value = "";
        options.forEach(o => (o.style.display = ""));
        setTimeout(() => search.focus(), 0);
      }
    });

    options.forEach(opt => {
      opt.addEventListener("click", () => {
        const val = opt.dataset.value || "";
        const id  = opt.dataset.id || "";

        hidden.value = val;
        if (hiddenId) hiddenId.value = id;

        label.textContent = val || "Select";
        label.style.color = "var(--grey-900)";

        sd.dispatchEvent(new CustomEvent("sd:change", { detail: { opt } }));

        sd.classList.remove("open");
        control.setAttribute("aria-expanded", "false");
      });
    });

    if (search) {
      search.addEventListener("input", () => {
        const q = search.value.trim().toLowerCase();
        options.forEach(opt => {
          const text = (opt.textContent || "").toLowerCase();
          opt.style.display = text.includes(q) ? "" : "none";
        });
      });
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".sd")) closeAllDropdowns();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllDropdowns();
  });

  // =========================================================
  // 6) SD CROSS SYNC (Pickup + Deliver)
  // =========================================================
  function setSD(sdEl, labelText, value, idValue = "") {
    if (!sdEl) return;
    const label   = sdEl.querySelector(".sd-placeholder");
    const hidden  = sdEl.querySelector(".sd-hidden");
    const hiddenId= sdEl.querySelector(".sd-hidden-id");

    if (label) {
      label.textContent = labelText || "Select";
      label.style.color = "var(--grey-900)";
    }
    if (hidden) hidden.value = value || "";
    if (hiddenId) hiddenId.value = idValue || "";
  }

  function findOption(sdEl, predicateFn) {
    if (!sdEl) return null;
    const options = Array.from(sdEl.querySelectorAll(".sd-option"));
    return options.find(predicateFn) || null;
  }

  // PICKUP
  const pickupFromSD      = document.getElementById("pickupFromSD");
  const pickupIdSD        = document.getElementById("pickupIdSD");
  const pickupNameInput   = document.getElementById("pickupNameInput");
  const pickupLocationInp = document.getElementById("pickupLocationInput");

  pickupFromSD?.addEventListener("sd:change", (e) => {
    const opt = e.detail?.opt;
    if (!opt) return;

    const name = opt.dataset.value || "";
    const id   = opt.dataset.id || "";
    const loc  = opt.dataset.location || "";

    const idOpt = findOption(pickupIdSD, o => (o.dataset.value || "") === id);
    if (idOpt) setSD(pickupIdSD, id, id, id);

    pickupNameInput && (pickupNameInput.value = name);
    pickupLocationInp && (pickupLocationInp.value = loc);

    pickupFromSD.querySelector(".sd-hidden-id")?.setAttribute("value", id);
  });

  pickupIdSD?.addEventListener("sd:change", (e) => {
    const opt = e.detail?.opt;
    if (!opt) return;

    const id   = opt.dataset.value || "";
    const name = opt.dataset.name || "";
    const loc  = opt.dataset.location || "";

    const fromOpt = findOption(pickupFromSD, o => (o.dataset.value || "") === name);
    if (fromOpt) setSD(pickupFromSD, name, name, id);

    pickupNameInput && (pickupNameInput.value = name);
    pickupLocationInp && (pickupLocationInp.value = loc);

    const pfHiddenId = pickupFromSD?.querySelector(".sd-hidden-id");
    if (pfHiddenId) pfHiddenId.value = id;
  });

  // DELIVER
  const deliverToSD        = document.getElementById("deliverToSD");
  const deliverIdSD        = document.getElementById("deliverIdSD");
  const deliverNameInput   = document.getElementById("deliverNameInput");
  const deliverLocationInp = document.getElementById("deliverLocationInput");

  deliverToSD?.addEventListener("sd:change", (e) => {
    const opt = e.detail?.opt;
    if (!opt) return;

    const name = opt.dataset.value || "";
    const id   = opt.dataset.id || "";
    const loc  = opt.dataset.location || "";

    const idOpt = findOption(deliverIdSD, o => (o.dataset.value || "") === id);
    if (idOpt) setSD(deliverIdSD, id, id, id);

    deliverNameInput && (deliverNameInput.value = name);
    deliverLocationInp && (deliverLocationInp.value = loc);

    const dtHiddenId = deliverToSD?.querySelector(".sd-hidden-id");
    if (dtHiddenId) dtHiddenId.value = id;
  });

  deliverIdSD?.addEventListener("sd:change", (e) => {
    const opt = e.detail?.opt;
    if (!opt) return;

    const id   = opt.dataset.value || "";
    const name = opt.dataset.name || "";
    const loc  = opt.dataset.location || "";

    const toOpt = findOption(deliverToSD, o => (o.dataset.value || "") === name);
    if (toOpt) setSD(deliverToSD, name, name, id);

    deliverNameInput && (deliverNameInput.value = name);
    deliverLocationInp && (deliverLocationInp.value = loc);

    const dtHiddenId = deliverToSD?.querySelector(".sd-hidden-id");
    if (dtHiddenId) dtHiddenId.value = id;
  });

});


document.addEventListener("DOMContentLoaded", function () {

  const form = document.getElementById("shipmentForm");
  const submitBtn = document.querySelector('.send-request-btn'); // Create Shipment button

  // Modal
  const modal = document.getElementById("shipmentSummaryModal");
  const backdrop = document.getElementById("shipmentSummaryBackdrop");
  const review = document.getElementById("shipmentSummaryReview");
  const success = document.getElementById("shipmentSummarySuccess");

  const btnEdit = document.getElementById("btnShipmentEdit");
  const btnConfirm = document.getElementById("btnShipmentConfirm");
  const errEl = document.getElementById("shipmentSummaryError");

  // Summary values
  const sumTransporter = document.getElementById("sumTransporter");
  const sumPickupDate = document.getElementById("sumPickupDate");
  const sumDeliveryDate = document.getElementById("sumDeliveryDate");
  const sumTotalOrders = document.getElementById("sumTotalOrders");
  const sumFinalPrice = document.getElementById("sumFinalPrice");

  if (!form || !submitBtn || !modal) return;

  function openModal() {
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function setError(msg) {
    if (!errEl) return;
    if (!msg) {
      errEl.style.display = "none";
      errEl.textContent = "";
    } else {
      errEl.style.display = "block";
      errEl.textContent = msg;
    }
  }

  function formatDatePretty(dateStr) {
    if (!dateStr) return "-";
    // input type=date gives YYYY-MM-DD
    const parts = dateStr.split("-");
    if (parts.length !== 3) return dateStr;
    const [y, m, d] = parts;
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const mm = Number(m);
    return `${d} ${months[mm - 1] || m} ${y}`;
  }

  function getTransporterName() {
    // Platform transporter dropdown hidden input name="transporter_name"
    // OR personal transporter input name="personal_transporter_name"
    const mode = form.querySelector('input[name="transporter_mode"]:checked')?.value;

    if (mode === "personal") {
      const p = form.querySelector('input[name="personal_transporter_name"]')?.value?.trim();
      return p || "-";
    }

    const t = form.querySelector('input[name="transporter_name"]')?.value?.trim();
    return t || "-";
  }

  function getPickupDate() {
    const v = form.querySelector('input[name="pickup_date"]')?.value;
    return formatDatePretty(v);
  }

  function getDeliveryDate() {
    const v = form.querySelector('input[name="delivery_date"]')?.value;
    return formatDatePretty(v);
  }

  function getFinalPrice() {
    // If you have an input for final price, use it.
    // Try common names:
    const possible = [
      'input[name="final_price"]',
      'input[name="price"]',
      'input[name="total_price"]',
      '#finalPriceInput'
    ];

    for (const sel of possible) {
      const el = form.querySelector(sel);
      if (el && el.value !== undefined) {
        const v = String(el.value).trim();
        if (v) return `₹ ${v}`;
      }
    }
    return "-";
  }
function getItemsCountSummary() {
  // Each row always has a quantity hidden input
  const qtyInputs = Array.from(document.querySelectorAll('input[name="items_quantity[]"]'));

  // Order rows: have items_order_id[] value
  const orderIds = Array.from(document.querySelectorAll('input[name="items_order_id[]"]'))
    .map(i => (i.value || "").trim());

  let ordersCount = 0;
  let cropsCount = 0;

  // qtyInputs length == number of rows
  qtyInputs.forEach((_, idx) => {
    const oid = orderIds[idx] || "";
    if (oid) ordersCount++;
    else cropsCount++;
  });

  const total = ordersCount + cropsCount;
  if (total === 0) return "-";

  // UI style: "1 item", "3 items (2 orders, 1 crop)"
  if (total === 1) {
    if (ordersCount === 1) return "1 order";
    return "1 crop";
  }

  // Your preferred style: show total like: "ORD-...+2" is possible too,
  // but for now this matches your requirement (total count)
  return `${total} items (${ordersCount} orders, ${cropsCount} crops)`;
}




function validateBeforeModal() {
  const deliveryDateRaw = form.querySelector('input[name="delivery_date"]')?.value;
  if (!deliveryDateRaw) return "Delivery date is required.";

  // ✅ Check real shipment items (order OR crop)
  const anyQty = form.querySelector('input[name="items_quantity[]"]');
  const hasAtLeastOneRow = !!anyQty;

  if (!hasAtLeastOneRow) {
    return "Please add at least 1 order/crop into Shipment Items.";
  }

  // ✅ Extra: ensure quantities are valid
  const qtyInputs = Array.from(form.querySelectorAll('input[name="items_quantity[]"]'));
  const badQty = qtyInputs.some(q => {
    const v = String(q.value || "").trim();
    if (!v) return true;
    const n = Number(v);
    return Number.isNaN(n) || n <= 0;
  });

  if (badQty) return "Please check shipment quantities (must be > 0).";

  return null;
}


  function fillSummary() {
    sumTransporter.textContent = getTransporterName();
    sumPickupDate.textContent = getPickupDate();
    sumDeliveryDate.textContent = getDeliveryDate();
    sumTotalOrders.textContent = getItemsCountSummary();
    sumFinalPrice.textContent = getFinalPrice();
  }

  // Intercept submit button click → open modal
  submitBtn.addEventListener("click", function (e) {
    e.preventDefault();

    // reset view
    if (review) review.style.display = "block";
    if (success) success.style.display = "none";

    const err = validateBeforeModal();
    if (err) {
      // you can show toast or simple alert
      alert(err);
      return;
    }

    setError(null);
    fillSummary();
    openModal();
  });

  // Close on backdrop
  if (backdrop) backdrop.addEventListener("click", closeModal);

  // Go back & edit
  if (btnEdit) btnEdit.addEventListener("click", closeModal);

  // Confirm → submit form
  if (btnConfirm) {
    btnConfirm.addEventListener("click", function () {
      setError(null);
      // submit normally (backend will redirect to listing page)
      form.submit();
    });
  }

});
