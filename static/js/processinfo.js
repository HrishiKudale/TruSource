
document.addEventListener("DOMContentLoaded", function () {
  const rows = document.querySelectorAll(".pi-click-row");

  rows.forEach(function (row) {
    row.addEventListener("click", function () {
      const url = row.getAttribute("data-href");
      if (url) {
        window.location.href = url;
      }
    });
  });
});
