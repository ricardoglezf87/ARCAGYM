(() => {
  const SELECTOR = "select[data-searchable-select]";
  const MAX_RESULTS = 12;

  function normalize(value) {
    return (value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function optionText(option) {
    return `${option.textContent || ""} ${option.dataset.search || ""}`;
  }

  function matchesQuery(option, query) {
    if (!query) {
      return true;
    }
    const haystack = normalize(optionText(option));
    return query.split(/\s+/).every((token) => haystack.includes(token));
  }

  function selectedOption(select) {
    return select.options[select.selectedIndex] || select.options[0] || null;
  }

  function closeAll(except) {
    document.querySelectorAll(".search-select.is-open").forEach((control) => {
      if (control !== except) {
        control.classList.remove("is-open");
      }
    });
  }

  function commit(select, input, option) {
    if (!option) {
      return;
    }
    select.value = option.value;
    input.value = option.textContent.trim();
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function renderOptions(control, select, input, list) {
    const query = normalize(input.value);
    const options = Array.from(select.options)
      .filter((option) => !option.disabled)
      .filter((option) => matchesQuery(option, query))
      .slice(0, MAX_RESULTS);

    list.innerHTML = "";
    if (!options.length) {
      const empty = document.createElement("div");
      empty.className = "search-select-empty";
      empty.textContent = "Sin resultados";
      list.appendChild(empty);
      control.classList.add("is-open");
      return;
    }

    options.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-select-option";
      button.textContent = option.textContent.trim();
      button.addEventListener("mousedown", (event) => {
        event.preventDefault();
        commit(select, input, option);
        control.classList.remove("is-open");
      });
      list.appendChild(button);
    });
    control.classList.add("is-open");
  }

  function initSelect(select) {
    if (select.dataset.searchableReady === "true") {
      return;
    }
    select.dataset.searchableReady = "true";
    select.classList.add("searchable-native");

    const control = document.createElement("div");
    control.className = "search-select";

    const input = document.createElement("input");
    input.type = "search";
    input.autocomplete = "off";
    input.className = "search-select-input";
    input.placeholder = select.dataset.searchPlaceholder || "Buscar";
    input.value = selectedOption(select)?.textContent.trim() || "";

    const list = document.createElement("div");
    list.className = "search-select-list";

    control.append(input, list);
    select.insertAdjacentElement("afterend", control);

    input.addEventListener("focus", () => {
      closeAll(control);
      renderOptions(control, select, input, list);
    });
    input.addEventListener("input", () => renderOptions(control, select, input, list));
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        control.classList.remove("is-open");
        input.value = selectedOption(select)?.textContent.trim() || "";
      }
      if (event.key === "Enter") {
        const firstOption = list.querySelector(".search-select-option");
        if (firstOption) {
          event.preventDefault();
          firstOption.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
        }
      }
    });
    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        control.classList.remove("is-open");
        input.value = selectedOption(select)?.textContent.trim() || "";
      }, 120);
    });
    select.addEventListener("change", () => {
      input.value = selectedOption(select)?.textContent.trim() || "";
    });
  }

  function init(root = document) {
    root.querySelectorAll(SELECTOR).forEach(initSelect);
  }

  window.ArcaSearchableSelect = { init };
  document.addEventListener("DOMContentLoaded", () => init(document));
})();
