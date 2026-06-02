document.addEventListener("DOMContentLoaded", () => {
  const dataNode = document.querySelector("#measurement-data");
  if (!dataNode) {
    return;
  }

  const payload = JSON.parse(dataNode.textContent);
  const chartsByKey = new Map((payload.charts || []).map((chart) => [chart.key, chart]));
  const palette = ["#2f6f4e", "#c97828", "#4c6f91", "#8a5d73", "#6d7f3f", "#b13d3d"];

  function renderMessage(canvas, message) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = message;
    canvas.replaceWith(p);
  }

  document.querySelectorAll("[data-measurement-chart]").forEach((canvas, index) => {
    const chartData = chartsByKey.get(canvas.dataset.measurementChart);
    if (!chartData || !chartData.labels || chartData.labels.length === 0) {
      renderMessage(canvas, "Sin datos suficientes para este grafico.");
      return;
    }

    if (!window.Chart) {
      renderMessage(canvas, "Chart.js no esta disponible. Revisa la conexion o usa el historial.");
      return;
    }

    const color = palette[index % palette.length];
    const label = chartData.unit ? `${chartData.label} (${chartData.unit})` : chartData.label;
    new Chart(canvas, {
      type: "line",
      data: {
        labels: chartData.labels,
        datasets: [
          {
            label,
            data: chartData.values,
            borderColor: color,
            backgroundColor: `${color}26`,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: { precision: 1 },
          },
        },
      },
    });
  });
});
