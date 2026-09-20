function showToast(message, isError) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = "toast show" + (isError ? " error" : "");
  setTimeout(() => {
    toast.className = "toast";
  }, 3000);
}

async function apiFetch(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch (e) {
      // ignore
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}
