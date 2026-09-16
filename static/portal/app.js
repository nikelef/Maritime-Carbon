"use strict";
const windMode = document.querySelector('[name="wind_mode"]');
if (windMode) {
  const updateWind = () => document.querySelectorAll('.consumption-table').forEach(table => {
    const hasErrors = table.querySelector('[data-wind-cell] .errorlist');
    table.classList.toggle('wind-columns-hidden', windMode.value === 'none' && !hasErrors);
  });
  windMode.addEventListener('change', updateWind);
  updateWind();
}
document.querySelectorAll("[data-sea-fuel-editor]").forEach(editor => {
  const rows = editor.querySelector("[data-sea-fuel-rows]");
  const template = editor.querySelector("[data-sea-fuel-template]");
  const prefix = editor.dataset.formsetPrefix || "sea_fuels";
  const total = editor.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);
  const rowLimit = Number(editor.dataset.rowLimit || 20);
  const absoluteLimit = Number(editor.dataset.absoluteLimit || 40);
  const add = editor.querySelector("[data-add-sea-fuel]");
  const status = editor.querySelector("[data-sea-fuel-status]");
  const activeRows = () => [...rows.querySelectorAll("[data-sea-fuel-row]")].filter(row => !row.hidden);
  const refresh = () => {
    const count = activeRows().length;
    add.disabled = count >= rowLimit || Number(total.value) >= absoluteLimit;
    status.textContent = prefix === "consumption"
      ? `${count} consumption row${count === 1 ? "" : "s"}. Group sea and berth rows under the same voyage number.`
      : `${count} sea fuel${count === 1 ? "" : "s"} entered. Up to 20 fuels per vessel.`;
  };
  const wire = row => {
    const remove = row.querySelector('input[name$="-DELETE"]');
    const leg = row.querySelector('select[name$="-leg"]');
    const ops = row.querySelector('input[name$="-ops_share"]');
    const update = () => {
      row.hidden = remove.checked;
      row.querySelectorAll("input, select").forEach(input => { if (input !== remove) input.disabled = remove.checked; });
      if (leg && ops) {
        ops.disabled = remove.checked || leg.value !== "eu_berth_t";
        ops.placeholder = leg.value === "eu_berth_t" ? "Default" : "N/A";
      }
      row.querySelectorAll('[data-wind-cell] input').forEach(input => {
        const sea = ["intra_t", "extra_t", "outside_t"].includes(leg?.value);
        input.disabled = remove.checked || !sea;
        input.placeholder = sea ? "Review for wind" : "N/A";
      });
      refresh();
    };
    remove.addEventListener("change", () => { update(); if (remove.checked) add.focus(); });
    if (leg) leg.addEventListener("change", update);
    update();
  };
  rows.querySelectorAll("[data-sea-fuel-row]").forEach(wire);
  add.addEventListener("click", event => {
    event.preventDefault();
    if (add.disabled) return;
    const index = Number(total.value);
    const markup = template.innerHTML.replaceAll("__prefix__", String(index));
    rows.insertAdjacentHTML("beforeend", markup);
    total.value = index + 1;
    const row = rows.lastElementChild;
    wire(row);
    row.querySelector("select").focus();
    refresh();
  });
  refresh();
});
document.querySelectorAll("form[data-confirm]").forEach(form => form.addEventListener("submit", event => {
  if (!window.confirm(form.dataset.confirm)) event.preventDefault();
}));
document.querySelectorAll("form").forEach(form => form.addEventListener("submit", event => {
  if (event.defaultPrevented) return;
  if (event.submitter?.matches("[data-add-sea-fuel]")) return;
  const button = form.querySelector("button[data-busy]");
  if (button) { button.textContent = button.dataset.busy; button.disabled = true; form.setAttribute("aria-busy", "true"); }
}));
document.querySelectorAll("[data-print]").forEach(button => button.addEventListener("click", () => window.print()));
const menu = document.querySelector("[data-menu]");
const navigation = document.querySelector("#navigation");
if (menu && navigation) {
  const close = () => { navigation.classList.remove("is-open"); menu.setAttribute("aria-expanded", "false"); };
  menu.addEventListener("click", () => { const expanded = navigation.classList.toggle("is-open"); menu.setAttribute("aria-expanded", String(expanded)); });
  document.addEventListener("click", event => { if (!navigation.contains(event.target) && !menu.contains(event.target)) close(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape") { close(); menu.focus(); } });
}
