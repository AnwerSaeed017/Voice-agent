// Shell: navigation, hash routing, theme, system status.
import { api } from "./api.js";
import { openPatient } from "./records.js";
import { closeDrawer, h, icon } from "./ui.js";
import { callsView, overviewView, patientsView } from "./views.js";

const PAGES = {
  overview: { label: "Overview", icon: "overview", title: "Overview",
              subtitle: "Registrations and calls handled by the voice agent.", view: overviewView },
  patients: { label: "Patients", icon: "users", title: "Patients",
              subtitle: "Search, review and correct patient records.", view: patientsView },
  calls: { label: "Calls", icon: "phone", title: "Calls",
           subtitle: "Every call the agent handled, with its transcript.", view: callsView },
};
const THEMES = [["system", "monitor", "System theme"], ["light", "sun", "Light theme"], ["dark", "moon", "Dark theme"]];

let current = { name: null, handle: null };

function parseHash() {
  const [path, search] = location.hash.replace(/^#\/?/, "").split("?");
  const [section, id] = path.split("/");
  return { section: section || "overview", id: id ? decodeURIComponent(id) : null, params: new URLSearchParams(search || "") };
}

// Keeps filters in the address bar (shareable, survives a reload) without re-running the router.
function setParams(values) {
  const { section, id } = parseHash();
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries(values)) if (value) params.set(name, value);
  const record = id ? `/${encodeURIComponent(id)}` : "";
  history.replaceState(null, "", `#/${section}${record}${params.size ? "?" + params : ""}`);
}

// The address of the list behind an open record, filters included.
function listAddress() {
  const { section, params } = parseHash();
  return `#/${section}${params.size ? "?" + params : ""}`;
}

function showPatient(patientId) {
  const { section, params } = parseHash();
  if (section === "patients") {
    location.hash = `#/patients/${encodeURIComponent(patientId)}${params.size ? "?" + params : ""}`;
  }
  else {
    // Opened from another page: stay there, and return to it when the panel closes.
    openPatient(patientId, { onChanged: () => current.handle && current.handle.reload(), onClose: () => {} });
  }
}

function route() {
  const { section, id, params } = parseHash();
  if (!PAGES[section]) { location.replace("#/overview"); return; }
  const page = PAGES[section];

  if (current.name !== section) {
    closeDrawer(true);
    if (current.handle) current.handle.destroy();
    document.title = `${page.title} · Patient Registration`;
    document.getElementById("page-title").textContent = page.title;
    document.getElementById("page-sub").textContent = page.subtitle;
    for (const link of document.querySelectorAll("#nav a")) {
      if (link.dataset.page === section) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    const main = document.getElementById("main");
    main.replaceChildren();
    current = { name: section, handle: page.view(main, { params, setParams, openPatient: showPatient }) };
    window.scrollTo(0, 0);
  }

  if (section === "patients" && id) {
    openPatient(id, {
      onChanged: () => current.handle.reload(),
      onClose: () => history.replaceState(null, "", listAddress()),
    });
  } else {
    closeDrawer(true);
  }
}

function applyTheme(theme) {
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
}

function storedTheme() {
  try { return localStorage.getItem("theme") || "system"; } catch (error) { return "system"; }
}

function buildShell() {
  document.getElementById("nav").append(
    h("div", { class: "nav-label" }, "Workspace"),
    ...Object.entries(PAGES).map(([name, page]) =>
      h("a", { href: `#/${name}`, "data-page": name }, icon(page.icon), page.label)));
  document.getElementById("docs-link").prepend(icon("book"));

  let theme = storedTheme();
  const themeButton = h("button", { class: "btn square", type: "button" });
  const showTheme = () => {
    const [, iconName, label] = THEMES.find(([value]) => value === theme);
    themeButton.replaceChildren(icon(iconName));
    themeButton.setAttribute("aria-label", `${label}. Activate to change.`);
    themeButton.title = label;
  };
  themeButton.addEventListener("click", () => {
    theme = THEMES[(THEMES.findIndex(([value]) => value === theme) + 1) % THEMES.length][0];
    try { localStorage.setItem("theme", theme); } catch (error) { /* private window: keep for this visit only */ }
    applyTheme(theme);
    showTheme();
  });
  showTheme();

  const refresh = h("button", { class: "btn", type: "button" }, icon("refresh"), "Refresh");
  refresh.addEventListener("click", async () => {
    refresh.classList.add("busy");
    checkHealth();
    try { await current.handle.reload(); } finally { refresh.classList.remove("busy"); }
  });
  document.getElementById("page-actions").append(themeButton, refresh);
}

async function checkHealth() {
  const status = document.getElementById("status");
  const text = document.getElementById("status-text");
  try {
    await api.health();
    status.className = "status ok";
    text.textContent = "All systems online";
  } catch (error) {
    status.className = "status down";
    text.textContent = "Service unavailable";
  }
}

applyTheme(storedTheme());
buildShell();
window.addEventListener("hashchange", route);
route();
checkHealth();
setInterval(() => { if (!document.hidden) checkHealth(); }, 30000);
