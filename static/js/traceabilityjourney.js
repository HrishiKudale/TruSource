// traceabilityjourney.js (FULL • paste entire file)
(() => {
  const norm = (v) => (v || "").toString().toLowerCase().trim();

  // ✅ window.__TRACE_CROP__ comes from HTML as asset_dir ("rice"/"turmeric"/"wheat")
  const getCropKey = () => {
    const raw = norm(window.__TRACE_CROP__);
    if (raw) return raw;

    // fallback if window var missing
    const title = norm(document.title);
    const h = norm(document.querySelector(".hero-title")?.textContent);
    const s = `${title} ${h}`;

    if (s.includes("turmeric") || s.includes("lakadong")) return "turmeric";
    if (s.includes("rice") || s.includes("assam red")) return "rice";
    if (s.includes("wheat")) return "wheat";
    return "rice";
  };

  // Reveal animations
  const revealCards = () => {
    const cards = document.querySelectorAll(".event");
    if (!cards.length) return;

    if (!("IntersectionObserver" in window)) {
      cards.forEach((c) => c.classList.add("show"));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("show");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 }
    );

    cards.forEach((c) => io.observe(c));
  };

  // Icons mapping (targets .icon class)
  const setIcons = () => {
    document.querySelectorAll(".event").forEach((ev) => {
      const k = norm(ev.getAttribute("data-kind"));
      const s = norm(ev.getAttribute("data-stage"));
      const icon = ev.querySelector(".icon");
      if (!icon) return;

      let emoji = "🔗";
      if (k.includes("plant")) emoji = "🌱";
      else if (k.includes("harvest")) emoji = "🌾";
      else if (k.includes("process")) emoji = s === "received" ? "📦" : "🏭";
      else if (k.includes("distrib")) emoji = s === "received" ? "🧾" : "🚚";
      else if (k.includes("retail") || k.includes("sold")) emoji = s === "received" ? "🏪" : "🛒";

      icon.textContent = emoji;
    });
  };

  // Theme based on crop key
  const applyTheme = () => {
    const crop = getCropKey();

    const themes = {
      rice:     { bg1:"#f2fbf4", bg2:"#e9fbff", brand:"#22c55e", brand2:"#0ea5e9" },
      wheat:    { bg1:"#fff7ed", bg2:"#f0fdf4", brand:"#f59e0b", brand2:"#22c55e" },
      turmeric: { bg1:"#fff7ed", bg2:"#fffbeb", brand:"#f59e0b", brand2:"#eab308" },
    };

    const t = themes[crop] || themes.rice;
    const root = document.documentElement;
    root.style.setProperty("--bg1", t.bg1);
    root.style.setProperty("--bg2", t.bg2);
    root.style.setProperty("--brand", t.brand);
    root.style.setProperty("--brand2", t.brand2);

    console.log("[TRACEABILITY THEME]", crop, t);
  };

  // Nutrition fill
  const fillNutrition = () => {
    const crop = getCropKey();

    const map = {
      rice:      { Calories:"130 kcal", Carbs:"28 g", Protein:"2.7 g", Fat:"0.3 g", Fiber:"0.4 g", Sodium:"1 mg" },
      wheat:     { Calories:"120 kcal", Carbs:"25 g", Protein:"4 g",   Fat:"0.9 g", Fiber:"3.6 g", Sodium:"2 mg" },
      turmeric:  { Calories:"312 kcal", Carbs:"67 g",  Protein:"9.7 g", Fat:"3.3 g", Fiber:"22 g",  Sodium:"38 mg" },
    };

    const d = map[crop] || { Calories:"—", Carbs:"—", Protein:"—", Fat:"—", Fiber:"—", Sodium:"—" };
    const root = document.getElementById("nutriGrid");
    if (!root) {
      console.warn("[NUTRITION] #nutriGrid not found");
      return;
    }

    root.innerHTML = "";
    Object.keys(d).forEach((k) => {
      const div = document.createElement("div");
      div.className = "nutri";
      div.innerHTML = `<div class="k">${k}</div><div class="val">${d[k]}</div>`;
      root.appendChild(div);
    });

    console.log("[NUTRITION] loaded for", crop);
  };

  window.addEventListener("load", () => {
    applyTheme();
    setIcons();
    fillNutrition();
    revealCards();
  });
})();