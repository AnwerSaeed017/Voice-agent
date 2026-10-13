// The side panels: a patient record (view, edit, remove) and a single call.
import { api } from "./api.js";
import {
  closeDrawer, confirmDialog, format, h, icon, openDrawer, outcomeBadge, sourceBadge, state, toast, transcriptBlock,
} from "./ui.js";

const SEX_OPTIONS = ["Male", "Female", "Other", "Decline to Answer"];
const FORM = [
  ["Identity", [
    { key: "first_name", label: "First name", required: true },
    { key: "last_name", label: "Last name", required: true },
    { key: "date_of_birth", label: "Date of birth", required: true, hint: "MM/DD/YYYY" },
    { key: "sex", label: "Sex", required: true, options: SEX_OPTIONS },
    { key: "preferred_language", label: "Preferred language", hint: "Defaults to English" },
  ]],
  ["Contact", [
    { key: "phone_number", label: "Phone number", required: true, hint: "10-digit U.S. number", mode: "tel" },
    { key: "email", label: "Email", mode: "email" },
    { key: "address_line_1", label: "Street address", required: true, full: true },
    { key: "address_line_2", label: "Apartment or unit" },
    { key: "city", label: "City", required: true },
    { key: "state", label: "State", required: true, hint: "2-letter abbreviation" },
    { key: "zip_code", label: "ZIP code", required: true, mode: "numeric" },
  ]],
  ["Insurance", [
    { key: "insurance_provider", label: "Insurance provider" },
    { key: "insurance_member_id", label: "Member ID" },
  ]],
  ["Emergency contact", [
    { key: "emergency_contact_name", label: "Name" },
    { key: "emergency_contact_phone", label: "Phone number", mode: "tel" },
  ]],
];

function section(title, pairs, extra) {
  const list = h("dl", { class: "pairs" });
  for (const [label, value] of pairs || []) {
    list.append(h("dt", null, label), h("dd", { class: value ? null : "sub" }, value || "Not provided"));
  }
  return h("div", { class: "section" }, h("h3", null, title), pairs ? list : null, extra);
}

function callCard(call) {
  const turns = format.turns(call.transcript).length;
  return h("div", { class: "call-card" },
    h("div", { class: "call-head" }, icon("phone"), format.dateTime(call.created_at),
      h("span", { class: "badge neutral" }, format.endReason(call.ended_reason))),
    h("div", { class: "call-body" },
      call.summary ? h("p", null, call.summary) : null,
      turns
        ? h("details", null, h("summary", null, `View transcript (${turns} turns)`), transcriptBlock(call))
        : h("div", { class: "sub" }, "No transcript was stored for this call.")));
}

/** Opens a patient record. `onChanged` runs after a save or removal; `onClose` when the panel closes. */
export function openPatient(patientId, { onChanged, onClose }) {
  const panel = openDrawer({ label: "Patient record", onClose });
  let patient = null;
  let calls = [];

  const closeButton = () => h("button", { class: "btn square ghost", type: "button", "aria-label": "Close", onclick: () => closeDrawer() }, icon("close"));
  const head = () => h("div", { class: "drawer-head" },
    h("div", { class: `avatar lg ${calls.length ? "voice" : ""}` }, format.initials(patient)),
    h("div", { class: "grow" },
      h("div", { class: "drawer-title" }, format.fullName(patient)),
      h("div", { class: "drawer-meta" },
        h("span", { class: "sub" }, `${format.age(patient.date_of_birth)} · ${patient.sex}`), sourceBadge(calls.length))),
    closeButton());

  const showMessage = (node) => {
    panel.replaceChildren(
      h("div", { class: "drawer-head" }, h("div", { class: "grow drawer-title" }, "Patient record"), closeButton()),
      h("div", { class: "drawer-body" }, node));
    panel.querySelector("button").focus();
  };

  const load = async () => {
    showMessage(h("div", { class: "state" }, "Loading record..."));
    try {
      [patient, calls] = await Promise.all([api.patient(patientId), api.patientCalls(patientId)]);
      view();
    } catch (error) {
      showMessage(error.status === 404 || error.status === 400
        ? state("empty", "Record not found", "This patient record does not exist or has been removed.")
        : state("error", "Could not load this record", error.message, { label: "Try again", run: load }));
    }
  };

  const view = () => {
    const address = [patient.address_line_1, patient.address_line_2,
                     `${patient.city}, ${patient.state} ${patient.zip_code}`].filter(Boolean).join("\n");
    const copy = h("button", { class: "link-button", type: "button", onclick: async () => {
      try { await navigator.clipboard.writeText(patient.patient_id); toast("Patient ID copied"); }
      catch (error) { toast("Could not copy the ID", "error"); }
    } }, "Copy");
    panel.replaceChildren(
      head(),
      h("div", { class: "drawer-actions" },
        h("button", { class: "btn", type: "button", onclick: edit }, icon("edit"), "Edit details"),
        h("button", { class: "btn danger push", type: "button", onclick: remove }, icon("trash"), "Remove")),
      h("div", { class: "drawer-body" },
        section("Demographics", [
          ["Date of birth", patient.date_of_birth], ["Sex", patient.sex], ["Preferred language", patient.preferred_language]]),
        section("Contact", [
          ["Phone", format.phone(patient.phone_number)], ["Email", patient.email], ["Address", address]]),
        section("Insurance", [["Provider", patient.insurance_provider], ["Member ID", patient.insurance_member_id]]),
        section("Emergency contact", [
          ["Name", patient.emergency_contact_name], ["Phone", format.phone(patient.emergency_contact_phone)]]),
        section("Record", [
          ["Patient ID", h("span", null, h("span", { class: "mono" }, patient.patient_id), " ", copy)],
          ["Registered", format.dateTime(patient.created_at)],
          ["Last updated", format.dateTime(patient.updated_at)]]),
        section(`Call history (${calls.length})`, null, calls.length
          ? h("div", null, calls.map(callCard))
          : h("div", { class: "sub" }, "No calls are linked to this record. It was created through the API or as demo data."))));
    panel.querySelector(".drawer-head button").focus();
  };

  const edit = () => {
    const inputs = {};
    const banner = h("div", { class: "banner", role: "alert", hidden: true });
    const groups = FORM.map(([title, fields]) => h("div", { class: "section" }, h("h3", null, title),
      h("div", { class: "form-grid" }, fields.map((field) => {
        const id = `field-${field.key}`;
        const value = patient[field.key] || "";
        const control = field.options
          ? h("select", { id }, field.options.map((option) => h("option", { value: option, selected: option === value }, option)))
          : h("input", { id, value, inputmode: field.mode, autocomplete: "off", "aria-describedby": `${id}-note` });
        inputs[field.key] = control;
        return h("div", { class: `field ${field.full ? "full" : ""}`, "data-field": field.key },
          h("label", { for: id }, field.label, field.required ? h("span", { class: "req", "aria-hidden": "true" }, " *") : null),
          control,
          h("div", { id: `${id}-note`, class: "hint" }, field.hint || ""));
      }))));

    const save = async (event) => {
      event.preventDefault();
      const changes = {};
      for (const [key, control] of Object.entries(inputs)) {
        const value = control.value.trim();
        if (value !== (patient[key] || "")) changes[key] = value === "" ? null : value;
      }
      if (!Object.keys(changes).length) { toast("No changes to save"); view(); return; }
      for (const wrapper of form.querySelectorAll(".field")) {
        wrapper.classList.remove("invalid");
        const field = FORM.flatMap(([, fields]) => fields).find((entry) => entry.key === wrapper.dataset.field);
        const note = wrapper.querySelector(".hint, .error");
        note.className = "hint";
        note.textContent = field.hint || "";
      }
      banner.hidden = true;
      saveButton.disabled = true;
      try {
        patient = await api.updatePatient(patient.patient_id, changes);
        toast("Patient record updated");
        view();
        if (onChanged) onChanged();
      } catch (error) {
        saveButton.disabled = false;
        let first = null;
        for (const detail of error.details || []) {
          const wrapper = form.querySelector(`[data-field="${CSS.escape(detail.field)}"]`);
          if (!wrapper) continue;
          wrapper.classList.add("invalid");
          const note = wrapper.querySelector(".hint, .error");
          note.className = "error";
          note.textContent = detail.message;
          first = first || inputs[detail.field];
        }
        banner.textContent = first ? "Some details need attention. Nothing was saved." : error.message;
        banner.hidden = false;
        if (first) first.focus();
      }
    };

    const saveButton = h("button", { class: "btn primary", type: "submit" }, "Save changes");
    const form = h("form", { class: "drawer-body", novalidate: true, onsubmit: save }, banner, groups);
    const foot = h("div", { class: "drawer-foot" },
      h("button", { class: "btn", type: "button", onclick: view }, "Cancel"), saveButton);
    saveButton.setAttribute("form", "patient-form");
    form.id = "patient-form";
    panel.replaceChildren(head(), form, foot);
    inputs.first_name.focus();
  };

  const remove = async () => {
    const confirmed = await confirmDialog({
      title: `Remove ${format.fullName(patient)}?`,
      message: "The record will be hidden from the console and the API. It is kept in the database and is not erased.",
      confirmLabel: "Remove record",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.deletePatient(patient.patient_id);
      toast("Patient record removed");
      closeDrawer();
      if (onChanged) onChanged();
    } catch (error) {
      toast(error.message, "error");
    }
  };

  load();
}

/** Opens one call. `call` is a row from the calls list. */
export function openCall(call, { onOpenPatient }) {
  const panel = openDrawer({ label: "Call details" });
  let patientLine = "No patient record was saved on this call";
  if (call.patient_id && call.patient_name) {
    patientLine = h("button", { class: "link-button", type: "button", onclick: () => onOpenPatient(call.patient_id) },
      `${call.patient_name} →`);
  } else if (call.patient_id) {
    patientLine = "The patient record has since been removed";
  }
  panel.replaceChildren(
    h("div", { class: "drawer-head" },
      h("div", { class: `round-icon ${call.registered ? "" : "warn"}` }, icon(call.registered ? "phone" : "phoneOff")),
      h("div", { class: "grow" },
        h("div", { class: "drawer-title" }, format.dateTime(call.created_at)),
        h("div", { class: "drawer-meta" }, outcomeBadge(call), h("span", { class: "sub" }, format.ago(call.created_at)))),
      h("button", { class: "btn square ghost", type: "button", "aria-label": "Close", onclick: () => closeDrawer() }, icon("close"))),
    h("div", { class: "drawer-body" },
      section("Details", [
        ["Patient", patientLine],
        ["Caller number", call.caller_number || "Not available (web call)"],
        ["How it ended", format.endReason(call.ended_reason)],
        ["Call ID", h("span", { class: "mono" }, call.call_id)],
      ]),
      call.summary ? section("Summary", null, h("p", null, call.summary)) : null,
      section(`Transcript (${format.turns(call.transcript).length} turns)`, null, transcriptBlock(call))));
  panel.querySelector(".drawer-head button").focus();
}
