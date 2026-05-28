document.addEventListener("DOMContentLoaded", () => {
  const dataNode = document.querySelector("#stats-data");
  if (!dataNode) {
    return;
  }

  const stats = JSON.parse(dataNode.textContent);
  const palette = ["#2f6f4e", "#c97828", "#4c6f91", "#8a5d73", "#6d7f3f", "#b13d3d"];

  function renderMessage(id, message) {
    const canvas = document.querySelector(`#${id}`);
    if (!canvas) {
      return;
    }
    const panel = canvas.closest(".chart-panel");
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = message;
    canvas.replaceWith(p);
  }

  if (!window.Chart) {
    ["weeklyVolumeChart", "weeklySessionsChart", "exerciseVolumeChart", "muscleChart"].forEach((id) => {
      renderMessage(id, "Chart.js no esta disponible. Revisa la conexion o usa los datos tabulares.");
    });
    return;
  }

  function chart(id, type, labels, values, label) {
    const canvas = document.querySelector(`#${id}`);
    if (!canvas || !labels || labels.length === 0) {
      renderMessage(id, "Sin datos suficientes para este grafico.");
      return;
    }

    new Chart(canvas, {
      type,
      data: {
        labels,
        datasets: [
          {
            label,
            data: values,
            borderColor: palette[0],
            backgroundColor: type === "doughnut" ? palette : "rgba(47, 111, 78, 0.18)",
            tension: 0.25,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: type === "doughnut" },
        },
        scales:
          type === "doughnut"
            ? {}
            : {
                y: {
                  beginAtZero: true,
                  ticks: { precision: 0 },
                },
              },
      },
    });
  }

  chart("weeklyVolumeChart", "line", stats.weekly_volume.labels, stats.weekly_volume.values, "Volumen");
  chart("weeklySessionsChart", "bar", stats.weekly_sessions.labels, stats.weekly_sessions.values, "Sesiones");
  chart("exerciseVolumeChart", "bar", stats.exercise_volume.labels, stats.exercise_volume.values, "Volumen por ejercicio");
  chart("muscleChart", "doughnut", stats.muscle_distribution.labels, stats.muscle_distribution.values, "Series");
});
