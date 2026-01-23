document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("marketplaceForm");

  // Crop
  const cropIdSelect = document.getElementById("cropIdSelect");
  const cropNameSelect = document.getElementById("cropNameSelect");
  const cropTypePreview = document.getElementById("cropTypePreview");
  const availableQty = document.getElementById("availableQty");

  // Qty/Price
  const qtyInput = document.getElementById("qtyInput");
  const priceInput = document.getElementById("priceInput");
  const priceUnit = document.getElementById("priceUnit");
  const totalValue = document.getElementById("totalValue");

  // Payment terms
  const paymentTerms = document.getElementById("paymentTerms");

  // Pickup location
  const pickupFrom = document.getElementById("pickupFrom");
  const pickupID = document.getElementById("pickupID");
  const pickupName = document.getElementById("pickupName");
  const pickupLocation = document.getElementById("pickupLocation");

  // ----------------------------
  // 1) Payment terms fill
  // ----------------------------
  const DEFAULT_PAYMENT_TERMS = [
    { value: "razorpay", label: "Razorpay" },
    { value: "bank_transfer", label: "Bank Transfer" },
    { value: "cash_on_pickup", label: "Cash on Pickup" },
    { value: "upi", label: "UPI" }
  ];

  if (paymentTerms) {
    // only add if empty beyond placeholder
    if (paymentTerms.options.length <= 1) {
      DEFAULT_PAYMENT_TERMS.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.value;
        opt.textContent = t.label;
        paymentTerms.appendChild(opt);
      });
    }
  }

  // ----------------------------
  // 2) Total value calculation
  // ----------------------------
  function unitMultiplier(unit) {
    // qty is assumed in KG
    // if you want qty unit selectable, add a qtyUnit dropdown.
    if (unit === "per_kg") return 1;
    if (unit === "per_quintal") return 1 / 100;  // ₹ per quintal => kg/100
    if (unit === "per_ton") return 1 / 1000;     // ₹ per ton => kg/1000
    return 1;
  }

  function calcTotal() {
    const q = Number(qtyInput?.value || 0);
    const p = Number(priceInput?.value || 0);
    const u = priceUnit?.value || "per_kg";

    if (!q || !p) {
      if (totalValue) totalValue.value = "";
      return;
    }

    const mult = unitMultiplier(u);
    const total = q * p * mult;
    if (totalValue) totalValue.value = `₹ ${total.toFixed(2)}`;
  }

  qtyInput?.addEventListener("input", calcTotal);
  priceInput?.addEventListener("input", calcTotal);
  priceUnit?.addEventListener("change", calcTotal);

  // ----------------------------
  // 3) Crop ID <-> Crop Type sync
  // ----------------------------
  function setAvailableFromOption(opt) {
    if (!opt) return;
    const av = opt.dataset.available || "";
    availableQty.value = av ? `${av} kg` : "";
  }

  function syncPreviewCrop(cropType) {
    if (!cropTypePreview) return;
    // keep preview options unique
    const existing = new Set(Array.from(cropTypePreview.options).map(o => o.value));
    if (!existing.has(cropType)) {
      const o = document.createElement("option");
      o.value = cropType;
      o.textContent = cropType;
      cropTypePreview.appendChild(o);
    }
    cropTypePreview.value = cropType || "";
  }

  // Crop ID -> Crop Name
  cropIdSelect?.addEventListener("change", () => {
    const opt = cropIdSelect.selectedOptions[0];
    if (!opt || !opt.value) return;

    const cropType = opt.dataset.cropType || "";
    // set cropNameSelect to matching cropType
    if (cropType) cropNameSelect.value = cropType;

    setAvailableFromOption(opt);
    syncPreviewCrop(cropType);
  });

  // Crop Name -> Crop ID
  cropNameSelect?.addEventListener("change", () => {
    const opt = cropNameSelect.selectedOptions[0];
    if (!opt || !opt.value) return;

    const id = opt.dataset.cropId || "";
    if (id) cropIdSelect.value = id;

    setAvailableFromOption(opt);
    syncPreviewCrop(opt.value);
  });

  // ----------------------------
  // 4) Pickup From <-> ID sync + autofill
  // ----------------------------
  function fillPickupFields(type, id, name, location) {
    if (pickupFrom && type) pickupFrom.value = type;
    if (pickupID && id) pickupID.value = id;

    if (pickupName) pickupName.value = name || "";
    if (pickupLocation) pickupLocation.value = location || "";
  }

  pickupFrom?.addEventListener("change", () => {
    const opt = pickupFrom.selectedOptions[0];
    if (!opt || !opt.value) return;

    // We stored id/name/location directly on Pickup From option
    const type = opt.value;
    const id = opt.dataset.id || "";

    // Find matching id option for same type (if exists)
    if (id) pickupID.value = id;

    const name = opt.dataset.name || "";
    const location = opt.dataset.location || "";
    fillPickupFields(type, id, name, location);
  });

  pickupID?.addEventListener("change", () => {
    const opt = pickupID.selectedOptions[0];
    if (!opt || !opt.value) return;

    const id = opt.value;
    const type = opt.dataset.type || "";
    const name = opt.dataset.name || "";
    const location = opt.dataset.location || "";

    fillPickupFields(type, id, name, location);
  });

  // ----------------------------
  // 5) Prefill (when editing listing)
  // ----------------------------
  try {
    const prefillEl = document.getElementById("prefillCrop");
    const pre = prefillEl ? JSON.parse(prefillEl.textContent || "{}") : {};

    // Adjust these keys if your marketplace listing uses different field names
    if (pre && Object.keys(pre).length) {
      if (pre.cropId) cropIdSelect.value = pre.cropId;
      if (pre.cropType) cropNameSelect.value = pre.cropType;

      // trigger change to fill available + preview
      cropIdSelect.dispatchEvent(new Event("change"));

      if (pre.quantity) qtyInput.value = pre.quantity;
      if (pre.minOrderQty) document.getElementById("minOrderQty").value = pre.minOrderQty;
      if (pre.price) priceInput.value = pre.price;
      if (pre.priceUnit) priceUnit.value = pre.priceUnit;

      if (pre.paymentTerms) paymentTerms.value = pre.paymentTerms;
      if (pre.targetBuyerType) document.getElementById("buyerType").value = pre.targetBuyerType;
      if (pre.listingDuration) document.getElementById("listingDuration").value = pre.listingDuration;

      if (pre.deliveryMode) {
        const radio = form.querySelector(`input[name="deliveryMode"][value="${pre.deliveryMode}"]`);
        if (radio) radio.checked = true;
      }

      if (pre.pickupFromType) pickupFrom.value = pre.pickupFromType;
      if (pre.pickupFromId) pickupID.value = pre.pickupFromId;
      pickupID.dispatchEvent(new Event("change"));

      calcTotal();
    }
  } catch (e) {
    // ignore
  }

  // ----------------------------
  // 6) Form validation guard (optional)
  // ----------------------------
  form?.addEventListener("submit", (e) => {
    // totalValue is readonly display with ₹, backend should compute anyway
    // but keep it populated for UX
    calcTotal();

    // Ensure cropId & cropType not empty
    if (!cropIdSelect?.value || !cropNameSelect?.value) {
      e.preventDefault();
      alert("Please select both Crop ID and Crop.");
      return;
    }
  });
});
