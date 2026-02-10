(function () {
  // -------------------- SAFE HELPERS --------------------
  const byId = (id) => document.getElementById(id);

  // fallback: id -> name
  const getField = (id, name) => byId(id) || document.querySelector(`[name="${name}"]`);

  const setVal = (el, v) => {
    if (!el) return;
    el.value = (v === undefined || v === null) ? "" : String(v);
  };


  const getVal = (el) => (el && el.value != null) ? String(el.value).trim() : "";

  const getSelectText = (sel) => {
    if (!sel) return "";
    const opt = sel.selectedOptions && sel.selectedOptions[0];
    return opt ? (opt.textContent || "").trim() : (sel.value || "").trim();
  };

  const safeNumber = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };

  // Prefill styling hook:
  // CSS should define .is-prefilled { background: #f6f6f6 !important; }
  const markPrefilled = (el, yes) => {
    if (!el) return;
    if (yes) el.classList.add("is-prefilled");
    else el.classList.remove("is-prefilled");
  };

  async function safeFetchJSON(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const isJson = ct.includes("application/json");
    const data = isJson ? await res.json().catch(() => ({})) : null;
    return { res, data, isJson };
  }

  // -------------------- ELEMENTS --------------------
  const form = byId("orderForm");

  // order fields
  const orderIdEl   = getField("orderId", "order_id");
  const requestIdEl = getField("requestId", "request_id");
  const orderDateEl = getField("orderDate", "order_date");

  // buyer fields
  const buyerTypeEl   = getField("buyerType", "buyer_type");
  const buyerSelectEl = getField("buyerSelect", "buyer");

  const buyerAddressEl       = getField("buyerAddress", "address");
  const buyerContactPersonEl = getField("buyerContactPerson", "contact_person");
  const buyerContactEl       = getField("buyerContact", "contact");
  const buyerEmailEl         = getField("buyerEmail", "email");

  // crop fields
  const cropIdSelect   = getField("cropIdSelect", "crop_id");
  const cropTypeSelect = getField("cropTypeSelect", "crop");
  const quantityKgEl   = getField("quantityKg", "quantity");
  const priceEl        = getField("price", "price");
  const paymentTermsEl = getField("paymentTerms", "payment_terms");

  // pickup toggle
  const pickupTypeRadios = document.querySelectorAll(`input[name="pickupFromType"]`);
  const pickupWarehouseWrap = byId("pickupWarehouseWrap");
  const pickupFarmWrap = byId("pickupFarmWrap");
  const pickupWarehouseSelect = byId("pickupWarehouseSelect");
  const pickupFarmSelect = byId("pickupFarmSelect");
  const pickupDateEl = byId("pickupDate");
  const notesEl = byId("notes");

  // modal
  const modal     = byId("orderSummaryModal");
  const backdrop  = byId("orderSummaryBackdrop");
  const btnOpen   = byId("openOrderSummaryBtn");
  const btnEdit   = byId("btnOrderEdit");
  const btnConfirm= byId("btnOrderConfirm");

  const stateReview  = byId("orderSummaryReview");
  const stateSuccess = byId("orderSummarySuccess");
  const errEl        = byId("orderSummaryError");

  const setText = (id, val) => {
    const el = byId(id);
    if (!el) return;
    const t = (val && String(val).trim()) ? String(val).trim() : "-";
    el.textContent = t;
  };

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

  // -------------------- INIT: today + IDs --------------------
  async function initIdsAndDate() {
    try {
      // date default today
      if (orderDateEl && !getVal(orderDateEl)) {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const dd = String(d.getDate()).padStart(2, "0");
        setVal(orderDateEl, `${yyyy}-${mm}-${dd}`);
      }

      // OrderId
      if (orderIdEl && !getVal(orderIdEl)) {
        const { res, data } = await safeFetchJSON("/farmer/sales/api/generate_order_id");
        if (res.ok && data && data.orderId) setVal(orderIdEl, data.orderId);
      }

      // RequestId (optional endpoint)
      if (requestIdEl && !getVal(requestIdEl)) {
        try {
          const { res, data } = await safeFetchJSON("/farmer/sales/api/generate_request_id");
          if (res.ok && data && data.requestId) setVal(requestIdEl, data.requestId);
        } catch (_) {
          // endpoint may not exist yet -> ignore
        }
      }
    } catch (e) {
      console.error("initIdsAndDate failed:", e);
    }
  }

  // -------------------- PICKUP TOGGLE --------------------
  function initPickupToggle() {
    if (!pickupTypeRadios || pickupTypeRadios.length === 0) return;

    const setMode = (mode) => {
      const farm = mode === "farm";
      if (pickupWarehouseWrap) pickupWarehouseWrap.style.display = farm ? "none" : "";
      if (pickupFarmWrap) pickupFarmWrap.style.display = farm ? "" : "none";

      // clear other select so backend doesn't get wrong value
      if (farm) {
        if (pickupWarehouseSelect) pickupWarehouseSelect.value = "";
      } else {
        if (pickupFarmSelect) pickupFarmSelect.value = "";
      }
    };

    pickupTypeRadios.forEach(r => {
      r.addEventListener("change", () => setMode(r.value));
    });

    // initial
    const checked = document.querySelector(`input[name="pickupFromType"]:checked`);
    setMode(checked ? checked.value : "warehouse");
  }

  // -------------------- BUYER TYPE -> FILTER BUYERS --------------------
  function resetBuyerAutoFill() {
    setVal(buyerAddressEl, "");
    setVal(buyerContactPersonEl, "");
    setVal(buyerContactEl, "");
    setVal(buyerEmailEl, "");

    markPrefilled(buyerAddressEl, false);
    markPrefilled(buyerContactPersonEl, false);
    markPrefilled(buyerContactEl, false);
    markPrefilled(buyerEmailEl, false);
  }

  function filterBuyersByType() {
    if (!buyerSelectEl) return;

    const buyerType = getVal(buyerTypeEl).toLowerCase();
    buyerSelectEl.value = "";
    resetBuyerAutoFill();

    Array.from(buyerSelectEl.options).forEach(opt => {
      if (!opt.value) return; // placeholder
      const role = (opt.getAttribute("data-role") || "").toLowerCase();
      opt.hidden = buyerType ? (role !== buyerType) : false;
    });
  }

  // -------------------- BUYER SELECT -> AUTOFILL --------------------
  async function loadBuyerDetails() {
    clearError();
    const buyerId = getVal(buyerSelectEl);
    const buyerType = getVal(buyerTypeEl);
    if (!buyerId) return;

    try {
      const url = `/farmer/sales/api/buyer/${encodeURIComponent(buyerId)}?buyerType=${encodeURIComponent(buyerType)}`;
      const { res, data, isJson } = await safeFetchJSON(url);

      if (!res.ok) {
        const msg = (isJson && data && (data.error || data.message)) ? (data.error || data.message) : "Failed to fetch buyer details";
        throw new Error(msg);
      }

      // Fill + mark grey (prefilled)
      setVal(buyerAddressEl, data.address || "-");            markPrefilled(buyerAddressEl, true);
      setVal(buyerContactPersonEl, data.contactPerson || "-");markPrefilled(buyerContactPersonEl, true);
      setVal(buyerContactEl, data.phone || "-");              markPrefilled(buyerContactEl, true);
      setVal(buyerEmailEl, data.email || "-");                markPrefilled(buyerEmailEl, true);

    } catch (e) {
      console.error(e);
      showError(e.message);
    }
  }

  // -------------------- CROPS: sync id <-> type --------------------
  function syncCropFromId() {
    if (!cropIdSelect || !cropTypeSelect) return;
    const opt = cropIdSelect.selectedOptions && cropIdSelect.selectedOptions[0];
    const cropName = opt ? (opt.getAttribute("data-name") || "") : "";
    if (!cropName) return;

    for (let i = 0; i < cropTypeSelect.options.length; i++) {
      if (cropTypeSelect.options[i].value === cropName) {
        cropTypeSelect.selectedIndex = i;
        break;
      }
    }
  }

  function syncCropFromType() {
    if (!cropIdSelect || !cropTypeSelect) return;
    const opt = cropTypeSelect.selectedOptions && cropTypeSelect.selectedOptions[0];
    const id = opt ? (opt.getAttribute("data-id") || "") : "";
    if (!id) return;

    for (let i = 0; i < cropIdSelect.options.length; i++) {
      if (cropIdSelect.options[i].value === id) {
        cropIdSelect.selectedIndex = i;
        break;
      }
    }
  }

  // -------------------- PREFILL FROM farmer_request --------------------
  async function prefillFromRequestId(requestId) {
    if (!requestId) return;

    try {
      const { res, data, isJson } = await safeFetchJSON(`/farmer/sales/api/request/${encodeURIComponent(requestId)}`);
      if (!res.ok) {
        const msg = (isJson && data && (data.error || data.message)) ? (data.error || data.message) : "Request not found";
        throw new Error(msg);
      }

      // lock requestId if exists
      if (requestIdEl) {
        setVal(requestIdEl, requestId);
        markPrefilled(requestIdEl, true);
      }

      // crop prefill
      if (data.cropId && cropIdSelect) {
        cropIdSelect.value = data.cropId;
        syncCropFromId();
        markPrefilled(cropIdSelect, true);
      }
      if (data.cropType && cropTypeSelect) {
        cropTypeSelect.value = data.cropType;
        syncCropFromType();
        markPrefilled(cropTypeSelect, true);
      }
      if (data.quantityKg && quantityKgEl) {
        setVal(quantityKgEl, data.quantityKg);
        markPrefilled(quantityKgEl, true);
      }

      // buyer type + buyer prefill
      if (data.buyerType && buyerTypeEl) {
        setVal(buyerTypeEl, data.buyerType);
        markPrefilled(buyerTypeEl, true);
        filterBuyersByType();
      }
      if (data.buyerId && buyerSelectEl) {
        buyerSelectEl.value = data.buyerId;
        markPrefilled(buyerSelectEl, true);
        await loadBuyerDetails();
      }

      // pickup info (optional)
      // If your request returns pickupFromType + pickupLocationId, you can prefill here.
      // Example:
      // if (data.pickupFromType) { ... }
    } catch (e) {
      console.warn("Prefill skipped:", e.message);
      // no error popup on page-load; only console
    }
  }

  // -------------------- SUMMARY MODAL FILL --------------------
  function fillSummary() {
    const oid = getVal(orderIdEl) || "-";
    const rid = getVal(requestIdEl) || "-";

    const buyerType = getVal(buyerTypeEl) || "-";
    const buyer = getSelectText(buyerSelectEl) || "-";

    const cropType = getVal(cropTypeSelect) || "-";
    const cropId = getVal(cropIdSelect) || "-";

    const qty = getVal(quantityKgEl);
    const price = getVal(priceEl);
    const pay = getVal(paymentTermsEl) || "-";

    const total = safeNumber(qty) * safeNumber(price);

    // pickup summary (optional)
    let pickupFrom = "-";
    const mode = document.querySelector(`input[name="pickupFromType"]:checked`)?.value || "warehouse";
    if (mode === "farm") pickupFrom = getSelectText(pickupFarmSelect) || "-";
    else pickupFrom = getSelectText(pickupWarehouseSelect) || "-";

    setText("sumOrderId", oid);
    setText("sumRequestId", rid);

    setText("sumBuyerType", buyerType);
    setText("sumBuyer", buyer);

    setText("sumCrop", cropType);
    setText("sumCropId", cropId);

    setText("sumQty", qty ? `${qty} Kg` : "-");
    setText("sumValue", total ? String(total) : "-");
    setText("sumPayment", pay);

    // if your modal has these fields
    setText("sumPickupFrom", pickupFrom);
    setText("sumPickupDate", getVal(pickupDateEl) || "-");
  }

  // -------------------- OPEN MODAL FLOW --------------------
  function openSummaryFlow() {
    clearError();

    if (!form) return;

    // HTML validation
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    // Require buyer select + crop select
    if (buyerTypeEl && !getVal(buyerTypeEl)) {
      showError("Please select Buyer Type.");
      return;
    }
    if (buyerSelectEl && !getVal(buyerSelectEl)) {
      showError("Please select Buyer.");
      return;
    }
    if (cropIdSelect && !getVal(cropIdSelect)) {
      showError("Please select Crop ID.");
      return;
    }
    if (quantityKgEl && !getVal(quantityKgEl)) {
      showError("Please enter Quantity.");
      return;
    }

    fillSummary();
    if (stateReview) stateReview.style.display = "block";
    if (stateSuccess) stateSuccess.style.display = "none";
    openModal();
  }

  // -------------------- CONFIRM: submit -> show success --------------------
  async function confirmAndSave() {
    clearError();
    if (!form) return;

    if (btnConfirm) {
      btnConfirm.disabled = true;
      btnConfirm.dataset.oldText = btnConfirm.textContent || "Confirm & Save";
      btnConfirm.textContent = "Saving...";
    }

    try {
      const fd = new FormData(form);

      const res = await fetch(form.action, {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      });

      const ct = (res.headers.get("content-type") || "").toLowerCase();
      const isJson = ct.includes("application/json");

      // Backend may return HTML (render_template) OR JSON
      if (!res.ok) {
        if (isJson) {
          const j = await res.json().catch(() => ({}));
          throw new Error(j.error || j.message || "Failed to create order");
        } else {
          // try to read text for debugging
          const t = await res.text().catch(() => "");
          throw new Error("Failed to create order (server returned non-JSON). Check logs.");
        }
      }

      // success: show success state
      if (stateReview) stateReview.style.display = "none";
      if (stateSuccess) stateSuccess.style.display = "block";

    } catch (e) {
      console.error(e);
      showError(e.message);
    } finally {
      if (btnConfirm) {
        btnConfirm.disabled = false;
        btnConfirm.textContent = btnConfirm.dataset.oldText || "Confirm & Save";
      }
    }
  }

  // -------------------- WIRE EVENTS --------------------
  document.addEventListener("DOMContentLoaded", async () => {
    // do nothing if page doesn't have this form
    if (!form) return;

    await initIdsAndDate();
    initPickupToggle();

    // buyer events
    if (buyerTypeEl) buyerTypeEl.addEventListener("change", filterBuyersByType);
    if (buyerSelectEl) buyerSelectEl.addEventListener("change", loadBuyerDetails);

    // crop sync
    if (cropIdSelect) cropIdSelect.addEventListener("change", syncCropFromId);
    if (cropTypeSelect) cropTypeSelect.addEventListener("change", syncCropFromType);

    // modal events
    if (btnOpen) btnOpen.addEventListener("click", (e) => {
      e.preventDefault();
      openSummaryFlow();
    });

    if (btnEdit) btnEdit.addEventListener("click", (e) => {
      e.preventDefault();
      closeModal();
    });

    if (backdrop) backdrop.addEventListener("click", closeModal);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal && modal.classList.contains("is-open")) closeModal();
    });

    if (btnConfirm) btnConfirm.addEventListener("click", (e) => {
      e.preventDefault();
      confirmAndSave();
    });

    // prefill via query string ?requestId=...
    const params = new URLSearchParams(window.location.search || "");
    const rid = params.get("requestId") || params.get("request_id") || (window.ADD_ORDER_PREFILL_REQUEST_ID || "");
    if (rid) await prefillFromRequestId(rid);
  });
})();
