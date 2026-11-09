document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".workout-form");
  const blocksContainer = document.querySelector("#exerciseBlocks");
  const addExerciseButton = document.querySelector("#addExercise");
  const exerciseTemplate = document.querySelector("#exerciseBlockTemplate");
  const setTemplate = document.querySelector("#setRowTemplate");
  const draftBanner = document.querySelector("[data-draft-banner]");
  const discardDraftButton = document.querySelector("[data-draft-discard]");
  const draftStatus = document.querySelector("[data-draft-status]");
  const completedTools = document.querySelector("[data-completed-tools]");
  const completedCount = document.querySelector("[data-completed-count]");
  const showCompletedButton = document.querySelector("[data-show-completed]");
  const muscleMaps = document.querySelectorAll(".muscle-map");
  const muscleMapStatus = document.querySelector("[data-muscle-map-status]");
  const exerciseProgress = document.querySelector("[data-exercise-progress]");

  if (!form || !blocksContainer || !addExerciseButton || !exerciseTemplate || !setTemplate) {
    return;
  }

  const draftKey = `${form.dataset.workoutDraftBase}:${window.location.pathname}`;
  const pendingClearKey = "arcagym:workout-draft:pending-clear";
  let saveTimer = null;
  let statusTimer = null;
  let isRestoring = false;
  let restoredLegacyDraftKey = null;
  let showCompletedExercises = false;

  function routinePickerValue(name) {
    const input = document.querySelector(`[data-routine-picker] [name="${name}"]`);
    return input ? input.value : "";
  }

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

  function syncRoutinePickerFromHidden() {
    const picker = document.querySelector("[data-routine-picker]");
    const routineSelect = picker?.querySelector("[data-routine-select]");
    const daySelect = picker?.querySelector('[name="routine_day_id"]');
    const routineId = formFieldValue("saved_routine_id");
    const routineDayName = formFieldValue("routine_day_name");

    if (routineSelect && routineId) {
      const option = routineSelect.querySelector(`option[value="${CSS.escape(routineId)}"]`);
      if (option) {
        routineSelect.value = routineId;
        routineSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    if (daySelect && routineDayName && !daySelect.value) {
      const matchingOption = Array.from(daySelect.options).find((option) =>
        option.textContent.trim().startsWith(routineDayName),
      );
      if (matchingOption) {
        daySelect.value = matchingOption.value;
        return;
      }
      if (daySelect.disabled) {
        daySelect.innerHTML = "";
        const restoredOption = document.createElement("option");
        restoredOption.value = "";
        restoredOption.textContent = routineDayName;
        restoredOption.selected = true;
        daySelect.appendChild(restoredOption);
      }
    }
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
      button.setAttribute("aria-label", done ? "Desmarcar serie realizada" : "Marcar serie realizada");
    }
  }

  function isExerciseDone(block) {
    const rows = Array.from(block.querySelectorAll(".set-row"));
    return rows.length > 0 && rows.every(isSetDone);
  }

  function normalizeMuscleName(value) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function regionsForMuscle(muscle) {
    const name = normalizeMuscleName(muscle);
    const regions = new Set();
    const add = (region) => regions.add(region);

    if (/pecho|pectoral/.test(name)) {
      if (/superior|clavicular/.test(name)) add("chest-upper");
      else if (/inferior/.test(name)) add("chest-lower");
      else if (/medio|esternocostal/.test(name)) add("chest-mid");
      else ["chest-upper", "chest-mid", "chest-lower"].forEach(add);
    }
    if (/hombro|deltoide|manguito rotador/.test(name)) {
      if (/anterior/.test(name)) add("deltoid-front");
      if (/lateral|participacion lateral/.test(name)) add("deltoid-side");
      if (/posterior/.test(name)) add("deltoid-rear");
      if (/manguito rotador/.test(name) || !/anterior|lateral|posterior/.test(name)) {
        ["deltoid-front", "deltoid-side", "deltoid-rear"].forEach(add);
      }
    }
    if (/biceps/.test(name)) {
      if (/cabeza larga|cabezas larga/.test(name)) add("biceps-long");
      if (/cabeza corta|cabezas larga y corta/.test(name)) add("biceps-short");
      if (!/cabeza larga|cabeza corta/.test(name)) {
        ["biceps-long", "biceps-short"].forEach(add);
      }
    }
    if (/braquial/.test(name)) add("brachialis");
    if (/braquiorradial/.test(name)) add("front-arms");
    if (/brazos/.test(name)) {
      ["biceps-long", "biceps-short", "triceps"].forEach(add);
    }
    if (/triceps|brazos/.test(name)) {
      add("triceps");
      if (/cabeza larga|porcion larga/.test(name)) add("triceps-long");
      if (/cabeza lateral|vasto lateral|porcion lateral/.test(name)) add("triceps-lateral");
      if (/cabeza medial|vasto medial|porcion medial/.test(name)) add("triceps-medial");
    }
    if (/antebrazo|muneca|agarre|pronadores|supinadores|flexores de dedos/.test(name)) add("forearms");
    if (/recto abdominal|transverso abdominal|core|estabilizadores/.test(name)) {
      add("abs");
      if (/superior/.test(name)) add("abs-upper");
      else if (/inferior/.test(name)) add("abs-lower");
      else if (/medio/.test(name)) add("abs-mid");
    }
    if (/oblicuo|cuadrado lumbar/.test(name)) add("obliques");
    if (/trapecio/.test(name)) {
      add("traps");
      if (/superior/.test(name)) add("traps-upper");
      if (/medio/.test(name)) add("traps-mid");
      if (/inferior/.test(name)) add("traps-lower");
      if (/medio|inferior/.test(name) || !/superior|medio|inferior/.test(name)) add("upper-back");
    }
    if (/elevador de la escapula/.test(name)) add("traps");
    if (/espalda media|espalda alta|romboides|toracica/.test(name)) add("upper-back");
    if (/dorsal ancho|redondo mayor/.test(name)) add("lats");
    if (/erectores|columna|multifidos/.test(name)) add("lower-back");
    if (/gluteo/.test(name)) {
      add("glutes");
      if (/mayor/.test(name)) add("glutes-max");
      if (/medio|menor/.test(name)) add("glutes-med");
    }
    if (/gluteo medio|gluteo menor|abductores|tensor de la fascia lata/.test(name)) add("outer-hips");
    if (/flexores de cadera/.test(name)) add("hip-flexors");
    if (/^cadera$/.test(name)) {
      ["hip-flexors", "outer-hips", "glutes"].forEach(add);
    }
    if (/aductores|pectineo|gracil/.test(name)) add("adductors");
    if (/cuadriceps/.test(name)) {
      add("quads");
      if (/recto femoral/.test(name)) add("quads-rectus");
      if (/vasto lateral|externo/.test(name)) add("quads-lateral");
      if (/vasto medial|interno/.test(name)) add("quads-medial");
    }
    if (/isquiosurales|biceps femoral|semitendinoso|semimembranoso/.test(name)) {
      add("hamstrings");
      if (/biceps femoral/.test(name)) add("hamstrings-lateral");
      if (/semitendinoso|semimembranoso/.test(name)) add("hamstrings-medial");
    }
    if (/gastrocnemio|soleo|gemelos|pantorrilla/.test(name)) {
      add("calves");
      if (/medial|interno/.test(name)) add("calves-medial");
      if (/lateral|externo/.test(name)) add("calves-lateral");
    }
    if (/tibial anterior|extensores del tobillo|tobillo/.test(name)) add("tibialis");
    if (/cuerpo completo/.test(name)) {
      [
        "deltoid-front", "deltoid-side", "deltoid-rear", "chest-upper", "chest-mid",
        "chest-lower", "biceps-long", "biceps-short", "brachialis", "front-arms", "triceps",
        "forearms", "abs", "obliques", "traps", "upper-back", "lats", "lower-back",
        "glutes", "outer-hips", "hip-flexors", "adductors", "quads", "hamstrings",
        "calves", "tibialis",
      ].forEach(add);
    }
    return regions;
  }

  function muscleLabelsForExercise(block, field) {
    const selectedOption = block.querySelector('select[name="exercise_id"] option:checked');
    if (!selectedOption) {
      return [];
    }
    const value = field === "primary"
      ? selectedOption.dataset.primaryMuscle || ""
      : selectedOption.dataset.secondaryMuscles || "";
    return value.split(/[\n,;]+/).map((muscle) => muscle.trim()).filter(Boolean);
  }

  function updateMuscleMap(completedBlocks) {
    if (muscleMaps.length === 0) {
      return;
    }

    const primaryRegions = new Set();
    const secondaryRegions = new Set();
    const primaryLabels = new Set();
    const secondaryLabels = new Set();

    completedBlocks.forEach((block) => {
      muscleLabelsForExercise(block, "primary").forEach((muscle) => {
        primaryLabels.add(muscle);
        regionsForMuscle(muscle).forEach((region) => primaryRegions.add(region));
      });
      muscleLabelsForExercise(block, "secondary").forEach((muscle) => {
        secondaryLabels.add(muscle);
        regionsForMuscle(muscle).forEach((region) => secondaryRegions.add(region));
      });
    });

    primaryRegions.forEach((region) => secondaryRegions.delete(region));
    muscleMaps.forEach((muscleMap) => {
      muscleMap.querySelectorAll(".muscle-region").forEach((muscleRegion) => {
        const regions = muscleRegion.dataset.muscle.split(/\s+/);
        muscleRegion.classList.toggle("is-primary", regions.some((region) => primaryRegions.has(region)));
        muscleRegion.classList.toggle("is-secondary", regions.some((region) => secondaryRegions.has(region)));
      });
    });

    if (muscleMapStatus) {
      const secondaryOnlyLabels = Array.from(secondaryLabels).filter((label) =>
        !Array.from(primaryLabels).some((primaryLabel) =>
          normalizeMuscleName(primaryLabel) === normalizeMuscleName(label),
        ),
      );
      muscleMapStatus.textContent = completedBlocks.length === 0
        ? "Marca todas las series de un ejercicio para ver los músculos trabajados."
        : `${completedBlocks.length} ${completedBlocks.length === 1 ? "ejercicio completado" : "ejercicios completados"} · Principal: ${Array.from(primaryLabels).join(", ") || "sin zona muscular identificada"} · Secundario: ${secondaryOnlyLabels.join(", ") || "ninguno"}.`;
    }
  }

  function syncCompletedExercises() {
    const blocks = Array.from(blocksContainer.querySelectorAll(".workout-exercise"));
    const completedBlocks = blocks.filter(isExerciseDone);
    updateMuscleMap(completedBlocks);
    if (exerciseProgress) {
      exerciseProgress.textContent = `${blocks.length - completedBlocks.length} de ${blocks.length}`;
    }

    blocks.forEach((block) => {
      const completed = isExerciseDone(block);
      block.classList.toggle("is-completed", completed);
      block.hidden = completed && !showCompletedExercises;
    });

    if (completedTools) {
      completedTools.hidden = completedBlocks.length === 0;
    }
    if (completedCount) {
      completedCount.textContent = completedBlocks.length === 1
        ? "1 ejercicio completado"
        : `${completedBlocks.length} ejercicios completados`;
    }
    if (showCompletedButton) {
      showCompletedButton.textContent = showCompletedExercises
        ? "Ocultar completados"
        : "Mostrar completados";
      showCompletedButton.setAttribute("aria-pressed", String(showCompletedExercises));
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
    ["weight", "reps", "rest", "notes"].forEach((field) => {
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
      syncCompletedExercises();
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
    syncCompletedExercises();
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
      saved_routine_id: formFieldValue("saved_routine_id") || routinePickerValue("routine_id"),
      routine_day_name: formFieldValue("routine_day_name"),
      routine_day_id: routinePickerValue("routine_day_id"),
      exercises: Array.from(blocksContainer.querySelectorAll(".workout-exercise")).map((block) => ({
        exercise_id: formFieldValueFrom(block, 'select[name="exercise_id"]'),
        notes: formFieldValueFrom(block, 'input[name="exercise_notes"]'),
        sets: Array.from(block.querySelectorAll(".set-row")).map((row) => ({
          weight: fieldInput(row, "weight")?.value || "",
          reps: fieldInput(row, "reps")?.value || "",
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
      if (restoredLegacyDraftKey && restoredLegacyDraftKey !== draftKey) {
        localStorage.removeItem(restoredLegacyDraftKey);
        restoredLegacyDraftKey = null;
      }
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

  function parseDraft(rawDraft) {
    try {
      return rawDraft ? JSON.parse(rawDraft) : null;
    } catch (error) {
      return null;
    }
  }

  function readDraft() {
    const currentDraft = parseDraft(localStorage.getItem(draftKey));
    if (currentDraft) {
      return currentDraft;
    }

    const legacyPrefix = `${form.dataset.workoutDraftBase}:${window.location.pathname}?`;
    const legacyDrafts = [];
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (!key || !key.startsWith(legacyPrefix)) {
        continue;
      }
      const draft = parseDraft(localStorage.getItem(key));
      if (draft) {
        legacyDrafts.push({ key, draft });
      }
    }

    legacyDrafts.sort((left, right) => String(right.draft.savedAt).localeCompare(String(left.draft.savedAt)));
    const legacyDraft = legacyDrafts[0];
    if (!legacyDraft) {
      return null;
    }
    restoredLegacyDraftKey = legacyDraft.key;
    return legacyDraft.draft;
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
    const daySelect = document.querySelector('[data-routine-picker] [name="routine_day_id"]');
    if (daySelect && draft.routine_day_id) {
      daySelect.value = draft.routine_day_id;
    }
    syncRoutinePickerFromHidden();
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
      syncCompletedExercises();
      changed = true;
    }

    if (target.closest(".remove-exercise")) {
      if (!window.confirm("Quitar este ejercicio del entrenamiento?")) {
        return;
      }
      block.remove();
      if (!blocksContainer.querySelector(".workout-exercise")) {
        addExercise();
      }
      reindexBlocks();
      syncCompletedExercises();
      changed = true;
    }

    const doneButton = target.closest("[data-set-done]");
    if (doneButton) {
      doneButton.setAttribute(
        "aria-pressed",
        doneButton.getAttribute("aria-pressed") === "true" ? "false" : "true",
      );
      syncSetDoneState(doneButton.closest(".set-row"));
      if (isExerciseDone(block)) {
        showCompletedExercises = false;
      }
      syncCompletedExercises();
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
    syncCompletedExercises();
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

  showCompletedButton?.addEventListener("click", () => {
    showCompletedExercises = !showCompletedExercises;
    syncCompletedExercises();
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

  syncCompletedExercises();

  if (!restoredDraft) {
    setDraftStatus("");
  }
});
