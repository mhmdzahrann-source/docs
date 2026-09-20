const form = document.getElementById("config-form");
const status = document.getElementById("config-status");

async function loadConfig() {
  try {
    const config = await apiFetch("/api/config");
    document.getElementById("page_id").value = config.page_id || "";
    document.getElementById("instagram_business_account_id").value = config.instagram_business_account_id || "";
    if (config.access_token_set) {
      document.getElementById("access_token").placeholder = "•••••••• (token saved — enter a new value to replace it)";
    }
  } catch (err) {
    showToast("Failed to load settings: " + err.message, true);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    access_token: document.getElementById("access_token").value.trim(),
    page_id: document.getElementById("page_id").value.trim(),
    instagram_business_account_id: document.getElementById("instagram_business_account_id").value.trim(),
  };
  try {
    await apiFetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    status.textContent = "Saved ✓";
    setTimeout(() => (status.textContent = ""), 2000);
    showToast("Settings saved");
    document.getElementById("access_token").value = "";
    loadConfig();
  } catch (err) {
    showToast("Failed to save settings: " + err.message, true);
  }
});

loadConfig();
