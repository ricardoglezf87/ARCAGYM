(() => {
  function selectedOption(select) {
    return select.options[select.selectedIndex] || null;
  }

  function updatePreview(preview) {
    const scope = preview.closest(".workout-exercise, .routine-edit-exercise") || preview.parentElement;
    const select = scope ? scope.querySelector("select[data-exercise-select]") : null;
    const option = select ? selectedOption(select) : null;
    const image = preview.querySelector("[data-exercise-preview-image]");
    const name = preview.querySelector("[data-exercise-preview-name]");
    const meta = preview.querySelector("[data-exercise-preview-meta]");
    const link = preview.querySelector("[data-exercise-preview-link]");
    const imageUrl = option?.dataset.imageUrl || "";
    const isTogglePreview = preview.dataset.exercisePreviewMode === "toggle";
    const canShow = Boolean(option && option.value && imageUrl);

    preview.hidden = !canShow || (isTogglePreview && preview.dataset.previewOpen !== "true");
    if (name) {
      name.textContent = option ? option.textContent.trim() : "";
    }
    if (meta) {
      meta.textContent = option?.dataset.meta || "";
    }
    if (image) {
      image.hidden = !imageUrl;
      if (imageUrl) {
        image.src = imageUrl;
        image.alt = option.dataset.imageAlt || option.textContent.trim();
      }
    }
    if (link) {
      link.hidden = !option?.dataset.detailUrl;
      if (option?.dataset.detailUrl) {
        link.href = option.dataset.detailUrl;
      }
    }
    const toggle = scope?.querySelector("[data-exercise-preview-toggle]");
    if (toggle) {
      toggle.hidden = !canShow;
      toggle.disabled = !canShow;
      toggle.setAttribute("aria-expanded", String(!preview.hidden));
      toggle.textContent = preview.hidden ? "Ver imagen" : "Ocultar imagen";
    }
  }

  function init(root = document) {
    root.querySelectorAll("[data-exercise-preview]").forEach(updatePreview);
  }

  document.addEventListener("change", (event) => {
    const select = event.target.closest("select[data-exercise-select]");
    if (!select) {
      return;
    }
    const scope = select.closest(".workout-exercise, .routine-edit-exercise") || document;
    scope.querySelectorAll("[data-exercise-preview]").forEach(updatePreview);
  });

  document.addEventListener("click", (event) => {
    const previewButton = event.target.closest("[data-exercise-preview-toggle]");
    if (previewButton) {
      const scope = previewButton.closest(".workout-exercise, .routine-edit-exercise") || document;
      const preview = scope.querySelector("[data-exercise-preview]");
      if (!preview) {
        return;
      }
      const willOpen = preview.hidden;
      preview.dataset.previewOpen = String(willOpen);
      updatePreview(preview);
      return;
    }

    const button = event.target.closest("[data-image-toggle]");
    if (!button) {
      return;
    }
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    if (!panel) {
      return;
    }
    const isHidden = !panel.hidden;
    panel.hidden = isHidden;
    button.setAttribute("aria-expanded", String(!isHidden));
    button.textContent = isHidden ? "Ver imagen" : "Ocultar imagen";
  });

  window.ArcaExerciseMedia = { init };
  document.addEventListener("DOMContentLoaded", () => init(document));
})();
