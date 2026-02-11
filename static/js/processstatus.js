document.addEventListener("DOMContentLoaded", () => {
  const stepper = document.getElementById("psStepper");
  if (!stepper) return;

  const current = parseInt(stepper.dataset.currentStep || "1", 10);

  const steps = stepper.querySelectorAll(".ps-step");
  steps.forEach((el) => {
    const n = parseInt(el.dataset.step || "0", 10);

    el.classList.remove("is-done", "is-current", "is-pending");

    if (n < current) el.classList.add("is-done");
    else if (n === current) el.classList.add("is-current");
    else el.classList.add("is-pending");
  });
});

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".pi-click-row").forEach((row) => {
      row.addEventListener("click", () => {
        const href = row.getAttribute("data-href");
        if (href) window.location.href = href;
      });
    });
  });

