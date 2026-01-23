document.addEventListener("DOMContentLoaded", () => {
  const dropdownToggles = document.querySelectorAll(".dropdown-toggle");

dropdownToggles.forEach(toggle => {
  toggle.addEventListener("click", (e) => {
    const parentLi = toggle.closest(".dropdown");
    const submenu = parentLi.querySelector(".submenu");

    // Always allow toggling if submenu exists
    if (submenu) {
      e.preventDefault();

      // Toggle this dropdown
      parentLi.classList.toggle("open");
      parentLi.classList.toggle("submenu-parent");
    }
  });
});


  const submenuLinks = document.querySelectorAll(".submenu .component-link");

  submenuLinks.forEach(link => {
    link.addEventListener("click", () => {
      const parentLi   = link.parentElement;
      const dropdownLi = parentLi.closest(".dropdown");

      // clear active from all submenu items
      dropdownLi.querySelectorAll(".submenu li").forEach(li => {
        li.classList.remove("submenu-active", "component-2");
      });

      // mark clicked submenu active
      parentLi.classList.add("submenu-active", "component-2");

      // keep dropdown open
      dropdownLi.classList.add("open", "submenu-parent");

      // update icons
      const submenuIcon = parentLi.querySelector(".sidebar-icon");
      if (submenuIcon) submenuIcon.classList.add("active");
    });
  });
});
