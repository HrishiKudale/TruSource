// traceabilityjourney.js (FINAL FIXED VERSION - SAFE + MAKHANA STABLE)

(() => {
  const norm = (v) => (v || "").toString().toLowerCase().trim();

  // ------------------------------------------------------------
  // GET CROP
  // ------------------------------------------------------------
  const getCropKey = () => {
    const raw = norm(window.__TRACE_CROP__);
    if (raw) return raw;

    const title = norm(document.title);
    const h = norm(document.querySelector(".hero-title")?.textContent);
    const s = `${title} ${h}`;

    if (s.includes("turmeric") || s.includes("lakadong")) return "turmeric";
    if (s.includes("rice") || s.includes("assam red")) return "rice";
    if (s.includes("wheat")) return "wheat";
    if (s.includes("makhana")) return "makhana";

    return "rice";
  };

  // ------------------------------------------------------------
  // ICONS
  // ------------------------------------------------------------
  const setIcons = () => {
    document.querySelectorAll(".event").forEach((ev) => {
      const k = norm(ev.getAttribute("data-kind"));
      const s = norm(ev.getAttribute("data-stage"));
      const icon = ev.querySelector(".icon");
      if (!icon) return;

      let emoji = "🔗";
      if (k.includes("plant")) emoji = "🌱";
      else if (k.includes("harvest")) emoji = "🌾";
      else if (k.includes("grade")) emoji = "🧪";
      else if (k.includes("popp")) emoji = "🔥";
      else if (k.includes("process")) emoji = s === "received" ? "📦" : "🏭";
      else if (k.includes("distrib")) emoji = s === "received" ? "🧾" : "🚚";
      else if (k.includes("retail") || k.includes("sold")) emoji = s === "received" ? "🏪" : "🛒";

      icon.textContent = emoji;
    });
  };

  // ------------------------------------------------------------
  // THEME
  // ------------------------------------------------------------
  const applyTheme = () => {
    const crop = getCropKey();

    const themes = {
      rice: { bg1:"#f2fbf4", bg2:"#e9fbff", brand:"#22c55e", brand2:"#0ea5e9" },
      wheat:{ bg1:"#fff7ed", bg2:"#f0fdf4", brand:"#f59e0b", brand2:"#22c55e" },
      turmeric:{ bg1:"#fff7ed", bg2:"#fffbeb", brand:"#f59e0b", brand2:"#eab308" },
      makhana:{
        bg1:"#FFF9F0",
        bg2:"#FDEFD9",
        brand:"#C49A6C",
        brand2:"#D7B98A"
      }
    };

    const t = themes[crop] || themes.rice;

    document.documentElement.style.setProperty("--bg1", t.bg1);
    document.documentElement.style.setProperty("--bg2", t.bg2);
    document.documentElement.style.setProperty("--brand", t.brand);
    document.documentElement.style.setProperty("--brand2", t.brand2);
  };

  // ------------------------------------------------------------
  // NUTRITION
  // ------------------------------------------------------------
  const fillNutrition = () => {
    const crop = getCropKey();

    const map = {
      rice: { Calories:"130 kcal", Carbs:"28 g", Protein:"2.7 g", Fat:"0.3 g", Fiber:"0.4 g", Sodium:"1 mg" },
      wheat:{ Calories:"120 kcal", Carbs:"25 g", Protein:"4 g", Fat:"0.9 g", Fiber:"3.6 g", Sodium:"2 mg" },
      turmeric:{ Calories:"312 kcal", Carbs:"67 g", Protein:"9.7 g", Fat:"3.3 g", Fiber:"22 g", Sodium:"38 mg" },
      makhana:{ Calories:"347 kcal", Carbs:"77 g", Protein:"9.7 g", Fat:"0.1 g", Fiber:"14 g", Sodium:"26 mg" }
    };

    const d = map[crop] || map.rice;
    const root = document.getElementById("nutriGrid");
    if (!root) return;

    root.innerHTML = "";
    Object.keys(d).forEach((k) => {
      const div = document.createElement("div");
      div.className = "nutri";
      div.innerHTML = `<div class="k">${k}</div><div class="val">${d[k]}</div>`;
      root.appendChild(div);
    });
  };

  // ------------------------------------------------------------
  // SAFE IMAGE FIX (ONLY IF IMAGE FAILS)
  // ------------------------------------------------------------
  function attachImageFallback(img) {
    const original = img.src;

    const exts = ["jpg", "png", "webp", "jpeg", "avif"];
    let i = 0;

    img.onerror = function () {
      if (i < exts.length - 1) {
        i++;
        const base = original.replace(/\.(jpg|jpeg|png|webp|avif)$/i, "");
        this.src = `${base}.${exts[i]}`;
      } else {
        this.src = "/static/images/crops/common/planted.jpg";
      }
    };
  }

  // ------------------------------------------------------------
  // MAKHANA FIX (SAFE VERSION - NO OVERRIDES)
  // ------------------------------------------------------------
  const fixMakhanaImages = () => {
    if (getCropKey() !== "makhana") return;

    const map = {
      planted: "planted",
      harvest: "harvested",
      harvested: "harvested",
      grading: "grading",
      popp: "popping",
      popping: "popping",
      roasting: "roasting",
      sun: "sun_drying",
      drying: "sun_drying",
      moisture: "moisture_reduction"
    };

    document.querySelectorAll(".event img").forEach((img) => {
      const alt = norm(img.alt);

      let matched = null;

      for (let key in map) {
        if (alt.includes(key)) {
          matched = map[key];
          break;
        }
      }

      if (!matched) return;

      const base = `/static/images/crops/makhana/${matched}`;
      img.dataset.makhana = "1";

      img.src = `${base}.jpg`;

      img.onerror = function () {
        this.onerror = function () {
          this.onerror = null;
          this.src = `${base}.png`;
        };
        this.src = `${base}.webp`;
      };
    });
  };

  // ------------------------------------------------------------
  // REVEAL
  // ------------------------------------------------------------
  const revealCards = () => {
    const cards = document.querySelectorAll(".event");
    if (!cards.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("show");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });

    cards.forEach((c) => io.observe(c));
  };

  // ------------------------------------------------------------
  // INIT
  // ------------------------------------------------------------
  window.addEventListener("load", () => {
    applyTheme();
    setIcons();
    fillNutrition();
    revealCards();

    // ONLY ADD FALLBACKS (DO NOT OVERRIDE JINJA IMAGES)
    document.querySelectorAll("img").forEach(attachImageFallback);

    fixMakhanaImages();
  });
})();