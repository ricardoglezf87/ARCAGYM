document.addEventListener("DOMContentLoaded", () => {
  const fieldset = document.querySelector(".checkbox-fieldset");
  if (!fieldset) {
    return;
  }

  const checkboxes = fieldset.querySelectorAll('input[type="checkbox"][name="equipment_items"]');
  fieldset.querySelectorAll("[data-equipment-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const shouldCheck = button.dataset.equipmentAction === "select-all";
      checkboxes.forEach((checkbox) => {
        checkbox.checked = shouldCheck;
      });
    });
  });
});
