document.addEventListener("DOMContentLoaded", () => {
  const fieldset = document.querySelector(".checkbox-fieldset");
  if (!fieldset) {
    return;
  }

  const checkboxes = fieldset.querySelectorAll('input[type="checkbox"][name="equipment_items"]');

  function syncGroups() {
    fieldset.querySelectorAll("[data-equipment-group]").forEach((groupCheckbox) => {
      const group = groupCheckbox.dataset.equipmentGroup;
      const children = fieldset.querySelectorAll(`[data-equipment-child="${group}"]`);
      const checked = fieldset.querySelectorAll(`[data-equipment-child="${group}"]:checked`);
      groupCheckbox.checked = children.length > 0 && checked.length === children.length;
      groupCheckbox.indeterminate = checked.length > 0 && checked.length < children.length;
    });
  }

  fieldset.querySelectorAll("[data-equipment-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const shouldCheck = button.dataset.equipmentAction === "select-all";
      checkboxes.forEach((checkbox) => {
        checkbox.checked = shouldCheck;
      });
      syncGroups();
    });
  });

  fieldset.querySelectorAll("[data-equipment-group]").forEach((groupCheckbox) => {
    groupCheckbox.addEventListener("change", () => {
      fieldset.querySelectorAll(`[data-equipment-child="${groupCheckbox.dataset.equipmentGroup}"]`).forEach((checkbox) => {
        checkbox.checked = groupCheckbox.checked;
      });
      syncGroups();
    });
  });

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", syncGroups);
  });

  syncGroups();
});
