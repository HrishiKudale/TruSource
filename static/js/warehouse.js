/* -------------------------------------------------------------
   WAREHOUSE FILTERING & SEARCH FUNCTIONALITY
-------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
  
  const table = document.querySelector(".warehouse-table");
  const rows = table ? table.querySelectorAll("tbody tr") : [];
  const searchInput = document.getElementById("table-search");

  // Dropdown filters
  const storageTypeFilter = document.getElementById("filter-storage-type");
  const locationFilter = document.getElementById("filter-location");

  // Date filter
  const dateFilterButton = document.getElementById("filter-date");
  const hiddenDateInput = document.createElement("input"); 
  hiddenDateInput.type = "date";
  hiddenDateInput.style.display = "none";
  document.body.appendChild(hiddenDateInput);


  /* -------------------------------------------------------------
     1. SEARCH FUNCTIONALITY
  -------------------------------------------------------------- */
  if (searchInput) {
    searchInput.addEventListener("keyup", () => {
      const query = searchInput.value.toLowerCase();
      filterTable(query, getFilters());
    });
  }


  /* -------------------------------------------------------------
     2. DROPDOWN FILTERS
  -------------------------------------------------------------- */

  // Example: You can attach actual dropdown menus later.

  if (storageTypeFilter) {
    storageTypeFilter.addEventListener("change", () => {
      filterTable(searchInput.value.toLowerCase(), getFilters());
    });
  }

  if (locationFilter) {
    locationFilter.addEventListener("change", () => {
      filterTable(searchInput.value.toLowerCase(), getFilters());
    });
  }

  /* -------------------------------------------------------------
     3. CALENDAR DATE FILTER
  -------------------------------------------------------------- */

  if (dateFilterButton) {
    dateFilterButton.addEventListener("click", () => {
      hiddenDateInput.showPicker();
    });
  }

  hiddenDateInput.addEventListener("change", () => {
    filterTable(searchInput.value.toLowerCase(), getFilters());
  });


  /* -------------------------------------------------------------
     4. FILTER FUNCTION LOGIC
  -------------------------------------------------------------- */

  function getFilters() {
    return {
      storageType: storageTypeFilter ? storageTypeFilter.value.toLowerCase() : "",
      location: locationFilter ? locationFilter.value.toLowerCase() : "",
      date: hiddenDateInput.value ? new Date(hiddenDateInput.value) : null
    };
  }

  function filterTable(searchQuery, filters) {

    rows.forEach(row => {
      let cells = row.querySelectorAll("td");

      if (row.classList.contains("empty-state-row")) return;

      const warehouseName = cells[1].innerText.toLowerCase();
      const location = cells[2].innerText.toLowerCase();
      const storageType = cells[5].innerText.toLowerCase();
      const lastUpdated = cells[7].innerText.trim();

      let rowDate = lastUpdated ? new Date(lastUpdated) : null;

      let matchesSearch =
        warehouseName.includes(searchQuery) ||
        location.includes(searchQuery) ||
        storageType.includes(searchQuery);

      let matchesStorageType =
        !filters.storageType || storageType.includes(filters.storageType);

      let matchesLocation =
        !filters.location || location.includes(filters.location);

      let matchesDate =
        !filters.date || (rowDate && rowDate >= filters.date);

      if (matchesSearch && matchesStorageType && matchesLocation && matchesDate) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
  }

});

document.addEventListener("click", (e) => {
  const row = e.target.closest(".click-row");
  if (!row) return;
  const href = row.dataset.href;
  if (href) window.location.href = href;
});

