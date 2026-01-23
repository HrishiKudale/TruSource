document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);

  // Form
  const form = $("processingForm");

  // Manufacturer
  const manufacturerSelect = $("manufacturerSelect");
  const manufacturerIdInput = $("manufacturerId");

  // Crop selectors
  const cropIdSelect = $("cropIdSelect");
  const cropTypeSelect = $("cropTypeSelect");

  // Inputs
  const processingType = $("processingType");
  const qtyKg = $("qtyKg");
  const priceValue = $("priceValue");

  // Table
  const tbody = $("processingTableBody");
  const emptyRow = $("processingEmptyRow");
  const addBtn = $("addProcessingRow");

  // Summary modal elements
  const modal = $("processSummaryModal");
  const backdrop = $("processSummaryBackdrop");
  const btnOpen = $("openProcessSummaryBtn");
  const btnEdit = $("btnProcessEdit");
  const btnConfirm = $("btnProcessConfirm");

  const stateReview = $("processStateReview");
  const stateSuccess = $("processStateSuccess");
  const errEl = $("processSummaryError");

  // Summary values
  const sumManufacturer = $("sumManufacturer");
  const sumCropType = $("sumCropType");
  const sumQuantity = $("sumQuantity");
  const sumDate = $("sumDate");
  const sumTotalValue = $("sumTotalValue");
  const sumPayment = $("sumPayment");

  const requestDate = $("requestDate");
  const paymentMode = $("paymentMode");

  function openModal() {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  }

  function showError(msg) {
    errEl.style.display = "block";
    errEl.textContent = msg;
  }

  function clearError() {
    errEl.style.display = "none";
    errEl.textContent = "";
  }

  // ✅ Manufacturer -> Manufacturer ID
  if (manufacturerSelect && manufacturerIdInput) {
    manufacturerSelect.addEventListener("change", () => {
      const opt = manufacturerSelect.selectedOptions[0];
      const id = opt ? opt.getAttribute("data-id") : "";
      manufacturerIdInput.value = id || "";
    });
  }

  // ✅ Crop ID -> Crop Type
  if (cropIdSelect && cropTypeSelect) {
    cropIdSelect.addEventListener("change", () => {
      const opt = cropIdSelect.selectedOptions[0];
      const cropType = opt ? opt.getAttribute("data-croptype") : "";
      if (!cropType) return;

      for (let i = 0; i < cropTypeSelect.options.length; i++) {
        if (cropTypeSelect.options[i].value === cropType) {
          cropTypeSelect.selectedIndex = i;
          break;
        }
      }
    });

    // ✅ Crop Type -> Crop ID
    cropTypeSelect.addEventListener("change", () => {
      const opt = cropTypeSelect.selectedOptions[0];
      const cropId = opt ? opt.getAttribute("data-cropid") : "";
      if (!cropId) return;

      for (let i = 0; i < cropIdSelect.options.length; i++) {
        if (cropIdSelect.options[i].value === cropId) {
          cropIdSelect.selectedIndex = i;
          break;
        }
      }
    });
  }

  // ✅ Add row to table + create hidden inputs for backend
  addBtn.addEventListener("click", () => {
    const cropId = cropIdSelect.value;
    const cropType = cropTypeSelect.value;
    const procType = processingType.value;
    const qty = qtyKg.value;
    const price = priceValue.value || "";

    if (!cropId || !cropType || !procType || !qty) {
      alert("Please select Crop ID, Crop, Processing Type and enter Quantity.");
      return;
    }

    // Remove empty illustration row
    if (emptyRow) emptyRow.remove();

    const tr = document.createElement("tr");
    tr.classList.add("proc-row");
    tr.dataset.qty = qty;
    tr.dataset.price = price || "0";
    tr.dataset.crop = cropType;

    tr.innerHTML = `
      <td>
        ${cropId}
        <input type="hidden" name="items_crop_id[]" value="${cropId}">
      </td>
      <td>
        ${cropType}
        <input type="hidden" name="items_crop_type[]" value="${cropType}">
      </td>
      <td>
        ${procType}
        <input type="hidden" name="items_processing_type[]" value="${procType}">
      </td>
      <td>
        ${qty} Kg
        <input type="hidden" name="items_quantityKg[]" value="${qty}">
      </td>
      <td>
        ${price ? "₹ " + price : "-"}
        <input type="hidden" name="items_price[]" value="${price}">
      </td>
    `;

    tbody.appendChild(tr);

    // Reset inputs
    qtyKg.value = "";
    priceValue.value = "";
    processingType.selectedIndex = 0;
  });

  function computeTotals() {
    const rows = tbody.querySelectorAll("tr.proc-row");
    let totalQty = 0;
    let totalPrice = 0;
    let cropName = "-";

    rows.forEach((r, idx) => {
      totalQty += Number(r.dataset.qty || 0);
      totalPrice += Number(r.dataset.price || 0);
      if (idx === 0) cropName = r.dataset.crop || "-";
    });

    return { count: rows.length, totalQty, totalPrice, cropName };
  }

  function fillSummary() {
    const mOpt = manufacturerSelect.selectedOptions[0];
    const manufacturerName = mOpt ? mOpt.textContent.trim() : "-";

    const totals = computeTotals();
    sumManufacturer.textContent = manufacturerName;
    sumCropType.textContent = totals.cropName;
    sumQuantity.textContent = totals.count ? `${totals.totalQty} Kg` : "-";
    sumDate.textContent = requestDate.value || "-";
    sumTotalValue.textContent = totals.count ? `₹ ${totals.totalPrice}` : "-";
    sumPayment.textContent = paymentMode.value || "-";
  }

  // ✅ Open summary modal instead of direct submit
  btnOpen.addEventListener("click", () => {
    clearError();

    // Validate base form fields
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    fillSummary();

    const totals = computeTotals();
    stateReview.style.display = "block";
    stateSuccess.style.display = "none";

    if (!totals.count) {
      showError("Please add at least one crop row before sending the request.");
    }

    openModal();
  });

  // Close modal
  btnEdit.addEventListener("click", closeModal);
  backdrop.addEventListener("click", closeModal);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) closeModal();
  });

  // ✅ Confirm & Save -> submit to backend (works even if redirect)
  btnConfirm.addEventListener("click", async () => {
    clearError();

    const totals = computeTotals();
    if (!totals.count) {
      showError("Please add at least one crop row before saving.");
      return;
    }

    btnConfirm.disabled = true;
    const oldText = btnConfirm.textContent;
    btnConfirm.textContent = "Saving...";

    try {
      const res = await fetch(form.action, {
        method: "POST",
        body: new FormData(form)
      });

      if (!res.ok) throw new Error("Failed to submit processing request.");

      stateReview.style.display = "none";
      stateSuccess.style.display = "block";
    } catch (err) {
      showError(err.message);
    } finally {
      btnConfirm.disabled = false;
      btnConfirm.textContent = oldText;
    }
  });
});
