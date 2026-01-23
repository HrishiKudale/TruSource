function qs(id){ return document.getElementById(id); }

async function acceptOffer(listingId, reqId){
  if(!confirm("Accept this buyer request?")) return;

  const res = await fetch(`/farmer/marketplace/listing/${listingId}/request/${reqId}/accept`, {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({})
  });

  const js = await res.json().catch(()=> ({}));
  if(!res.ok || js.error){
    alert(js.error || "Failed to accept request");
    return;
  }
  location.reload();
}

async function openRequestDetails(listingId, reqId){
  const modal = qs("requestDetailsModal");
  modal.classList.add("show");
  modal.setAttribute("aria-hidden","false");

  // loading placeholders
  qs("rdBuyer").textContent = "Loading...";
  qs("rdBuyerType").textContent = "Loading...";
  qs("rdPrice").textContent = "Loading...";
  qs("rdQty").textContent = "Loading...";
  qs("rdLocation").textContent = "Loading...";
  qs("rdNote").textContent = "Loading...";

  const res = await fetch(`/farmer/marketplace/listing/${listingId}/request/${reqId}/detail`);
  const js = await res.json().catch(()=> ({}));
  if(!res.ok || js.error){
    alert(js.error || "Failed to load request details");
    closeRequestDetails();
    return;
  }

  const d = js.data || {};
  qs("rdBuyer").textContent = d.buyer_name || "-";
  qs("rdBuyerType").textContent = d.buyer_type || "-";
  qs("rdPrice").textContent = `₹${d.price_value || "-"} / ${d.price_unit || "-"}`;
  qs("rdQty").textContent = `${d.requested_qty || "-"} kg`;
  qs("rdLocation").textContent = d.location || "-";
  qs("rdNote").textContent = d.note || "-";

  qs("rdAcceptBtn").onclick = () => acceptOffer(listingId, reqId);
}

function closeRequestDetails(){
  const modal = qs("requestDetailsModal");
  modal.classList.remove("show");
  modal.setAttribute("aria-hidden","true");
}

window.acceptOffer = acceptOffer;
window.openRequestDetails = openRequestDetails;
window.closeRequestDetails = closeRequestDetails;
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;

  const action = btn.dataset.action;

  if (action === "viewBuyer") {
    const buyerId = btn.dataset.buyer;
    if (!buyerId) return alert("Buyer id missing");
    // You can route to buyer info page if you have one
    window.location.href = `/farmer/pricing/info/buyer/${encodeURIComponent(buyerId)}`;
  }

  if (action === "downloadInvoice") {
    const listingId = btn.dataset.id;
    window.location.href = `/farmer/marketplace/listing/${encodeURIComponent(listingId)}/invoice`;
  }
});
function acceptRequest(listingId, reqId) {
  fetch(`/farmer/marketplace/listing/${listingId}/request/${reqId}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}) // accept current offer
  })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Failed to accept request");
      // reload to show Approved UI
      window.location.reload();
    })
    .catch((err) => {
      alert(err.message || "Something went wrong");
    });
}

function openRequestModal(reqId) {
  const el = document.getElementById(`reqdata-${reqId}`);
  if (!el) return;

  let obj = {};
  try {
    obj = JSON.parse(el.dataset.json || "{}");
  } catch (e) {}

  const modal = document.getElementById("requestModal");
  const body = document.getElementById("modalBody");

  const nego = Array.isArray(obj.negotiations) ? obj.negotiations : [];
  const negoHtml = nego.length
    ? `<div style="margin-top:10px;">
         <div style="font-weight:800; margin-bottom:6px;">Negotiations</div>
         ${nego.map(n => `
            <div style="border:1px solid #e5e7eb; padding:10px; border-radius:12px; margin-bottom:8px;">
              <div><b>By:</b> ${n.by || "-"}</div>
              <div><b>Price:</b> ₹${n.price_value || "-"} / ${n.price_unit || "kg"}</div>
              <div><b>Note:</b> ${n.note || "-"}</div>
            </div>
         `).join("")}
       </div>`
    : `<div style="margin-top:10px; color:#6b7280;">No negotiation history.</div>`;

  body.innerHTML = `
    <div><b>Buyer:</b> ${obj.buyer_name || "-"}</div>
    <div><b>Buyer Type:</b> ${obj.buyer_type || "-"}</div>
    <div><b>Requested Qty:</b> ${obj.requested_qty || "-"} ${obj.price_unit || "kg"}</div>
    <div><b>Price:</b> ₹${obj.price_value || "-"} / ${obj.price_unit || "kg"}</div>
    <div><b>Status:</b> ${obj.status || "-"}</div>
    <div><b>Note:</b> ${obj.note || "-"}</div>
    ${negoHtml}
  `;

  modal.classList.remove("hidden");
}

function closeRequestModal() {
  const modal = document.getElementById("requestModal");
  modal.classList.add("hidden");
}
