document.addEventListener("DOMContentLoaded", () => {
  const template = document.querySelector("#routineExerciseTemplate");
  if (!template) {
    return;
  }

  function nameFields(row, dayId) {
    row.querySelectorAll("[data-field]").forEach((input) => {
      input.name = `${input.dataset.field}_${dayId}`;
    });
  }

  document.querySelectorAll(".routine-edit-day").forEach((day) => {
    day.querySelectorAll(".routine-edit-exercise").forEach((row) => nameFields(row, day.dataset.dayId));
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    const day = target.closest(".routine-edit-day");

    if (target.classList.contains("add-routine-exercise") && day) {
      const row = template.content.firstElementChild.cloneNode(true);
      nameFields(row, day.dataset.dayId);
      day.querySelector("[data-exercise-list]").appendChild(row);
    }

    if (target.classList.contains("remove-routine-exercise")) {
      target.closest(".routine-edit-exercise").remove();
    }
  });
});
