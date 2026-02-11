document.addEventListener("DOMContentLoaded", function () {
  const tbody = document.querySelector(".manufacturer-table tbody");
  if (!tbody) return;

  tbody.addEventListener("click", function (e) {
    const row = e.target.closest("tr.pi-click-row");
    if (!row) return;

    const url = row.getAttribute("data-href");
    if (url) window.location.href = url;
  });
});
