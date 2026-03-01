(() => {
  const init = () => {
    const modal = document.getElementById("adminUserInfoModal");
    const body = document.getElementById("adminUserInfoModalBody");
    const panel = modal ? modal.querySelector("[data-admin-user-info-panel]") : null;
    if (!modal || !body || !panel) return;

    const openModal = () => {
      modal.classList.remove("hidden");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    };

    const closeModal = () => {
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      body.innerHTML = "Laden...";
      document.body.style.overflow = "";
    };

    const loadModalBody = async (url) => {
      const targetUrl = String(url || "").trim();
      if (!targetUrl) {
        body.innerHTML = "Fehler: URL fehlt.";
        return;
      }

      const resp = await fetch(targetUrl, { credentials: "same-origin" });
      if (!resp.ok) {
        body.innerHTML = `Fehler: ${resp.status} ${resp.statusText}`;
        return;
      }

      body.innerHTML = await resp.text();
    };

    document.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const closeEl = target.closest("[data-admin-user-info-close]");
      if (closeEl) {
        event.preventDefault();
        closeModal();
        return;
      }

      const openEl = target.closest("[data-admin-user-info-open]");
      if (openEl) {
        event.preventDefault();
        openModal();
        try {
          await loadModalBody(openEl.getAttribute("data-user-info-url") || "");
        } catch {
          body.innerHTML = "Fehler beim Laden.";
        }
        return;
      }

      if (!modal.classList.contains("hidden") && !panel.contains(target) && target.closest("#adminUserInfoModal")) {
        closeModal();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        event.preventDefault();
        closeModal();
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
