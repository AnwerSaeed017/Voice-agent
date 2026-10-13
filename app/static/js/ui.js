// DOM helpers, formatting and the shared overlay components (drawer, confirm, toast).
// Record data is only ever inserted as text nodes, never as HTML.

import { format } from "./format.js";

export { format };

const SVG_NS = "http://www.w3.org/2000/svg";

const ICONS = {
  overview: "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  phone: "M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z",
  phoneOff: "M10.7 13.3a16 16 0 0 0 3.4 2.6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1M6.7 17.3A19.5 19.5 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9M22 2L2 22",
  code: "M8 6l-6 6 6 6M16 6l6 6-6 6",
  refresh: "M21 12a9 9 0 1 1-2.64-6.36M21 4v5h-5",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-4.3-4.3",
  close: "M18 6L6 18M6 6l12 12",
  edit: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  trash: "M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  left: "M15 18l-6-6 6-6",
  right: "M9 18l6-6-6-6",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  monitor: "M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM8 21h8M12 17v4",
  calendar: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  alert: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  check: "M20 6L9 17l-5-5",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.5 5.1L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1z",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5zM4 19.500A2.500 2.500 0 0 0 6.500 22H20v-5",
};

/** h("div", { class: "x", onclick: fn, "aria-label": "..." }, child, "text", ...) */
export function h(tag, props, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name === "class") element.className = value;
    else if (name === "text") element.textContent = value;
    else if (name.startsWith("on")) element.addEventListener(name.slice(2), value);
    else if (name in element && typeof value !== "string") element[name] = value;
    else element.setAttribute(name, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return element;
}

/** Like replaceChildren, but skips null and false, which the DOM would print as text. */
export function fill(parent, ...children) {
  parent.replaceChildren(...children.flat().filter((child) => child !== null && child !== undefined && child !== false));
  return parent;
}

export function svg(tag, attributes) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes || {})) element.setAttribute(name, value);
  return element;
}

export function icon(name) {
  const element = svg("svg", { class: "icon", viewBox: "0 0 24 24", "aria-hidden": "true" });
  element.append(svg("path", { d: ICONS[name] }));
  return element;
}

export function debounce(callback, delay) {
  let timer;
  return (...parameters) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...parameters), delay);
  };
}

// ---------- small components ----------

export function sourceBadge(callCount) {
  return callCount > 0
    ? h("span", { class: "badge voice" }, icon("phone"), "Voice call")
    : h("span", { class: "badge" }, icon("code"), "API");
}

export function outcomeBadge(call) {
  return call.registered
    ? h("span", { class: "badge ok" }, icon("check"), "Registered")
    : h("span", { class: "badge warn" }, "No registration");
}

export function segmented(label, options, current, onChange) {
  const group = h("div", { class: "segmented", role: "group", "aria-label": label });
  for (const [value, text] of options) {
    group.append(h("button", {
      type: "button", "aria-pressed": String(value === current),
      onclick: (event) => {
        for (const button of group.children) button.setAttribute("aria-pressed", "false");
        event.currentTarget.setAttribute("aria-pressed", "true");
        onChange(value);
      },
    }, text));
  }
  return group;
}

export function searchBox(placeholder, value, onInput) {
  const input = h("input", { type: "search", placeholder, value, autocomplete: "off", "aria-label": placeholder });
  input.addEventListener("input", debounce(() => onInput(input.value.trim()), 250));
  return h("div", { class: "search" }, icon("search"), input);
}

export function state(kind, title, text, action) {
  return h("div", { class: `state ${kind === "error" ? "error" : ""}`, role: kind === "error" ? "alert" : null },
    h("div", { class: "round-icon" }, icon(kind === "error" ? "alert" : "inbox")),
    h("strong", null, title), text,
    action ? h("div", null, h("button", { class: "btn", type: "button", onclick: action.run }, action.label)) : null);
}

export function skeletonRows(columns, rows = 6) {
  const widths = ["w60", "w40", "w80"];
  return Array.from({ length: rows }, (_, row) =>
    h("tr", { "aria-hidden": "true" }, Array.from({ length: columns }, (_, column) =>
      h("td", null, h("span", { class: `skeleton ${widths[(row + column) % 3]}` })))));
}

export function pagination({ total, limit, offset, onPage, onLimit }) {
  const first = total ? offset + 1 : 0;
  const last = Math.min(offset + limit, total);
  const size = h("select", { class: "select", "aria-label": "Rows per page", onchange: (event) => onLimit(Number(event.target.value)) },
    [25, 50, 100].map((option) => h("option", { value: option, selected: option === limit }, `${option} per page`)));
  return h("div", { class: "pagination" },
    h("span", null, `${first.toLocaleString()}-${last.toLocaleString()} of ${total.toLocaleString()}`),
    h("div", { class: "push" }, size,
      h("button", { class: "btn square", type: "button", "aria-label": "Previous page", disabled: offset === 0,
                    onclick: () => onPage(Math.max(0, offset - limit)) }, icon("left")),
      h("button", { class: "btn square", type: "button", "aria-label": "Next page", disabled: last >= total,
                    onclick: () => onPage(offset + limit) }, icon("right"))));
}

export function transcriptBlock(call) {
  const turns = format.turns(call.transcript);
  if (!turns.length) return h("div", { class: "sub" }, "No transcript was stored for this call.");
  return h("div", { class: "chat" }, turns.map((turn) =>
    h("div", { class: `bubble ${turn.agent ? "agent" : "caller"}` },
      h("span", { class: "who" }, turn.agent ? "Agent" : "Caller"), turn.text)));
}

// ---------- overlays ----------

const overlay = () => document.getElementById("overlay");
let drawerState = null;

/** Opens the side panel. `build(panel)` fills it; the returned handle can re-render or close it. */
export function openDrawer({ label, onClose }) {
  closeDrawer(true);
  const previousFocus = document.activeElement;
  const panel = h("aside", { class: "drawer", role: "dialog", "aria-modal": "true", "aria-label": label });
  const backdrop = h("div", { class: "backdrop", onclick: () => closeDrawer() });
  overlay().append(backdrop, panel);
  document.getElementById("app").inert = true;
  drawerState = { panel, backdrop, previousFocus, onClose };
  return panel;
}

export function closeDrawer(silent = false) {
  if (!drawerState) return;
  const { panel, backdrop, previousFocus, onClose } = drawerState;
  drawerState = null;
  panel.remove();
  backdrop.remove();
  document.getElementById("app").inert = false;
  if (previousFocus && previousFocus.isConnected) previousFocus.focus();
  if (!silent && onClose) onClose();
}

export const drawerIsOpen = () => drawerState !== null;

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && drawerState && !document.querySelector("dialog[open]")) closeDrawer();
});

export function confirmDialog({ title, message, confirmLabel, danger }) {
  return new Promise((resolve) => {
    const dialog = h("dialog", { class: "confirm", "aria-labelledby": "confirm-title" },
      h("div", { class: "confirm-body" }, h("h2", { id: "confirm-title" }, title), h("p", null, message)),
      h("div", { class: "confirm-actions" },
        h("button", { class: "btn", type: "button", onclick: () => dialog.close("cancel") }, "Cancel"),
        h("button", { class: `btn ${danger ? "danger solid" : "primary"}`, type: "button",
                      onclick: () => dialog.close("confirm") }, confirmLabel)));
    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(dialog.returnValue === "confirm");
    });
    document.body.append(dialog);
    dialog.showModal();
  });
}

export function toast(message, kind = "success") {
  const element = h("div", { class: `toast ${kind === "error" ? "error" : ""}`, role: kind === "error" ? "alert" : null },
    icon(kind === "error" ? "alert" : "check"), message);
  document.getElementById("toasts").append(element);
  setTimeout(() => element.remove(), kind === "error" ? 6000 : 3500);
}
