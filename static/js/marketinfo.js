document.addEventListener("DOMContentLoaded", () => {
  const priceInput = document.getElementById("proposedPrice");
  const unitSelect = document.getElementById("priceUnit");
  const qtyHidden  = document.getElementById("demandQty");
  const totalField = document.getElementById("totalValue");

  // If negotiate card not present, silently exit
  if (!priceInput || !unitSelect || !qtyHidden || !totalField) return;

  function parseQtyToKg(raw) {
    // Supports: "1000 kg", "1000kg", "10 qtl", "1 ton", "1.5ton"
    const s = String(raw || "").toLowerCase().trim();
    if (!s) return 0;

    const num = parseFloat(s.replace(/[^0-9.]/g, ""));
    if (Number.isNaN(num)) return 0;

    if (s.includes("qtl")) return num * 100;   // 1 qtl = 100 kg
    if (s.includes("ton")) return num * 1000;  // 1 ton = 1000 kg
    return num; // default kg
  }

  function computeTotal() {
    const price = parseFloat(priceInput.value);
    if (Number.isNaN(price) || price <= 0) {
      totalField.value = "₹ -";
      return;
    }

    const qtyKg = parseQtyToKg(qtyHidden.value);
    if (!qtyKg || qtyKg <= 0) {
      totalField.value = "₹ -";
      return;
    }

    const unit = unitSelect.value; // kg/qtl/ton
    let qtyInUnit = qtyKg;
    if (unit === "qtl") qtyInUnit = qtyKg / 100;
    if (unit === "ton") qtyInUnit = qtyKg / 1000;

    const total = price * qtyInUnit;
    totalField.value = `₹ ${total.toFixed(2)}`;
  }

  // Recalc on typing + unit change
  priceInput.addEventListener("input", computeTotal);
  unitSelect.addEventListener("change", computeTotal);

  // Initial
  computeTotal();
});
