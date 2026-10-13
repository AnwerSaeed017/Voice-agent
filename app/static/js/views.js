// The three pages. Each factory builds its DOM into `main` and returns { reload, destroy }.
import { api } from "./api.js";
import { registrationsChart } from "./chart.js";
import { openCall } from "./records.js";
import {
  drawerIsOpen, fill, format, h, icon, outcomeBadge, pagination, searchBox, segmented, skeletonRows, sourceBadge, state, toast,
} from "./ui.js";

function clickableRow(row, label, open) {
  row.tabIndex = 0;
  row.setAttribute("aria-label", label);
  row.addEventListener("click", open);
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
  });
  return row;
}

function personCell(patient, callCount) {
  return h("div", { class: "person" },
    h("div", { class: `avatar ${callCount > 0 ? "voice" : ""}` }, format.initials(patient)),
    h("div", null, h("div", { class: "strong" }, format.fullName(patient)),
      h("div", { class: "sub" }, patient.email || "No email on file")));
}

// ---------------------------------------------------------------- Overview

export function overviewView(main, context) {
  let days = 14;
  let version = 0;

  const tile = (name, label, tone) => {
    const value = h("div", { class: "tile-value" }, h("span", { class: "skeleton tall" }));
    const note = h("div", { class: "tile-note" }, " ");
    const badge = h("div", { class: `tile-icon ${tone || ""}` }, icon(name));
    return { value, note, badge, node: h("div", { class: "card tile" }, badge,
      h("div", { class: "tile-body" }, h("div", { class: "tile-label" }, label), value, note)) };
  };
  const tiles = {
    total: tile("users", "Total patients"),
    voice: tile("phone", "Registered by voice", "teal"),
    week: tile("calendar", "New in the last 7 days"),
    calls: tile("phone", "Calls handled", "teal"),
  };
  const chartSub = h("div", { class: "sub" }, " ");
  const chartBody = h("div", { class: "card-body" });
  const meters = h("div", { class: "card-body" });
  const recentPatients = h("div", { class: "list" });
  const recentCalls = h("div", { class: "list" });
  const alert = h("div");

  main.replaceChildren(h("div", { class: "stack" },
    alert,
    h("section", { class: "tiles", "aria-label": "Summary" }, Object.values(tiles).map((entry) => entry.node)),
    h("section", { class: "split" },
      h("div", { class: "card" },
        h("div", { class: "card-head" }, h("h2", null, "Registrations per day"),
          h("div", { class: "push" }, segmented("Chart range", [[7, "7 days"], [14, "14 days"], [30, "30 days"], [90, "90 days"]],
            days, (value) => { days = value; load(); })),
          chartSub),
        chartBody),
      h("div", { class: "card" },
        h("div", { class: "card-head" }, h("h2", null, "Record completeness"),
          h("div", { class: "sub" }, "Optional details patients chose to give")),
        meters)),
    h("section", { class: "halves" },
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Latest registrations")),
        recentPatients,
        h("div", { class: "card-foot" }, h("a", { href: "#/patients" }, "View all patients"))),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h2", null, "Latest calls")),
        recentCalls,
        h("div", { class: "card-foot" }, h("a", { href: "#/calls" }, "View all calls"))))));

  const meter = (label, count, total) => h("div", { class: "meter" },
    h("div", { class: "meter-head" }, h("span", null, label),
      h("span", null, `${count.toLocaleString()} of ${total.toLocaleString()} · ${format.percent(count, total)}`)),
    h("div", { class: "meter-track" }, (() => {
      const fill = h("div", { class: "meter-fill" });
      fill.style.width = total ? `${(count / total) * 100}%` : "0";
      return fill;
    })()));

  async function load() {
    const current = ++version;
    try {
      const [summary, patients, calls] = await Promise.all([
        api.summary(days), api.patients({ limit: 5 }), api.calls({ limit: 5 }),
      ]);
      if (current !== version) return;
      alert.replaceChildren();
      const { patients: counts, calls: callCounts } = summary;

      tiles.total.value.textContent = counts.total.toLocaleString();
      tiles.total.note.textContent = `${counts.voice.toLocaleString()} by voice, ${counts.api.toLocaleString()} by API`;
      tiles.voice.value.textContent = format.percent(counts.voice, counts.total);
      tiles.voice.note.textContent = `${format.count(counts.voice, "patient")} registered on a call`;
      tiles.week.value.textContent = counts.new_last_7_days.toLocaleString();
      tiles.week.note.textContent = summary.latest_registration_at
        ? `Latest ${format.ago(summary.latest_registration_at).toLowerCase()}` : "No recent registrations";
      tiles.calls.value.textContent = callCounts.total.toLocaleString();
      tiles.calls.note.textContent = callCounts.total
        ? `${callCounts.not_registered.toLocaleString()} ended without a registration` : "No calls yet";
      tiles.calls.badge.className = `tile-icon ${callCounts.not_registered ? "amber" : "teal"}`;

      const inRange = summary.registrations.reduce((sum, day) => sum + day.count, 0);
      chartSub.textContent = `${format.count(inRange, "registration")} in the last ${days} days`;
      chartBody.replaceChildren(registrationsChart(summary.registrations));
      meters.replaceChildren(
        meter("Email address", counts.with_email, counts.total),
        meter("Insurance", counts.with_insurance, counts.total),
        meter("Emergency contact", counts.with_emergency_contact, counts.total),
        meter("Apartment or unit", counts.with_unit, counts.total));

      recentPatients.replaceChildren(...(patients.items.length ? patients.items.map((patient) =>
        h("button", { class: "list-row", type: "button", onclick: () => context.openPatient(patient.patient_id) },
          h("div", { class: `avatar ${patient.call_count ? "voice" : ""}` }, format.initials(patient)),
          h("div", { class: "grow" }, h("div", { class: "strong" }, format.fullName(patient)),
            h("div", { class: "sub" }, `${patient.city}, ${patient.state} · ${format.ago(patient.created_at)}`)),
          sourceBadge(patient.call_count)))
        : [state("empty", "No patients yet", "Registrations appear here as soon as a call is completed.")]));
      recentCalls.replaceChildren(...(calls.items.length ? calls.items.map((call) =>
        h("button", { class: "list-row", type: "button",
                      onclick: () => openCall(call, { onOpenPatient: context.openPatient }) },
          h("div", { class: `round-icon ${call.registered ? "" : "warn"}` }, icon(call.registered ? "phone" : "phoneOff")),
          h("div", { class: "grow" }, h("div", { class: "strong" }, call.patient_name || "Unregistered caller"),
            h("div", { class: "sub" }, `${format.endReason(call.ended_reason)} · ${format.ago(call.created_at)}`)),
          outcomeBadge(call)))
        : [state("empty", "No calls yet", "Calls appear here when the agent finishes them.")]));
    } catch (error) {
      if (current !== version) return;
      alert.replaceChildren(h("div", { class: "card" },
        state("error", "Could not load the overview", error.message, { label: "Try again", run: load })));
    }
  }

  // Quiet refresh so a registration made on a call shows up without a reload.
  const timer = setInterval(() => { if (!document.hidden && !drawerIsOpen()) load(); }, 30000);
  load();
  return { reload: load, destroy: () => clearInterval(timer) };
}

// ---------------------------------------------------------------- Patients

const PATIENT_COLUMNS = 7;

export function patientsView(main, context) {
  const query = { q: context.params.get("q") || "", source: context.params.get("source") || "all",
                  sort: context.params.get("sort") || "newest", limit: 25, offset: 0 };
  let version = 0;
  let total = 0;

  const body = h("tbody");
  const below = h("div");
  const sortHeader = (label, ascending, descending) => {
    const arrow = h("span", { class: "arrow" }, "▲");
    const header = h("th", { scope: "col" }, h("button", { type: "button", onclick: () => {
      query.sort = query.sort === descending ? ascending : descending;
      query.offset = 0;
      load();
    } }, label, " ", arrow));
    header.sync = () => {
      const active = query.sort === ascending || query.sort === descending;
      if (active) header.setAttribute("aria-sort", query.sort === descending ? "descending" : "ascending");
      else header.removeAttribute("aria-sort");
      arrow.textContent = active && query.sort === descending ? "▼" : "▲";
    };
    return header;
  };
  const nameHeader = sortHeader("Patient", "name", "name_desc");
  const registeredHeader = sortHeader("Registered", "oldest", "newest");
  const exportButton = h("button", { class: "btn push", type: "button", onclick: exportCsv }, icon("download"), "Export CSV");

  main.replaceChildren(h("div", { class: "card" },
    h("div", { class: "toolbar" },
      searchBox("Search name, phone, email, city or insurer", query.q, (value) => { query.q = value; query.offset = 0; load(); }),
      segmented("Filter by how the patient registered", [["all", "All"], ["voice", "Voice"], ["api", "API"]], query.source,
        (value) => { query.source = value; query.offset = 0; load(); }),
      exportButton),
    h("div", { class: "table-wrap" }, h("table", { class: "data" },
      h("thead", null, h("tr", null, nameHeader,
        ...["Date of birth", "Phone", "Location", "Insurance", "Source"].map((label) => h("th", { scope: "col" }, label)),
        registeredHeader)),
      body)),
    below));

  function row(patient) {
    return clickableRow(h("tr", null,
      h("td", null, personCell(patient, patient.call_count)),
      h("td", null, h("div", null, patient.date_of_birth),
        h("div", { class: "sub" }, `${format.age(patient.date_of_birth)} · ${patient.sex}`)),
      h("td", null, format.phone(patient.phone_number)),
      h("td", null, h("div", null, `${patient.city}, ${patient.state}`), h("div", { class: "sub" }, patient.zip_code)),
      h("td", null, patient.insurance_provider || h("span", { class: "sub" }, "Not provided")),
      h("td", null, sourceBadge(patient.call_count)),
      h("td", null, h("div", null, format.date(patient.created_at)), h("div", { class: "sub" }, format.ago(patient.created_at)))),
    `Open record for ${format.fullName(patient)}`, () => context.openPatient(patient.patient_id));
  }

  async function load() {
    const current = ++version;
    nameHeader.sync();
    registeredHeader.sync();
    context.setParams({ q: query.q, source: query.source === "all" ? "" : query.source, sort: query.sort === "newest" ? "" : query.sort });
    if (!body.children.length) body.replaceChildren(...skeletonRows(PATIENT_COLUMNS));
    try {
      const page = await api.patients(query);
      if (current !== version) return;
      // A page can empty out after a removal: step back to the last page that has rows.
      if (!page.items.length && page.total && query.offset) {
        query.offset = Math.floor((page.total - 1) / query.limit) * query.limit;
        return load();
      }
      total = page.total;
      const filtered = query.q || query.source !== "all";
      body.replaceChildren(...page.items.map(row));
      exportButton.disabled = !total;
      fill(below,
        page.items.length ? null : state("empty",
          filtered ? "No patients match" : "No patients registered yet",
          filtered ? "Try a different search, or switch the filter back to All."
                   : "Patients appear here as soon as a registration call is completed."),
        pagination({ total, limit: query.limit, offset: query.offset,
                     onPage: (offset) => { query.offset = offset; load(); },
                     onLimit: (limit) => { query.limit = limit; query.offset = 0; load(); } }));
    } catch (error) {
      if (current !== version) return;
      body.replaceChildren();
      below.replaceChildren(state("error", "Could not load patients", error.message, { label: "Try again", run: load }));
    }
  }

  async function exportCsv() {
    const columns = ["patient_id", "first_name", "last_name", "date_of_birth", "sex", "phone_number", "email",
      "address_line_1", "address_line_2", "city", "state", "zip_code", "insurance_provider", "insurance_member_id",
      "preferred_language", "emergency_contact_name", "emergency_contact_phone", "call_count", "created_at", "updated_at"];
    // Quote every cell, and neutralise values a spreadsheet would run as a formula.
    const cell = (value) => {
      let text = value === null || value === undefined ? "" : String(value);
      if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
      return `"${text.replace(/"/g, '""')}"`;
    };
    exportButton.disabled = true;
    exportButton.classList.add("busy");
    try {
      const rows = [];
      const cap = 5000;
      for (let offset = 0; offset < Math.min(total, cap); offset += 100) {
        const page = await api.patients({ ...query, limit: 100, offset });
        rows.push(...page.items);
        if (!page.items.length) break;
      }
      const lines = [columns.join(","), ...rows.map((patient) => columns.map((column) => cell(patient[column])).join(","))];
      const link = h("a", { href: URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv" })),
                            download: `patients-${new Date().toISOString().slice(0, 10)}.csv` });
      link.click();
      URL.revokeObjectURL(link.href);
      toast(total > cap ? `Exported the first ${cap.toLocaleString()} patients` : `Exported ${format.count(rows.length, "patient")}`);
    } catch (error) {
      toast(`Export failed. ${error.message}`, "error");
    } finally {
      exportButton.disabled = false;
      exportButton.classList.remove("busy");
    }
  }

  load();
  return { reload: load, destroy: () => {} };
}

// ---------------------------------------------------------------- Calls

const CALL_COLUMNS = 6;

export function callsView(main, context) {
  const query = { q: context.params.get("q") || "", outcome: context.params.get("outcome") || "all", limit: 25, offset: 0 };
  let version = 0;
  const body = h("tbody");
  const below = h("div");

  main.replaceChildren(h("div", { class: "card" },
    h("div", { class: "toolbar" },
      searchBox("Search patient, caller number or transcript", query.q, (value) => { query.q = value; query.offset = 0; load(); }),
      segmented("Filter by outcome", [["all", "All"], ["registered", "Registered"], ["not_registered", "No registration"]],
        query.outcome, (value) => { query.outcome = value; query.offset = 0; load(); })),
    h("div", { class: "table-wrap" }, h("table", { class: "data" },
      h("thead", null, h("tr", null,
        ...["Date and time", "Outcome", "Patient", "Caller number", "How it ended", "Conversation"]
          .map((label) => h("th", { scope: "col" }, label)))),
      body)),
    below));

  function row(call) {
    const turns = format.turns(call.transcript).length;
    return clickableRow(h("tr", null,
      h("td", null, h("div", { class: "strong" }, format.dateTime(call.created_at)), h("div", { class: "sub" }, format.ago(call.created_at))),
      h("td", null, outcomeBadge(call)),
      h("td", null, call.patient_name || h("span", { class: "sub" }, call.patient_id ? "Record removed" : "None saved")),
      h("td", null, call.caller_number || h("span", { class: "sub" }, "Web call")),
      h("td", null, format.endReason(call.ended_reason)),
      h("td", null, turns ? format.count(turns, "turn") : h("span", { class: "sub" }, "No transcript"))),
    `Open call from ${format.dateTime(call.created_at)}`, () => openCall(call, { onOpenPatient: context.openPatient }));
  }

  async function load() {
    const current = ++version;
    context.setParams({ q: query.q, outcome: query.outcome === "all" ? "" : query.outcome });
    if (!body.children.length) body.replaceChildren(...skeletonRows(CALL_COLUMNS));
    try {
      const page = await api.calls(query);
      if (current !== version) return;
      const filtered = query.q || query.outcome !== "all";
      body.replaceChildren(...page.items.map(row));
      fill(below,
        page.items.length ? null : state("empty",
          filtered ? "No calls match" : "No calls yet",
          filtered ? "Try a different search, or switch the filter back to All."
                   : "Every call the agent handles is listed here, including ones that end early."),
        pagination({ total: page.total, limit: query.limit, offset: query.offset,
                     onPage: (offset) => { query.offset = offset; load(); },
                     onLimit: (limit) => { query.limit = limit; query.offset = 0; load(); } }));
    } catch (error) {
      if (current !== version) return;
      body.replaceChildren();
      below.replaceChildren(state("error", "Could not load calls", error.message, { label: "Try again", run: load }));
    }
  }

  load();
  return { reload: load, destroy: () => {} };
}
