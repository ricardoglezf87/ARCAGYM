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
    const checkbox = row.querySelector("[data-set-done]");
    return Boolean(checkbox && checkbox.checked);
  }

  function syncSetDoneState(row) {
    row.classList.toggle("is-done", isSetDone(row));
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

    if (target.matches("[data-set-done]")) {
      syncSetDoneState(target.closest(".set-row"));
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
    reindexBlocks();
  }
});
