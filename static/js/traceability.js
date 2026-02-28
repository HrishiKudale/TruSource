/* static/js/traceability.js */
(function () {
  "use strict";

  const input = document.getElementById("trSearchInput");
  const btn = document.getElementById("trSearchBtn");
  const timeline = document.getElementById("timeline");
  const docBody = document.getElementById("docBody");
  const cropChip = document.getElementById("cropChip");
  const msg = document.getElementById("trMsg");

  const btnCopyCrop = document.getElementById("btnCopyCrop");

  function showMsg(text) {
    msg.style.display = text ? "block" : "none";
    msg.textContent = text || "";
  }

  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, (m) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[m]));
  }

  function makeRow(label, value) {
    return `<div class="row"><b>${esc(label)}:</b> ${esc(value || "-")}</div>`;
  }

  function renderTimeline(data) {
    timeline.innerHTML = "";

    const sections = [
      {
        key: "originHarvest",
        title: "Origin",
        icon: window.STATIC_ICONS.origin,
        subtitle: data?.originHarvest?.location || "—",
        detailsHtml: [
          makeRow("Location", data?.originHarvest?.location),
          makeRow("Crop", data?.originHarvest?.cropName || data?.originHarvest?.cropType),
          makeRow("Planted on", data?.originHarvest?.plantedOn),
          makeRow("Harvest Date", data?.originHarvest?.harvestDate),
          makeRow("Farming Type", data?.originHarvest?.farmingType),
          makeRow("Farmer Name", data?.originHarvest?.farmerName),
        ].join("")
      },
      {
        key: "storage",
        title: "Storage",
        icon: window.STATIC_ICONS.storage,
        subtitle: data?.storage?.warehouseName ? `${data.storage.warehouseName}, ${data.storage.city || ""}`.trim() : "—",
        detailsHtml: data?.storage ? [
          makeRow("Warehouse", data.storage.warehouseName),
          makeRow("City", data.storage.city),
          makeRow("Stored On", data.storage.storedOn),
          makeRow("Quality Check", data.storage.qualityCheck),
        ].join("") : `<div class="row">No storage record found.</div>`
      },
      {
        key: "processing",
        title: "Processing",
        icon: window.STATIC_ICONS.processing,
        subtitle: data?.processing?.processorName ? `${data.processing.processorName}` : "—",
        detailsHtml: data?.processing ? [
          makeRow("Processor", data.processing.processorName),
          makeRow("Process", data.processing.process),
          makeRow("Input Qty", data.processing.inputQty),
          makeRow("Output Qty", data.processing.outputQty),
          makeRow("Processing Date", data.processing.processingDate),
        ].join("") : `<div class="row">No processing record found.</div>`
      },
      {
        key: "shipment",
        title: "Shipment",
        icon: window.STATIC_ICONS.shipment,
        subtitle: data?.shipment?.count ? `${data.shipment.count} shipments` : "—",
        detailsHtml: data?.shipment?.shipments?.length ? (
          data.shipment.shipments.map((s, idx) => `
            <div class="row"><b>Shipment ${idx + 1}</b></div>
            ${makeRow("Transporter", s.transporterName)}
            ${makeRow("Delivered To", s.deliveredTo)}
            ${makeRow("Route", s.route)}
            ${s.shipmentDate ? makeRow("Date", s.shipmentDate) : ""}
            <div class="row" style="height:8px"></div>
          `).join("")
        ) : `<div class="row">No shipment record found.</div>`
      },
      {
        key: "sale",
        title: "Sale",
        icon: window.STATIC_ICONS.sale,
        subtitle: data?.sale?.buyerName ? data.sale.buyerName : "—",
        detailsHtml: data?.sale ? [
          makeRow("Buyer", data.sale.buyerName),
          makeRow("City", data.sale.city),
          makeRow("Purchase Date", data.sale.purchaseDate),
        ].join("") : `<div class="row">No sale record found.</div>`
      },
    ];

    sections.forEach((sec, i) => {
      const hasLine = i !== sections.length - 1;

      const item = document.createElement("div");
      item.className = "t-item";
            item.innerHTML = `
            <div class="t-left">
                <div class="t-dot">
                <img class="t-dot-icon" src="${esc(sec.icon)}" alt="${esc(sec.title)}">
                </div>
                ${hasLine ? `<div class="t-line"></div>` : ``}
            </div>

            <div class="t-card">
                <div class="t-title-row">
                <div>
                    <div class="t-title">${esc(sec.title)}</div>
                    <div class="t-sub">${esc(sec.subtitle)}</div>
                </div>
                <div class="t-chevron" data-open="0">▾</div>
                </div>
                <div class="t-details">${sec.detailsHtml}</div>
            </div>

            <div></div>
            `;


      const chevron = item.querySelector(".t-chevron");
      const details = item.querySelector(".t-details");
      chevron.addEventListener("click", () => {
        const open = chevron.getAttribute("data-open") === "1";
        chevron.setAttribute("data-open", open ? "0" : "1");
        chevron.textContent = open ? "▾" : "▴";
        details.style.display = open ? "none" : "block";
      });

      timeline.appendChild(item);
    });
  }

  function renderDocs(docs) {
    docBody.innerHTML = "";

    if (!docs || !docs.length) {
      docBody.innerHTML = `<div class="doc-row"><div style="color:#777">No documents found.</div><div></div></div>`;
      return;
    }

    docs.forEach((d) => {
      const row = document.createElement("div");
      row.className = "doc-row";

      row.innerHTML = `
        <div>${esc(d.name || "Document")}</div>
        <div class="right">
          <button class="doc-action" title="View">👁</button>
          <button class="doc-action" title="Download">⬇</button>
        </div>
      `;

      const [btnView, btnDown] = row.querySelectorAll("button");

      btnView.addEventListener("click", () => {
        if (d.viewUrl) window.open(d.viewUrl, "_blank");
      });

      btnDown.addEventListener("click", () => {
        if (d.downloadUrl) window.open(d.downloadUrl, "_blank");
      });

      // If urls not available, disable
      if (!d.viewUrl) btnView.disabled = true;
      if (!d.downloadUrl) btnDown.disabled = true;

      docBody.appendChild(row);
    });
  }

async function search() {
  const cropId = (input.value || "").trim();
  if (!cropId) return showMsg("Select a crop.");

  showMsg("");
  cropChip.textContent = "…";
  timeline.innerHTML = "";
  docBody.innerHTML = "";

  try {
    const url = `${window.TRACE_API}?cropId=${encodeURIComponent(cropId)}`; // ✅ changed
    const res = await fetch(url, { cache: "no-store" });
    const out = await res.json().catch(() => ({}));

    if (!res.ok || !out.ok) {
      cropChip.textContent = "—";
      showMsg(out.message || out.err || "Not found.");
      return;
    }

    const data = out.data;
    cropChip.textContent = data.cropId || "—";

    renderTimeline(data);
    renderDocs(data.documents || []);
  } catch (e) {
    cropChip.textContent = "—";
    showMsg(e.message || "Failed to fetch traceability.");
  }
}

  btn.addEventListener("click", search);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      search();
    }
  });

  btnCopyCrop.addEventListener("click", async () => {
    const t = cropChip.textContent || "";
    if (!t || t === "—" || t === "…") return;
    try {
      await navigator.clipboard.writeText(t);
    } catch {}
  });

})();
