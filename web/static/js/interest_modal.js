// FILE: web/static/js/interest_modal.js  (обновлено — 2026-02-16)
// PURPOSE: Навешивает handlers после загрузки DOM (работает даже если скрипт подключён в <head>).

(() => {
  const init = () => {
    const modal = document.getElementById("interestModal");
    const body = document.getElementById("interestModalBody");
    if (!modal || !body) return;

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

    const loadIssueTable = async (issueId) => {
      const id = String(issueId || "").trim();
      if (!id) {
        body.innerHTML = "Fehler: issue_id fehlt.";
        return;
      }

      const url = `/issue/${encodeURIComponent(id)}/interest-table/`;
      const resp = await fetch(url, { credentials: "same-origin" });
      if (!resp.ok) {
        body.innerHTML = `Fehler: ${resp.status} ${resp.statusText}`;
        return;
      }

      body.innerHTML = await resp.text();
    };

    document.addEventListener("click", async (ev) => {
      const t = ev.target;
      if (!(t instanceof Element)) return;

      const openEl = t.closest("[data-interest-modal-open]");
      if (openEl) {
        ev.preventDefault();
        const issueId = openEl.getAttribute("data-issue-id") || "";
        openModal();
        try {
          await loadIssueTable(issueId);
        } catch {
          body.innerHTML = "Fehler beim Laden.";
        }
        return;
      }

      if (t.closest("[data-interest-modal-close]")) {
        ev.preventDefault();
        closeModal();
      }
    });

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && !modal.classList.contains("hidden")) {
        ev.preventDefault();
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
