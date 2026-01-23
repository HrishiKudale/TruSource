document.addEventListener("DOMContentLoaded", () => {
  const dataEl = document.getElementById("pricingData");
  const data = dataEl ? JSON.parse(dataEl.textContent) : {};
  const tabs = document.querySelectorAll(".pricing-tab");
  const thead = document.getElementById("pricingThead");
  const tbody = document.getElementById("pricingTbody");
  const empty = document.getElementById("pricingEmpty");

  const searchInput = document.getElementById("pricingSearchInput");
  const filterWrap = document.getElementById("manufacturerFilterWrap");
  const processingFilter = document.getElementById("manufacturerProcessingFilter");

  // Modal
  const modal = document.getElementById("pricingInfoModal");
  const backdrop = document.getElementById("pricingInfoBackdrop");
  const closeBtn = document.getElementById("pricingInfoClose");

  // Modal fields
  const pimHero = document.getElementById("pimHero");
  const pimThumbs = document.getElementById("pimThumbs");
  const pimDesc = document.getElementById("pimDesc");
  const pimName = document.getElementById("pimName");
  const pimLocation = document.getElementById("pimLocation");

  const pimFeatureCard = document.getElementById("pimFeatureCard");
  const pimOptionsWrap = document.getElementById("pimOptionsWrap");
  const pimOptionsCard = document.getElementById("pimOptionsCard");

  const pimYear = document.getElementById("pimYear");
  const pimGst = document.getElementById("pimGst");
  const pimContactPerson = document.getElementById("pimContactPerson");
  const pimPhone = document.getElementById("pimPhone");

  const pimThead = document.getElementById("pimThead");
  const pimTbody = document.getElementById("pimTbody");

  let activeTab = "warehouse";

  function setModalOpen(open) {
    if (!modal) return;
    if (open) {
      modal.classList.add("show");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    } else {
      modal.classList.remove("show");
      modal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    }
  }

  backdrop?.addEventListener("click", () => setModalOpen(false));
  closeBtn?.addEventListener("click", () => setModalOpen(false));

  function setThead(cols) {
    thead.innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr>`;
  }

  function setEmptyState(show) {
    empty.style.display = show ? "block" : "none";
  }

  function textIncludes(row, q) {
    const hay = Object.values(row || {}).join(" ").toLowerCase();
    return hay.includes(q);
  }

  function renderTable() {
    const q = (searchInput?.value || "").trim().toLowerCase();
    const proc = (processingFilter?.value || "").trim();

    let rows = (data[activeTab] || []);

    if (activeTab === "manufacturer" && proc) {
      rows = rows.filter(r => (r.processingType || "") === proc);
    }
    if (q) rows = rows.filter(r => textIncludes(r, q));

    // headers per tab
    if (activeTab === "warehouse") {
      setThead(["Warehouse ID", "Warehouse Name", "Location", "Storage Type", "Rate"]);
      tbody.innerHTML = rows.map(r => `
        <tr class="pricing-row" data-kind="warehouse" data-id="${r.buyerId}">
          <td>${r.buyerId || "-"}</td>
          <td>${r.name || "-"}</td>
          <td>${r.location || "-"}</td>
          <td>${r.storageType || "-"}</td>
          <td>${r.rateLabel || "-"}</td>
        </tr>
      `).join("");
    }

    if (activeTab === "manufacturer") {
      setThead(["Manufacturer ID", "Manufacturer Name", "Crop", "Processing Type", "Rate", "Turnaround Time (TAT)"]);
      tbody.innerHTML = rows.map(r => `
        <tr class="pricing-row" data-kind="manufacturer" data-id="${r.buyerId}">
          <td>${r.buyerId || "-"}</td>
          <td>${r.name || "-"}</td>
          <td>${r.cropSummary || "-"}</td>
          <td>${r.processingSummary || "-"}</td>
          <td>${r.rateSummary || "-"}</td>
          <td>${r.tatSummary || "-"}</td>
        </tr>
      `).join("");
    }

    if (activeTab === "transporter") {
      setThead(["Transporter ID", "Transporter Name", "Location", "Coverage", "Tracking"]);
      tbody.innerHTML = rows.map(r => `
        <tr class="pricing-row" data-kind="transporter" data-id="${r.buyerId}">
          <td>${r.buyerId || "-"}</td>
          <td>${r.name || "-"}</td>
          <td>${r.location || "-"}</td>
          <td>${r.coverage || "-"}</td>
          <td>${r.tracking || "-"}</td>
        </tr>
      `).join("");
    }

    setEmptyState(rows.length === 0);
  }

  function setTab(tab) {
    activeTab = tab;

    tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === tab));

    // show/hide manufacturer filter
    if (tab === "manufacturer") filterWrap.classList.remove("hidden");
    else filterWrap.classList.add("hidden");

    renderTable();
  }

  tabs.forEach(t => t.addEventListener("click", () => setTab(t.dataset.tab)));

  searchInput?.addEventListener("input", renderTable);
  processingFilter?.addEventListener("change", renderTable);

  // Row click → fetch modal data
  tbody?.addEventListener("click", async (e) => {
    const tr = e.target.closest(".pricing-row");
    if (!tr) return;
    const kind = tr.dataset.kind;
    const id = tr.dataset.id;

    try {
      const res = await fetch(`/farmer/pricing/info/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`);
      const js = await res.json();
      if (!js || !js.ok) {
        alert(js?.error || "Failed to load buyer info");
        return;
      }
      fillModal(kind, js.data);
      setModalOpen(true);
    } catch (err) {
      console.error(err);
      alert("Failed to load buyer info");
    }
  });

    function setHero(url, type) {
    if (!pimHero) return;

    const t = (type || "").toLowerCase();

    const fbWarehouse = pimHero.getAttribute("data-fallback-warehouse") || "";
    const fbManufacturer = pimHero.getAttribute("data-fallback-manufacturer") || "";
    const fbTransporter = pimHero.getAttribute("data-fallback-transporter") || "";

    let fallback = fbWarehouse;
    if (t === "manufacturer") fallback = fbManufacturer;
    if (t === "transporter") fallback = fbTransporter;

    const finalUrl = (url && url.trim()) ? url.trim() : fallback;

    if (!finalUrl) {
        pimHero.style.backgroundImage = "none";
        return;
    }

    pimHero.style.backgroundImage = `url("${finalUrl}")`;
    }




  function setThumbs(urls) {
    if (!pimThumbs) return;
    const safe = (urls && urls.length ? urls : ["", "", ""]);
    pimThumbs.innerHTML = safe.slice(0, 3).map(u => `<div class="pim-thumb" style="background-image:url('${u || ""}'); background-size:cover; background-position:center;"></div>`).join("");
  }

  function fillKeyValueCard(container, rows) {
    container.innerHTML = (rows || []).map(r => `
      <div class="pim-feature-row">
        <span style="color:#666;">${r.label}</span>
        <span style="color:#111; font-weight:600;">${r.value}</span>
      </div>
    `).join("");
  }

  function fillModal(kind, d) {
    // common
    pimName.textContent = d.name || "-";
    pimLocation.textContent = d.location || "-";
    pimDesc.textContent = d.description || "-";

    setHero(d.image || "", kind);

    setThumbs(d.thumbs || []);

    pimYear.textContent = d.establishmentYear || "-";
    pimGst.textContent = d.gstNumber || "-";
    pimContactPerson.textContent = d.contactPerson || "-";
    pimPhone.textContent = d.phone || "-";

    // kind-specific sections
    if (kind === "warehouse") {
      fillKeyValueCard(pimFeatureCard, [
        { label: "Temperature Range", value: d.temperatureRange || "-" },
        { label: "Humidity Control", value: d.humidityControl || "-" },
        { label: "Transport Support", value: d.transportSupport || "-" },
        { label: "Storage Capacity", value: d.storageCapacity || "-" },
      ]);

      pimOptionsWrap.style.display = "block";
      fillKeyValueCard(pimOptionsCard, (d.storageOptions || []).map(x => ({
        label: x.label, value: x.value
      })));

      pimThead.innerHTML = `<tr>
        <th>Storage Type</th>
        <th>Rate</th>
      </tr>`;

      pimTbody.innerHTML = (d.tableRows || []).map(r => `
        <tr>
          <td>${r.storageType || "-"}</td>
          <td>${r.rate || "-"}</td>
        </tr>
      `).join("");
    }

    if (kind === "manufacturer") {
      fillKeyValueCard(pimFeatureCard, [
        { label: "Services", value: d.servicesLabel || "-" },
        { label: "Quality", value: d.qualityLabel || "-" },
        { label: "Facility", value: d.facilityLabel || "-" },
      ]);

      pimOptionsWrap.style.display = "none";

      pimThead.innerHTML = `<tr>
        <th>Crop Name</th>
        <th>Processing Type</th>
        <th>Rate</th>
        <th>Turnaround Time (TAT)</th>
      </tr>`;

      pimTbody.innerHTML = (d.tableRows || []).map(r => `
        <tr>
          <td>${r.crop || "-"}</td>
          <td>${r.processingType || "-"}</td>
          <td>${r.rate || "-"}</td>
          <td>${r.tat || "-"}</td>
        </tr>
      `).join("");
    }

    if (kind === "transporter") {
      fillKeyValueCard(pimFeatureCard, [
        { label: "Coverage", value: d.coverage || "-" },
        { label: "Insurance Premium", value: d.insurancePremium || "-" },
        { label: "Tracking", value: d.tracking || "-" },
      ]);

      pimOptionsWrap.style.display = "none";

      pimThead.innerHTML = `<tr>
        <th>Vehicle Type</th>
        <th>Base Charge</th>
        <th>Per Km Rate</th>
        <th>Loading/Unloading</th>
      </tr>`;

      pimTbody.innerHTML = (d.tableRows || []).map(r => `
        <tr>
          <td>${r.vehicleType || "-"}</td>
          <td>${r.baseCharge || "-"}</td>
          <td>${r.perKmRate || "-"}</td>
          <td>${r.loading || "-"}</td>
        </tr>
      `).join("");
    }
  }

  // Export (simple CSV via backend)
  document.getElementById("btnPricingExport")?.addEventListener("click", () => {
    window.location.href = "/farmer/pricing/export";
  });

  // init
  setTab("warehouse");
});
