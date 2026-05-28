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

  function addSet(block) {
    const clone = setTemplate.content.firstElementChild.cloneNode(true);
    block.querySelector(".sets-body").appendChild(clone);
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
  });

  addExerciseButton.addEventListener("click", addExercise);

  if (!blocksContainer.querySelector(".workout-exercise")) {
    addExercise();
  } else {
    blocksContainer.querySelectorAll(".workout-exercise").forEach((block) => {
      if (!block.querySelector(".set-row")) {
        addSet(block);
      }
    });
    reindexBlocks();
  }
});
