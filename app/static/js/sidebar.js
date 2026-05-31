document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".menu-toggle");
  const backdrop = document.querySelector("[data-sidebar-close]");
  const navLinks = document.querySelectorAll(".side-nav a");

  function setMenu(open) {
    document.body.classList.toggle("sidebar-open", open);
    if (toggle) {
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Cerrar menu" : "Abrir menu");
    }
  }

  if (toggle) {
    toggle.addEventListener("click", () => {
      setMenu(!document.body.classList.contains("sidebar-open"));
    });
  }

  if (backdrop) {
    backdrop.addEventListener("click", () => setMenu(false));
  }

  navLinks.forEach((link) => {
    link.addEventListener("click", () => setMenu(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setMenu(false);
    }
  });
});
