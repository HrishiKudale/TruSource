// traceabilityjourney.js (UPDATED • Better reveal + icons + theme by crop folder)
(() => {
  // Reveal animations
  const reveal = () => {
    const cards = document.querySelectorAll('.event');
    if (!('IntersectionObserver' in window)) {
      cards.forEach(c => c.classList.add('show'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('show');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    cards.forEach(c => io.observe(c));
  };

  // Icons mapping
  const setIcons = () => {
    document.querySelectorAll('.event').forEach(ev => {
      const k = (ev.getAttribute('data-kind') || '').toLowerCase();
      const s = (ev.getAttribute('data-stage') || '').toLowerCase();
      const icon = ev.querySelector('.icon');
      if (!icon) return;

      let emoji = "🔗";
      if (k.includes('plant')) emoji = "🌱";
      else if (k.includes('harvest')) emoji = "🌾";
      else if (k.includes('process')) emoji = (s === 'received' ? "📦" : "🏭");
      else if (k.includes('distrib')) emoji = (s === 'received' ? "🧾" : "🚚");
      else if (k.includes('retail')) emoji = (s === 'received' ? "🏪" : "🛒");
      icon.textContent = emoji;
    });
  };

  // Theme based on crop directory (your folder names: rice, turmeric, onion...)
  const applyTheme = () => {
    const crop = (window.__TRACE_CROP__ || '').toLowerCase().trim();

    const themes = {
      rice:      { bg1:"#f1f8e9", bg2:"#ecfeff", brand:"#22c55e", brand2:"#0ea5e9" },
      wheat:     { bg1:"#fff7ed", bg2:"#f0fdf4", brand:"#f59e0b", brand2:"#22c55e" },
      turmeric:  { bg1:"#fff7ed", bg2:"#fffbeb", brand:"#f59e0b", brand2:"#eab308" },
      onion:     { bg1:"#faf5ff", bg2:"#f0f9ff", brand:"#7c3aed", brand2:"#06b6d4" },
      cotton:    { bg1:"#f8fafc", bg2:"#ecfeff", brand:"#06b6d4", brand2:"#3b82f6" },
      sugarcane: { bg1:"#f0fdf4", bg2:"#ecfeff", brand:"#16a34a", brand2:"#0ea5e9" },
      strawberry:{ bg1:"#fff1f2", bg2:"#fff7ed", brand:"#fb7185", brand2:"#f97316" },
      soyabean:  { bg1:"#f0fdf4", bg2:"#ecfeff", brand:"#22c55e", brand2:"#0ea5e9" },
      jowar:     { bg1:"#fff7ed", bg2:"#f0fdf4", brand:"#f59e0b", brand2:"#22c55e" },
      coriander_kothambir: { bg1:"#f0fdf4", bg2:"#ecfeff", brand:"#16a34a", brand2:"#0ea5e9" }
    };

    const t = themes[crop] || themes.sugarcane;
    const root = document.documentElement;
    root.style.setProperty('--bg1', t.bg1);
    root.style.setProperty('--bg2', t.bg2);
    root.style.setProperty('--brand', t.brand);
    root.style.setProperty('--brand2', t.brand2);
  };

  // Nutrition demo
  const fillNutrition = () => {
    const crop = (window.__TRACE_CROP__ || '').toLowerCase().trim();

    const map = {
      rice:      { Calories: "130 kcal", Carbs: "28 g", Protein: "2.7 g", Fat: "0.3 g", Fiber: "0.4 g", Sodium: "1 mg" },
      wheat:     { Calories: "120 kcal", Carbs: "25 g", Protein: "4 g",   Fat: "0.9 g", Fiber: "3.6 g", Sodium: "2 mg" },
      onion:     { Calories: "40 kcal",  Carbs: "9.3 g", Protein: "1.1 g", Fat: "0.1 g", Fiber: "1.7 g", Sodium: "4 mg" },
      turmeric:  { Calories: "312 kcal", Carbs: "67 g",  Protein: "9.7 g", Fat: "3.3 g", Fiber: "22 g",  Sodium: "38 mg" },
      sugarcane: { Calories: "269 kcal", Carbs: "73 g",  Protein: "0 g",   Fat: "0 g",   Fiber: "0 g",   Sodium: "39 mg" }
    };

    const d = map[crop] || { Calories:"—", Carbs:"—", Protein:"—", Fat:"—", Fiber:"—", Sodium:"—" };
    const root = document.getElementById('nutriGrid');
    if (!root) return;

    root.innerHTML = '';
    Object.keys(d).forEach(k => {
      const div = document.createElement('div');
      div.className = 'nutri';
      div.innerHTML = `<div class="k">${k}</div><div class="val">${d[k]}</div>`;
      root.appendChild(div);
    });
  };

  window.addEventListener('load', () => {
    applyTheme();
    reveal();
    setIcons();
    fillNutrition();
  });
})();



// Reveal rows on scroll
const reveal = () => {
  document.querySelectorAll('.trow').forEach(row => {
    const r = row.getBoundingClientRect();
    if (r.top < innerHeight - 60) row.classList.add('show');
  });
};
document.addEventListener('scroll', reveal, { passive:true });
window.addEventListener('load', reveal);

// Icons by kind
document.querySelectorAll('.trow').forEach(row => {
  const k = (row.getAttribute('data-kind') || '').toLowerCase();
  const icon = row.querySelector('.ticon');
  if(!icon) return;

  if(k.includes('plant')) icon.textContent = '🌱';
  else if(k.includes('harvest')) icon.textContent = '🌾';
  else if(k.includes('process')) icon.textContent = '🏭';
  else if(k.includes('distrib')) icon.textContent = '🚚';
  else if(k.includes('retail')) icon.textContent = '🛒';
  else icon.textContent = '🔗';
});

// Nutrition demo (same)
(function fillNutrition(){
  const crop = (window.__TRACE_CROP__ || '').split('_')[0] || '';
  const map = {
    rice:      { Calories:"130 kcal", Carbs:"28 g", Protein:"2.7 g", Fat:"0.3 g", Fiber:"0.4 g", Sodium:"1 mg" },
    wheat:     { Calories:"120 kcal", Carbs:"25 g", Protein:"4 g",   Fat:"0.9 g", Fiber:"3.6 g", Sodium:"2 mg" },
    onion:     { Calories:"40 kcal",  Carbs:"9.3 g", Protein:"1.1 g", Fat:"0.1 g", Fiber:"1.7 g", Sodium:"4 mg" },
    turmeric:  { Calories:"312 kcal", Carbs:"67 g",  Protein:"9.7 g", Fat:"3.3 g", Fiber:"22 g", Sodium:"38 mg" },
    sugarcane: { Calories:"269 kcal", Carbs:"73 g",  Protein:"0 g",   Fat:"0 g",  Fiber:"0 g",  Sodium:"39 mg" }
  };
  const d = map[crop] || { Calories:"—", Carbs:"—", Protein:"—", Fat:"—", Fiber:"—", Sodium:"—" };
  const root = document.getElementById('nutriGrid');
  if(!root) return;

  root.innerHTML = '';
  Object.keys(d).forEach(k=>{
    const div = document.createElement('div');
    div.className = 'nutri';
    div.innerHTML = `<div class="meta-k">${k}</div><div class="val">${d[k]}</div>`;
    root.appendChild(div);
  });
})();
