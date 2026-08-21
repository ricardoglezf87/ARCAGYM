document.addEventListener("DOMContentLoaded", () => {
  const categoryFilter = document.querySelector("#clinical-entry-category");
  const searchFilter = document.querySelector("#clinical-entry-search");
  const rows = [...document.querySelectorAll("[data-clinical-row]")];
  const visibleCount = document.querySelector("#clinical-visible-count");
  const emptyMessage = document.querySelector("#clinical-entry-empty");

  const normalize = (value) =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

  const applyEntryFilters = () => {
    const category = categoryFilter?.value || "";
    const search = normalize(searchFilter?.value);
    let count = 0;
    rows.forEach((row) => {
      const matchesCategory = !category || row.dataset.category === category;
      const matchesSearch = !search || normalize(row.dataset.search).includes(search);
      const isVisible = matchesCategory && matchesSearch;
      row.hidden = !isVisible;
      if (isVisible) {
        count += 1;
      }
    });
    if (visibleCount) {
      visibleCount.textContent = String(count);
    }
    if (emptyMessage) {
      emptyMessage.hidden = count !== 0;
    }
  };

  categoryFilter?.addEventListener("change", applyEntryFilters);
  searchFilter?.addEventListener("input", applyEntryFilters);

  const dataNode = document.querySelector("#clinical-chart-data");
  const canvas = document.querySelector("#clinical-variable-chart");
  if (!dataNode || !canvas) {
    return;
  }
  const payload = JSON.parse(dataNode.textContent);
  if (!payload || !payload.datasets?.length) {
    return;
  }
  if (!window.Chart) {
    const message = document.createElement("p");
    message.className = "empty";
    message.textContent = "El grafico no esta disponible. Los valores siguen visibles en la tabla.";
    canvas.replaceWith(message);
    return;
  }

  const colors = ["#2f6f4e", "#c97828", "#4c6f91", "#8a5d73", "#6d7f3f", "#b13d3d"];
  new Chart(canvas, {
    type: "line",
    data: {
      labels: payload.labels,
      datasets: payload.datasets.map((dataset, index) => {
        const color = colors[index % colors.length];
        return {
          label: dataset.label,
          data: dataset.values,
          borderColor: color,
          backgroundColor: `${color}22`,
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.2,
          spanGaps: false,
        };
      }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: payload.datasets.length > 1, position: "bottom" },
      },
      scales: {
        y: { beginAtZero: false },
      },
    },
  });
});
