document.addEventListener("DOMContentLoaded", () => {
  // ✅ Row click navigation
  document.querySelectorAll("tr.click-row[data-href]").forEach((row) => {
    row.addEventListener("click", () => {
      const href = row.dataset.href;
      if (href) window.location.href = href;
    });
  });

  // ✅ Search filter
  const search = document.getElementById("table-search");
  const table = document.getElementById("ordersTable");

  if (search && table) {
    search.addEventListener("input", () => {
      const q = (search.value || "").trim().toLowerCase();
      const rows = table.querySelectorAll("tbody tr.click-row");

      rows.forEach((tr) => {
        const hay = (tr.dataset.search || "").toLowerCase();
        tr.style.display = hay.includes(q) ? "" : "none";
      });

      // If all rows hidden, show an inline "no results" row (optional)
      const anyVisible = Array.from(rows).some((r) => r.style.display !== "none");
      let noRes = table.querySelector("tr.no-results-row");

      if (!anyVisible) {
        if (!noRes) {
          noRes = document.createElement("tr");
          noRes.className = "no-results-row";
          noRes.innerHTML = `
            <td colspan="9" style="padding:18px; text-align:center; background:#fff;">
              No matching orders found.
            </td>`;
          table.querySelector("tbody").appendChild(noRes);
        }
      } else {
        if (noRes) noRes.remove();
      }
    });
  }
});
