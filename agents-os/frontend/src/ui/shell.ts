// ============================================================================
// Agent OS — UI: Sidebar + Topbar + Router
// ============================================================================

import { store } from "../store";
import type { PanelName } from "../types";

// -- Panel config --------------------------------------------------------------

const PANEL_DEFS: { id: PanelName; icon: string; label: string; badge?: string }[] = [
  { id: "overview", icon: "📊", label: "Dashboard" },
  { id: "canvas", icon: "🖥️", label: "Canvas", badge: "5" },
  { id: "graph", icon: "🔗", label: "Graphe" },
  { id: "chat", icon: "💬", label: "Chat Agents" },
  { id: "memory", icon: "🧠", label: "Mémoire" },
  { id: "skills", icon: "🧩", label: "Skills" },
  { id: "kanban", icon: "📋", label: "Kanban" },
  { id: "n8n", icon: "⚡", label: "n8n Orchestration" },
  { id: "admin", icon: "⚙️", label: "Admin" },
];

// -- Shell ---------------------------------------------------------------------

export function renderShell(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <aside class="aos-sidebar" id="aos-sidebar">
      <div class="aos-sidebar-logo">
        <h1>⚡<span> Agentic OS</span></h1>
        <div class="aos-ver">v3.0</div>
      </div>
      <nav class="aos-sidebar-nav" id="aos-nav"></nav>
      <div class="aos-sidebar-footer">
        <div class="aos-user-info">
          <div class="aos-avatar" id="aos-avatar">A</div>
          <span id="aos-user-name">...</span>
        </div>
        <a href="/logout">Déconnexion</a>
      </div>
    </aside>
    <div class="aos-main">
      <div class="aos-topbar">
        <div class="aos-page-title" id="aos-page-title">📊 Dashboard</div>
        <div class="aos-stats" id="aos-stats"></div>
      </div>
      <div class="aos-content" id="aos-content"></div>
    </div>
  `;

  renderNav();
  bindNavEvents();
  store.subscribe(onStateChange);
}

function renderNav(): void {
  const nav = document.getElementById("aos-nav");
  if (!nav) return;
  const state = store.getState();
  const user = state.status?.user;

  nav.innerHTML = PANEL_DEFS
    .filter(p => {
      // Status pas encore charge : afficher tous les panels (optimiste)
      if (!user) return true;
      // Panneau admin reserve aux admins
      if (p.id === "admin") return user.role === "admin";
      // Admin : tous les panels
      if (user.role === "admin") return true;
      // Permissions vides ou absentes = tous les panels par defaut
      const allowed = user.permissions?.panels ?? [];
      if (allowed.length === 0) return true;
      // Sinon : uniquement les panels autorises explicitement
      return allowed.includes(p.id);
    })
    .map(p => {
      const active = state.activePanel === p.id ? " active" : "";
      return `<button class="aos-nav-item${active}" data-panel="${p.id}">
        <span class="aos-nav-icon">${p.icon}</span>
        <span>${p.label}</span>
        ${p.badge ? `<span class="aos-nav-badge">${p.badge}</span>` : ""}
      </button>`;
    })
    .join("");
}

function bindNavEvents(): void {
  const nav = document.getElementById("aos-nav");
  if (!nav) return;
  nav.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>(".aos-nav-item");
    if (!btn) return;
    const panel = btn.dataset.panel as PanelName | undefined;
    if (panel) store.setPanel(panel);
  });
}

function onStateChange(): void {
  const state = store.getState();
  renderNav();
  updateTopbar(state);
}

function updateTopbar(state: ReturnType<typeof store.getState>): void {
  const title = document.getElementById("aos-page-title");
  if (title) {
    const def = PANEL_DEFS.find(p => p.id === state.activePanel);
    title.textContent = def ? `${def.icon} ${def.label}` : "Agentic OS";
  }
  const stats = document.getElementById("aos-stats");
  if (stats && state.status) {
    const s = state.status;
    const h = Math.floor(s.uptime_seconds / 3600);
    const m = Math.floor((s.uptime_seconds % 3600) / 60);
    stats.innerHTML = `
      <div class="aos-stat"><div class="aos-stat-val">${s.profiles.length}</div><div class="aos-stat-lbl">Agents</div></div>
      <div class="aos-stat"><div class="aos-stat-val">${s.total_calls}</div><div class="aos-stat-lbl">Requêtes</div></div>
      <div class="aos-stat"><div class="aos-stat-val">${h}h${m}</div><div class="aos-stat-lbl">Uptime</div></div>
    `;
  }
  const avatar = document.getElementById("aos-avatar");
  const name = document.getElementById("aos-user-name");
  if (avatar && name && state.status?.user) {
    avatar.textContent = state.status.user.name.charAt(0).toUpperCase();
    name.textContent = state.status.user.name;
  }
}

// -- Page title update ---------------------------------------------------------

export function setPageTitle(title: string): void {
  const el = document.getElementById("aos-page-title");
  if (el) el.textContent = title;
}
