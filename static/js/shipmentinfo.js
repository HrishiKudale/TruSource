// static/shipmentinfo.js

document.addEventListener("DOMContentLoaded", () => {

  // ---------------------------
  // Copy Request ID
  // ---------------------------
  const btnCopy = document.getElementById("btnCopyReq");
  const reqIdEl = document.getElementById("reqIdText");

  if (btnCopy && reqIdEl) {
    btnCopy.addEventListener("click", async () => {
      const text = (reqIdEl.textContent || "").trim();
      if (!text || text === "-") return;

      try {
        await navigator.clipboard.writeText(text);
        btnCopy.textContent = "Copied!";
        setTimeout(() => (btnCopy.textContent = "Copy ID"), 900);
      } catch (e) {
        alert("Copy failed. Please copy manually.");
      }
    });
  }

  // ---------------------------
  // Linked Orders table search
  // ---------------------------
  const search = document.getElementById("linkedOrdersSearch");
  const table  = document.getElementById("linkedOrdersTable");

  if (search && table) {
    const rows = Array.from(table.querySelectorAll("tbody tr"));

    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      rows.forEach(tr => {
        const txt = (tr.textContent || "").toLowerCase();
        tr.style.display = txt.includes(q) ? "" : "none";
      });
    });
  }

});
