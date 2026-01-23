// Simple light/dark theme toggle for farmer_base.html

(function () {
  var STORAGE_KEY = "pg-theme";

  function applyTheme(theme) {
    var body = document.body;
    var toggle = document.getElementById("themeToggle");
    var label = document.getElementById("themeLabel");

    if (!body) return;

    if (theme === "dark") {
      body.classList.add("dark");
      if (toggle) toggle.setAttribute("aria-pressed", "true");
      if (label) label.textContent = "Dark";
    } else {
      body.classList.remove("dark");
      if (toggle) toggle.setAttribute("aria-pressed", "false");
      if (label) label.textContent = "Light";
    }
  }

  function getInitialTheme() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "dark" || stored === "light") return stored;
    } catch (e) {
      // ignore
    }

    // System preference fallback
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.matches) return "dark";
    }

    return "light";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var currentTheme = getInitialTheme();
    applyTheme(currentTheme);

    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;

    toggle.addEventListener("click", function () {
      var newTheme = document.body.classList.contains("dark")
        ? "light"
        : "dark";

      applyTheme(newTheme);
      try {
        localStorage.setItem(STORAGE_KEY, newTheme);
      } catch (e) {
        // ignore storage errors
      }
    });
  });
})();
