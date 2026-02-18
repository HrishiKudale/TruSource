    // Smooth reveal of timeline cards
    const onScroll = () => {
      document.querySelectorAll('.event').forEach(ev => {
        const r = ev.getBoundingClientRect();
        if (r.top < innerHeight - 60) ev.classList.add('show');
      });
    };
    document.addEventListener('scroll', onScroll, {passive:true});
    window.addEventListener('load', onScroll);

    // Status → emoji flair
    document.querySelectorAll('.event').forEach(ev=>{
      const k = (ev.getAttribute('data-kind') || '').toLowerCase();
      const badge = ev.querySelector('.badge'); if(!badge) return;
      if(k.includes('plant'))   badge.textContent = '🌱 ' + badge.textContent;
      else if(k.includes('harvest')) badge.textContent = '🌾 ' + badge.textContent;
      else if(k.includes('process')) badge.textContent = '🏭 ' + badge.textContent;
      else if(k.includes('distrib')) badge.textContent = '🚚 ' + badge.textContent;
      else badge.textContent = '🔗 ' + badge.textContent;
    });

    // Theme by crop type
    (function themeByCrop(){
      const crop = "{{ (events_combined[0].cropType if events_combined else '')|lower }}";
      const themes = {
        rice:      { bg1:"#f1f8e9", bg2:"#ecfeff", brand:"#22c55e", brand2:"#0ea5e9" },
        wheat:     { bg1:"#fff7ed", bg2:"#f0fdf4", brand:"#f59e0b", brand2:"#22c55e" },
        tomato:    { bg1:"#fef2f2", bg2:"#fff7ed", brand:"#ef4444", brand2:"#f59e0b" },
        onion:     { bg1:"#faf5ff", bg2:"#f0f9ff", brand:"#7c3aed", brand2:"#06b6d4" },
        turmeric:  { bg1:"#fff7ed", bg2:"#fffbeb", brand:"#f59e0b", brand2:"#eab308" },
        cotton:    { bg1:"#f8fafc", bg2:"#ecfeff", brand:"#06b6d4", brand2:"#3b82f6" },
        sugarcane: { bg1:"#f0fdf4", bg2:"#ecfeff", brand:"#16a34a", brand2:"#0ea5e9" }
      };
      const t = themes[crop] || themes.sugarcane;
      const root = document.documentElement;
      root.style.setProperty('--bg1', t.bg1);
      root.style.setProperty('--bg2', t.bg2);
      root.style.setProperty('--brand', t.brand);
      root.style.setProperty('--brand2', t.brand2);
    })();

    // Nutrition (hard-coded demo per crop family)
    (function fillNutrition(){
      const crop = ("{{ (events_combined[0].cropType if events_combined else '')|lower }}").split(' ')[0] || "";
      const map = {
        rice:      { Calories: "130 kcal", Carbs: "28 g", Protein: "2.7 g", Fat: "0.3 g", Fiber: "0.4 g", Sodium: "1 mg" },
        wheat:     { Calories: "120 kcal", Carbs: "25 g", Protein: "4 g",   Fat: "0.9 g", Fiber: "3.6 g", Sodium: "2 mg" },
        tomato:    { Calories: "18 kcal",  Carbs: "3.9 g", Protein: "0.9 g", Fat: "0.2 g", Fiber: "1.2 g", Sodium: "5 mg" },
        onion:     { Calories: "40 kcal",  Carbs: "9.3 g", Protein: "1.1 g", Fat: "0.1 g", Fiber: "1.7 g", Sodium: "4 mg" },
        turmeric:  { Calories: "312 kcal", Carbs: "67 g",  Protein: "9.7 g", Fat: "3.3 g", Fiber: "22 g", Sodium: "38 mg" },
        cotton:    { Calories: "—", Carbs: "—", Protein: "—", Fat: "—", Fiber: "—", Sodium: "—" },
        sugarcane: { Calories: "269 kcal", Carbs: "73 g",  Protein: "0 g",   Fat: "0 g",  Fiber: "0 g",  Sodium: "39 mg" }
      };
      const d = map[crop] || { Calories:"—", Carbs:"—", Protein:"—", Fat:"—", Fiber:"—", Sodium:"—" };
      const root = document.getElementById('nutriGrid');
      root.innerHTML = '';
      Object.keys(d).forEach(k=>{
        const div = document.createElement('div');
        div.className = 'nutri';
        div.innerHTML = `<div class="note">${k}</div><div class="val">${d[k]}</div>`;
        root.appendChild(div);
      });
    })();