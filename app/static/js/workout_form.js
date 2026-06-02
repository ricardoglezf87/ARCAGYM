document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".workout-form");
  const blocksContainer = document.querySelector("#exerciseBlocks");
  const addExerciseButton = document.querySelector("#addExercise");
  const exerciseTemplate = document.querySelector("#exerciseBlockTemplate");
  const setTemplate = document.querySelector("#setRowTemplate");
  const draftBanner = document.querySelector("[data-draft-banner]");
  const discardDraftButton = document.querySelector("[data-draft-discard]");
  const draftStatus = document.querySelector("[data-draft-status]");

  if (!form || !blocksContainer || !addExerciseButton || !exerciseTemplate || !setTemplate) {
    return;
  }

  const draftKey = `${form.dataset.workoutDraftBase}:${window.location.pathname}${window.location.search}`;
  const pendingClearKey = "arcagym:workout-draft:pending-clear";
  let saveTimer = null;
  let statusTimer = null;
  let isRestoring = false;

  function initRoutinePicker() {
    const picker = document.querySelector("[data-routine-picker]");
    if (!picker) {
      return;
    }

    const routineSelect = picker.querySelector("[data-routine-select]");
    const submitButton = picker.querySelector("[data-routine-submit]");
    const helpText = picker.querySelector("[data-routine-help]");
    const canClearCurrentRoutine = picker.dataset.hasCurrentRoutine === "1";
    if (!routineSelect || !submitButton) {
      return;
    }

    function updateState() {
      const hasRoutine = routineSelect.value !== "";
      submitButton.disabled = !hasRoutine && !canClearCurrentRoutine;
      if (helpText) {
        helpText.hidden = hasRoutine || canClearCurrentRoutine;
      }
    }

    picker.addEventListener("submit", (event) => {
      if (!submitButton.disabled) {
        return;
      }
      event.preventDefault();
      if (helpText) {
        helpText.hidden = false;
      }
    });
    routineSelect.addEventListener("change", updateState);
    updateState();
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

  function applySetValues(row, values) {
    ["weight", "reps", "rpe", "rest", "notes"].forEach((field) => {
      const input = fieldInput(row, field);
      if (input && Object.prototype.hasOwnProperty.call(values, field)) {
        input.value = values[field] ?? "";
      }
    });
    const doneButton = row.querySelector("[data-set-done]");
    if (doneButton) {
      doneButton.setAttribute("aria-pressed", String(Boolean(values.done)));
    }
    syncSetDoneState(row);
  }

  function addSet(block, values = null, options = {}) {
    const clone = setTemplate.content.firstElementChild.cloneNode(true);
    block.querySelector(".sets-body").appendChild(clone);
    if (values) {
      applySetValues(clone, values);
    } else if (options.copyPrevious !== false) {
      copyLastSetValues(block, clone);
    } else {
      syncSetDoneState(clone);
    }
    if (options.reindex !== false) {
      reindexBlocks();
    }
    return clone;
  }

  function addExercise(entry = null, options = {}) {
    const clone = exerciseTemplate.content.firstElementChild.cloneNode(true);
    blocksContainer.appendChild(clone);

    if (entry) {
      const select = clone.querySelector('select[name="exercise_id"]');
      const notesInput = clone.querySelector('input[name="exercise_notes"]');
      if (select && entry.exercise_id) {
        select.value = entry.exercise_id;
      }
      if (notesInput) {
        notesInput.value = entry.notes || "";
      }
      const sets = Array.isArray(entry.sets) ? entry.sets : [];
      if (sets.length > 0) {
        sets.forEach((set) => addSet(clone, set, { reindex: false }));
      } else {
        addSet(clone, null, { copyPrevious: false, reindex: false });
      }
    } else {
      addSet(clone, null, { reindex: false });
    }

    if (options.init !== false) {
      window.ArcaSearchableSelect?.init(clone);
      window.ArcaExerciseMedia?.init(clone);
    }
    reindexBlocks();
    return clone;
  }

  function formFieldValue(name) {
    const input = form.querySelector(`[name="${name}"]`);
    return input ? input.value : "";
  }

  function setFormFieldValue(name, value) {
    const input = form.querySelector(`[name="${name}"]`);
    if (input && value !== undefined && value !== null) {
      input.value = value;
    }
  }

  function serializeDraft() {
    return {
      version: 1,
      savedAt: new Date().toISOString(),
      date: formFieldValue("date"),
      notes: formFieldValue("notes"),
      saved_routine_id: formFieldValue("saved_routine_id"),
      routine_day_name: formFieldValue("routine_day_name"),
      exercises: Array.from(blocksContainer.querySelectorAll(".workout-exercise")).map((block) => ({
        exercise_id: formFieldValueFrom(block, 'select[name="exercise_id"]'),
        notes: formFieldValueFrom(block, 'input[name="exercise_notes"]'),
        sets: Array.from(block.querySelectorAll(".set-row")).map((row) => ({
          weight: fieldInput(row, "weight")?.value || "",
          reps: fieldInput(row, "reps")?.value || "",
          rpe: fieldInput(row, "rpe")?.value || "",
          rest: fieldInput(row, "rest")?.value || "",
          notes: fieldInput(row, "notes")?.value || "",
          done: isSetDone(row),
        })),
      })),
    };
  }

  function formFieldValueFrom(root, selector) {
    const input = root.querySelector(selector);
    return input ? input.value : "";
  }

  function setDraftStatus(message) {
    if (!draftStatus) {
      return;
    }
    draftStatus.textContent = message;
    clearTimeout(statusTimer);
    if (message) {
      statusTimer = setTimeout(() => {
        draftStatus.textContent = "";
      }, 1800);
    }
  }

  function saveDraft() {
    if (isRestoring) {
      return;
    }
    try {
      localStorage.setItem(draftKey, JSON.stringify(serializeDraft()));
      setDraftStatus("Borrador guardado");
    } catch (error) {
      setDraftStatus("");
    }
  }

  function scheduleDraftSave() {
    if (isRestoring) {
      return;
    }
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraft, 120);
  }

  function readDraft() {
    try {
      const rawDraft = localStorage.getItem(draftKey);
      return rawDraft ? JSON.parse(rawDraft) : null;
    } catch (error) {
      return null;
    }
  }

  function restoreDraft(draft) {
    if (!draft || draft.version !== 1 || !Array.isArray(draft.exercises)) {
      return false;
    }

    isRestoring = true;
    setFormFieldValue("date", draft.date);
    setFormFieldValue("notes", draft.notes);
    setFormFieldValue("saved_routine_id", draft.saved_routine_id);
    setFormFieldValue("routine_day_name", draft.routine_day_name);
    blocksContainer.innerHTML = "";
    draft.exercises.forEach((entry) => addExercise(entry, { init: false }));
    if (!blocksContainer.querySelector(".workout-exercise")) {
      addExercise(null, { init: false });
    }
    reindexBlocks();
    isRestoring = false;
    if (draftBanner) {
      draftBanner.hidden = false;
    }
    setDraftStatus("Borrador recuperado");
    return true;
  }

  blocksContainer.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const block = target.closest(".workout-exercise");
    if (!block) {
      return;
    }

    let changed = false;

    if (target.closest(".add-set")) {
      addSet(block);
      changed = true;
    }

    const removeSetButton = target.closest(".remove-set");
    if (removeSetButton) {
      removeSetButton.closest(".set-row").remove();
      if (!block.querySelector(".set-row")) {
        addSet(block);
      }
      reindexBlocks();
      changed = true;
    }

    if (target.closest(".remove-exercise")) {
      block.remove();
      if (!blocksContainer.querySelector(".workout-exercise")) {
        addExercise();
      }
      reindexBlocks();
      changed = true;
    }

    const doneButton = target.closest("[data-set-done]");
    if (doneButton) {
      doneButton.setAttribute(
        "aria-pressed",
        doneButton.getAttribute("aria-pressed") === "true" ? "false" : "true",
      );
      syncSetDoneState(doneButton.closest(".set-row"));
      changed = true;
    }

    if (changed) {
      scheduleDraftSave();
    }
  });

  function handleSetFieldUpdate(event) {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
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
    if (!(target instanceof Element)) {
      return;
    }
    const block = target.closest(".workout-exercise");
    if (!block || !target.matches('select[name="exercise_id"]')) {
      return;
    }
    applyLastWeightToOpenSets(block);
  });

  form.addEventListener("input", scheduleDraftSave);
  form.addEventListener("change", scheduleDraftSave);

  form.addEventListener("submit", () => {
    saveDraft();
    sessionStorage.setItem(pendingClearKey, JSON.stringify([draftKey]));
  });

  addExerciseButton.addEventListener("click", () => {
    addExercise();
    scheduleDraftSave();
  });

  discardDraftButton?.addEventListener("click", () => {
    localStorage.removeItem(draftKey);
    sessionStorage.removeItem(pendingClearKey);
    window.location.reload();
  });

  initRoutinePicker();

  const restoredDraft = restoreDraft(readDraft());

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

  if (!restoredDraft) {
    setDraftStatus("");
  }
});
