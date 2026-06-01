document.addEventListener("DOMContentLoaded", () => {
  const blocksContainer = document.querySelector("#exerciseBlocks");
  const addExerciseButton = document.querySelector("#addExercise");
  const exerciseTemplate = document.querySelector("#exerciseBlockTemplate");
  const setTemplate = document.querySelector("#setRowTemplate");

  if (!blocksContainer || !addExerciseButton || !exerciseTemplate || !setTemplate) {
    return;
  }

  function updateSetRows(block, exerciseIndex) {
    const rows = block.querySelectorAll(".set-row");
    rows.forEach((row, rowIndex) => {
      const numberCell = row.querySelector(".set-number");
      if (numberCell) {
        numberCell.textContent = String(rowIndex + 1);
      }
      row.querySelectorAll("[data-set-field]").forEach((input) => {
        input.name = `set_${input.dataset.setField}_${exerciseIndex}`;
      });
    });
  }

  function reindexBlocks() {
    blocksContainer.querySelectorAll(".workout-exercise").forEach((block, index) => {
      block.dataset.exerciseIndex = String(index);
      updateSetRows(block, index);
    });
  }

  function fieldInput(row, field) {
    return row.querySelector(`[data-set-field="${field}"]`);
  }

  function isSetDone(row) {
    const button = row.querySelector("[data-set-done]");
    return Boolean(button && button.getAttribute("aria-pressed") === "true");
  }

  function syncSetDoneState(row) {
    const button = row.querySelector("[data-set-done]");
    const done = isSetDone(row);
    row.classList.toggle("is-done", done);
    if (button) {
      button.classList.toggle("is-active", done);
      button.setAttribute("aria-pressed", String(done));
    }
  }

  function selectedExerciseLastWeight(block) {
    const selectedOption = block.querySelector('select[name="exercise_id"] option:checked');
    return selectedOption ? selectedOption.dataset.lastWeight || "0" : "0";
  }

  function applyLastWeightToOpenSets(block) {
    const lastWeight = selectedExerciseLastWeight(block);
    block.querySelectorAll(".set-row").forEach((row) => {
      if (isSetDone(row)) {
        return;
      }
      const weightInput = fieldInput(row, "weight");
      if (weightInput) {
        weightInput.value = lastWeight;
      }
    });
  }

  function copyFieldValueToRows(block, sourceInput) {
    if (!["weight", "reps"].includes(sourceInput.dataset.setField) || sourceInput.value === "") {
      return;
    }

    const field = sourceInput.dataset.setField;
    block.querySelectorAll(".set-row").forEach((row) => {
      const input = fieldInput(row, field);
      if (input && input !== sourceInput && !isSetDone(row)) {
        input.value = sourceInput.value;
      }
    });
  }

  function copyLastSetValues(block, targetRow) {
    const rows = Array.from(block.querySelectorAll(".set-row"));
    const sourceRow = rows[rows.length - 2];
    if (!sourceRow) {
      const weightInput = fieldInput(targetRow, "weight");
      if (weightInput) {
        weightInput.value = selectedExerciseLastWeight(block);
      }
      syncSetDoneState(targetRow);
      return;
    }

    ["weight", "reps"].forEach((field) => {
      const sourceInput = fieldInput(sourceRow, field);
      const targetInput = fieldInput(targetRow, field);
      if (sourceInput && targetInput && sourceInput.value !== "") {
        targetInput.value = sourceInput.value;
      }
    });
    syncSetDoneState(targetRow);
  }

  function addSet(block) {
    const clone = setTemplate.content.firstElementChild.cloneNode(true);
    block.querySelector(".sets-body").appendChild(clone);
    copyLastSetValues(block, clone);
    reindexBlocks();
  }

  function addExercise() {
    const clone = exerciseTemplate.content.firstElementChild.cloneNode(true);
    blocksContainer.appendChild(clone);
    window.ArcaSearchableSelect?.init(clone);
    window.ArcaExerciseMedia?.init(clone);
    addSet(clone);
    reindexBlocks();
  }

  blocksContainer.addEventListener("click", (event) => {
    const target = event.target;
    const block = target.closest(".workout-exercise");
    if (!block) {
      return;
    }

    if (target.classList.contains("add-set")) {
      addSet(block);
    }

    if (target.classList.contains("remove-set")) {
      target.closest(".set-row").remove();
      if (!block.querySelector(".set-row")) {
        addSet(block);
      }
      reindexBlocks();
    }

    if (target.classList.contains("remove-exercise")) {
      block.remove();
      if (!blocksContainer.querySelector(".workout-exercise")) {
        addExercise();
      }
      reindexBlocks();
    }

    const doneButton = target.closest("[data-set-done]");
    if (doneButton) {
      doneButton.setAttribute(
        "aria-pressed",
        doneButton.getAttribute("aria-pressed") === "true" ? "false" : "true",
      );
      syncSetDoneState(doneButton.closest(".set-row"));
    }
  });

  function handleSetFieldUpdate(event) {
    const target = event.target;
    const block = target.closest(".workout-exercise");
    if (!block || !target.matches("[data-set-field]")) {
      return;
    }

    copyFieldValueToRows(block, target);
  }

  blocksContainer.addEventListener("input", handleSetFieldUpdate);
  blocksContainer.addEventListener("change", handleSetFieldUpdate);

  blocksContainer.addEventListener("change", (event) => {
    const target = event.target;
    const block = target.closest(".workout-exercise");
    if (!block || !target.matches('select[name="exercise_id"]')) {
      return;
    }
    applyLastWeightToOpenSets(block);
  });

  addExerciseButton.addEventListener("click", addExercise);

  if (!blocksContainer.querySelector(".workout-exercise")) {
    addExercise();
  } else {
    blocksContainer.querySelectorAll(".workout-exercise").forEach((block) => {
      if (!block.querySelector(".set-row")) {
        addSet(block);
      }
      block.querySelectorAll(".set-row").forEach(syncSetDoneState);
    });
    window.ArcaSearchableSelect?.init(blocksContainer);
    window.ArcaExerciseMedia?.init(blocksContainer);
    reindexBlocks();
  }
});
