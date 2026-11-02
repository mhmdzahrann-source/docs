const list = document.getElementById("reservation-list");
const handoffSection = document.getElementById("handoff-section");
const handoffList = document.getElementById("handoff-list");
let currentStatus = "pending";

const STATUS_BADGE = {
  pending: "badge-pending",
  confirmed: "badge-active",
  declined: "badge-inactive",
  cancelled: "badge-inactive",
};

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function formatDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
}

function formatTime(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

async function loadReservations() {
  try {
    const query = currentStatus ? `?status=${encodeURIComponent(currentStatus)}` : "";
    const reservations = await apiFetch("/api/whatsapp/reservations" + query);
    if (!reservations.length) {
      list.innerHTML = `<p class="empty-state">No ${currentStatus || ""} reservations yet.</p>`;
      return;
    }
    list.innerHTML = reservations
      .map(
        (r) => `
      <div class="campaign-card reservation-card">
        <div class="reservation-when">
          <div class="reservation-date">${escapeHtml(formatDate(r.date))}</div>
          <div class="reservation-time">${escapeHtml(formatTime(r.time))}</div>
        </div>
        <div class="campaign-main">
          <div><strong><bdi>${escapeHtml(r.customer_name)}</bdi></strong> · ${escapeHtml(r.guests)} guests</div>
          <div class="campaign-post-id">
            <a href="https://wa.me/${escapeHtml(r.wa_id)}" target="_blank" rel="noopener">+${escapeHtml(r.wa_id)}</a>
            · #${r.id} · ${r.lang === "ar" ? "Arabic" : "English"}
          </div>
        </div>
        <span class="badge ${STATUS_BADGE[r.status] || ""}">${escapeHtml(r.status)}</span>
        ${
          r.status === "pending"
            ? `<div class="reservation-actions">
                 <button class="btn btn-primary" data-id="${r.id}" data-action="confirmed">Confirm</button>
                 <button class="btn btn-danger" data-id="${r.id}" data-action="declined">Decline</button>
               </div>`
            : ""
        }
      </div>`
      )
      .join("");
  } catch (err) {
    list.innerHTML = `<p class="empty-state">Failed to load reservations: ${escapeHtml(err.message)}</p>`;
  }
}

list.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const verb = button.dataset.action === "confirmed" ? "confirm" : "decline";
  if (!confirm(`${verb[0].toUpperCase() + verb.slice(1)} this booking? The customer gets a WhatsApp message.`)) return;
  button.disabled = true;
  try {
    const result = await apiFetch(`/api/whatsapp/reservations/${button.dataset.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: button.dataset.action }),
    });
    if (result.customer_notified) {
      showToast(`Booking ${button.dataset.action} — customer notified`);
    } else {
      showToast(`Saved, but the WhatsApp message failed: ${result.notify_error || "not configured"}`, true);
    }
    loadReservations();
  } catch (err) {
    button.disabled = false;
    showToast("Failed: " + err.message, true);
  }
});

document.querySelectorAll(".btn-filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".btn-filter").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
    currentStatus = button.dataset.status;
    loadReservations();
  });
});

async function loadHandoffs() {
  try {
    const handoffs = await apiFetch("/api/whatsapp/handoffs");
    handoffSection.classList.toggle("hidden", !handoffs.length);
    handoffList.innerHTML = handoffs
      .map(
        (h) => `
      <form class="handoff-item" data-wa="${escapeHtml(h.wa_id)}">
        <div class="handoff-who">
          <strong><bdi>${escapeHtml(h.profile_name || "Customer")}</bdi></strong>
          <a href="https://wa.me/${escapeHtml(h.wa_id)}" target="_blank" rel="noopener">+${escapeHtml(h.wa_id)}</a>
        </div>
        <textarea rows="2" placeholder="Type your reply..." required></textarea>
        <div class="handoff-actions">
          <button type="button" class="btn btn-filter" data-resume>Hand back to bot</button>
          <button type="submit" class="btn btn-primary">Send reply</button>
        </div>
      </form>`
      )
      .join("");
  } catch (err) {
    showToast("Failed to load chats: " + err.message, true);
  }
}

handoffList.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const textarea = form.querySelector("textarea");
  try {
    await apiFetch(`/api/whatsapp/handoffs/${form.dataset.wa}/reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: textarea.value.trim() }),
    });
    textarea.value = "";
    showToast("Reply sent");
  } catch (err) {
    showToast("Failed to send: " + err.message, true);
  }
});

handoffList.addEventListener("click", async (event) => {
  if (!event.target.matches("[data-resume]")) return;
  const form = event.target.closest("form");
  try {
    await apiFetch(`/api/whatsapp/handoffs/${form.dataset.wa}/resume`, { method: "POST" });
    showToast("The bot will answer this customer again");
    loadHandoffs();
  } catch (err) {
    showToast("Failed: " + err.message, true);
  }
});

loadReservations();
loadHandoffs();
setInterval(() => {
  loadReservations();
  loadHandoffs();
}, 30000);
