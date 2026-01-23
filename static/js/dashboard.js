// Basic UI helpers for farmer_base.html + Mycrop.html

// ========== SIDEBAR TOGGLE (MOBILE) ==========
function toggleSidebar() {
  var sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  sidebar.classList.toggle("open");
}

// ========== APPROVED REQUESTS MODAL ==========
function openApprovedModal() {
  var modal = document.getElementById("approvedModal");
  if (!modal) return;
  modal.classList.add("open");
}

function closeApprovedModal() {
  var modal = document.getElementById("approvedModal");
  if (!modal) return;
  modal.classList.remove("open");
}

// ========== TRACEABILITY PANEL ==========
function openTracePanel() {
  var panel = document.getElementById("tracePanel");
  if (!panel) return;
  panel.classList.add("open");
}

function closeTracePanel() {
  var panel = document.getElementById("tracePanel");
  if (!panel) return;
  panel.classList.remove("open");
}

// ========== OPTIONAL: highlight current nav by URL (fallback) ==========
document.addEventListener("DOMContentLoaded", function () {
  var navLinks = document.querySelectorAll(".nav a[href]");
  var current = window.location.pathname || "";

  navLinks.forEach(function (link) {
    var href = link.getAttribute("href") || "";
    // basic heuristic; Jinja already sets .active via active_page
    if (href && href !== "#" && current.startsWith(href)) {
      link.classList.add("active");
    }
  });
});
