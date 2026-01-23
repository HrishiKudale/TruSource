// -----------------------------
// DROPDOWN TOGGLE
// -----------------------------
document.querySelectorAll(".dropdown-btn").forEach(btn => {
    btn.addEventListener("click", (event) => {
        event.stopPropagation(); // Prevent closing immediately

        const menu = btn.parentElement.querySelector(".dropdown-menu");

        // Close other dropdowns first
        document.querySelectorAll(".dropdown-menu").forEach(m => {
            if (m !== menu) m.style.display = "none";
        });

        // Toggle current
        menu.style.display = (menu.style.display === "block") ? "none" : "block";
    });
});

// Close dropdown when clicking outside
document.addEventListener("click", () => {
    document.querySelectorAll(".dropdown-menu").forEach(menu => {
        menu.style.display = "none";
    });
});


// -----------------------------
// SEARCH TABLE FILTER
// -----------------------------
const searchInput = document.getElementById("table-search");

if (searchInput) {
    searchInput.addEventListener("input", () => {
        let filter = searchInput.value.toLowerCase();

        document.querySelectorAll(".order-table tbody tr").forEach(row => {
            if (row.classList.contains("no-data-row")) return;
            row.style.display = row.innerText.toLowerCase().includes(filter) ? "" : "none";
        });
    });
}


// -----------------------------
// CLOSE EMPTY STATE WHEN DATA APPEARS
// -----------------------------
function hideEmptyStateIfRowsExist() {
    const visibleRows = [...document.querySelectorAll(".order-table tbody tr")]
        .filter(tr => tr.style.display !== "none" && !tr.classList.contains("no-data-row"));

    const emptyState = document.querySelector(".empty-state-inside");
    if (!emptyState) return;

    if (visibleRows.length > 0) {
        emptyState.style.display = "none";
    } else {
        emptyState.style.display = "flex";
    }
}

// When search filters rows
searchInput?.addEventListener("input", hideEmptyStateIfRowsExist);
