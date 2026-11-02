(function () {
  const form = document.getElementById("wa-config-form");
  const status = document.getElementById("wa-config-status");
  const el = (id) => document.getElementById(id);

  async function load() {
    try {
      const config = await apiFetch("/api/whatsapp/config");
      el("wa_bot_enabled").checked = config.bot_enabled;
      el("wa_phone_number_id").value = config.phone_number_id || "";
      el("wa_owner_phone").value = config.owner_phone || "";
      el("wa_business_name").value = config.business_name || "";
      el("wa_max_party_size").value = config.max_party_size || 20;
      el("wa_opening_hours").value = config.opening_hours || "";
      el("wa_location").value = config.location || "";
      if (config.access_token_set) {
        el("wa_access_token").placeholder = "•••••••• (token saved — enter a new value to replace it)";
      }
    } catch (err) {
      showToast("Failed to load WhatsApp settings: " + err.message, true);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      access_token: el("wa_access_token").value.trim(),
      phone_number_id: el("wa_phone_number_id").value.trim(),
      owner_phone: el("wa_owner_phone").value.trim(),
      business_name: el("wa_business_name").value.trim(),
      max_party_size: parseInt(el("wa_max_party_size").value, 10) || 20,
      opening_hours: el("wa_opening_hours").value.trim(),
      location: el("wa_location").value.trim(),
      bot_enabled: el("wa_bot_enabled").checked,
    };
    try {
      await apiFetch("/api/whatsapp/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      status.textContent = "Saved ✓";
      setTimeout(() => (status.textContent = ""), 2000);
      showToast("WhatsApp settings saved");
      el("wa_access_token").value = "";
      load();
    } catch (err) {
      showToast("Failed to save WhatsApp settings: " + err.message, true);
    }
  });

  load();
})();
