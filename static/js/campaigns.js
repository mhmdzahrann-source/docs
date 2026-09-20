const listEl = document.getElementById("campaign-list");
const modal = document.getElementById("campaign-modal");
const form = document.getElementById("campaign-form");
const modalTitle = document.getElementById("modal-title");
const deleteBtn = document.getElementById("delete-campaign-btn");
const postIdInput = document.getElementById("post_id");
const previewBox = document.getElementById("post-preview");
const previewImg = document.getElementById("post-preview-img");
const previewCaption = document.getElementById("post-preview-caption");
const previewError = document.getElementById("post-preview-error");

let campaigns = [];

function openModal(campaign) {
  form.reset();
  previewBox.classList.add("hidden");
  if (campaign) {
    modalTitle.textContent = "Edit Campaign";
    document.getElementById("campaign_id").value = campaign.id;
    postIdInput.value = campaign.post_id;
    document.getElementById("keywords").value = campaign.keywords;
    document.getElementById("comment_reply").value = campaign.comment_reply;
    document.getElementById("dm_message").value = campaign.dm_message;
    document.getElementById("is_active").checked = campaign.is_active;
    deleteBtn.classList.remove("hidden");
    if (campaign.post_thumbnail_url) {
      showPreview({ thumbnail_url: campaign.post_thumbnail_url, caption: campaign.post_caption });
    }
  } else {
    modalTitle.textContent = "New Campaign";
    document.getElementById("campaign_id").value = "";
    document.getElementById("is_active").checked = true;
    deleteBtn.classList.add("hidden");
  }
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
}

document.getElementById("new-campaign-btn").addEventListener("click", () => openModal(null));
document.getElementById("modal-close").addEventListener("click", closeModal);
modal.addEventListener("click", (e) => {
  if (e.target === modal) closeModal();
});

function showPreview(data) {
  previewError.textContent = "";
  if (data.error) {
    previewBox.classList.remove("hidden");
    previewImg.style.display = "none";
    previewError.textContent = data.error;
    previewCaption.textContent = "";
    return;
  }
  previewBox.classList.remove("hidden");
  if (data.thumbnail_url) {
    previewImg.src = data.thumbnail_url;
    previewImg.style.display = "block";
  } else {
    previewImg.style.display = "none";
  }
  previewCaption.textContent = data.caption ? data.caption.slice(0, 140) : "(no caption)";
}

postIdInput.addEventListener("blur", async () => {
  const postId = postIdInput.value.trim();
  if (!postId) return;
  try {
    const data = await apiFetch(`/api/post-preview?post_id=${encodeURIComponent(postId)}`);
    showPreview(data);
  } catch (err) {
    showPreview({ error: err.message });
  }
});

function renderCampaigns() {
  if (!campaigns.length) {
    listEl.innerHTML = '<p class="empty-state">No campaigns yet. Click "New Campaign" to create your first automation.</p>';
    return;
  }
  listEl.innerHTML = "";
  campaigns.forEach((campaign) => {
    const card = document.createElement("div");
    card.className = "campaign-card";
    const keywordSpans = campaign.keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean)
      .map((k) => `<span>${escapeHtml(k)}</span>`)
      .join("");
    card.innerHTML = `
      <img class="campaign-thumb" src="${campaign.post_thumbnail_url || ""}" onerror="this.style.visibility='hidden'" />
      <div class="campaign-main">
        <div class="campaign-post-id">Post ID: ${escapeHtml(campaign.post_id)}</div>
        <div class="campaign-keywords">${keywordSpans}</div>
      </div>
      <span class="badge ${campaign.is_active ? "badge-active" : "badge-inactive"}">${campaign.is_active ? "Active" : "Inactive"}</span>
    `;
    card.addEventListener("click", () => openModal(campaign));
    listEl.appendChild(card);
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function loadCampaigns() {
  try {
    campaigns = await apiFetch("/api/campaigns");
    renderCampaigns();
  } catch (err) {
    listEl.innerHTML = `<p class="empty-state">Failed to load campaigns: ${escapeHtml(err.message)}</p>`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.getElementById("campaign_id").value;
  const payload = {
    post_id: postIdInput.value.trim(),
    keywords: document.getElementById("keywords").value.trim(),
    comment_reply: document.getElementById("comment_reply").value.trim(),
    dm_message: document.getElementById("dm_message").value.trim(),
    is_active: document.getElementById("is_active").checked,
  };
  try {
    if (id) {
      await apiFetch(`/api/campaigns/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      showToast("Campaign updated");
    } else {
      await apiFetch("/api/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      showToast("Campaign created");
    }
    closeModal();
    loadCampaigns();
  } catch (err) {
    showToast("Failed to save campaign: " + err.message, true);
  }
});

deleteBtn.addEventListener("click", async () => {
  const id = document.getElementById("campaign_id").value;
  if (!id || !confirm("Delete this campaign?")) return;
  try {
    await apiFetch(`/api/campaigns/${id}`, { method: "DELETE" });
    showToast("Campaign deleted");
    closeModal();
    loadCampaigns();
  } catch (err) {
    showToast("Failed to delete campaign: " + err.message, true);
  }
});

loadCampaigns();
