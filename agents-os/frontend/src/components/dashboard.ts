// ============================================================================
// Agent OS — Panneau Dashboard (Overview)
// ============================================================================

import { store } from "../store";
import { renderWidgetGrid } from "../ui/widgets";
import type { PanelName, ActivityEvent, AgentProfile } from "../types";

// -- Dashboard renderer --------------------------------------------------------

export function renderDashboard(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-dashboard" id="aos-dashboard">
      <div class="aos-dash-header">
        <div class="aos-dash-summary" id="aos-dash-summary"></div>
        <div class="aos-dash-filters">
          <button class="aos-filter-btn active" data-filter="all">Tout</button>
          <button class="aos-filter-btn" data-filter="error">Erreurs</button>
          <button class="aos-filter-btn" data-filter="tool_call">Tool Calls</button>
          <button class="aos-filter-btn" data-filter="agent_action">Actions Agent</button>
        </div>
      </div>
      <div class="aos-widget-area" id="aos-widget-area"></div>
      <div class="aos-agent-grid" id="aos-agent-grid"></div>
    </div>
  `;

  bindFilters();
  store.subscribe(onDashboardUpdate);

  // Initial render
  const widgetArea = document.getElementById("aos-widget-area");
  if (widgetArea) renderWidgetGrid(widgetArea);

  const agentGrid = document.getElementById("aos-agent-grid");
  if (agentGrid) renderAgentCards(agentGrid, store.getState().profiles);

  updateSummary();
}

// -- Filters --------------------------------------------------------------------

let activeFilter = "all";

function bindFilters(): void {
  document.querySelectorAll<HTMLButtonElement>(".aos-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".aos-filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter ?? "all";
      updateFeedFilter();
    });
  });
}

function updateFeedFilter(): void {
  const feed = document.querySelector(".aos-feed-list");
  if (!feed) return;
  const events = store.getState().activityFeed;
  const iconMap: Record<string, string> = {
    info: "ℹ️", success: "✅", error: "❌", tool_call: "🔧", agent_action: "🤖",
  };
  const filtered = activeFilter === "all" ? events : events.filter(e => e.type === activeFilter);

  feed.innerHTML = filtered.length === 0
    ? `<div class="aos-feed-empty">Aucune activité</div>`
    : filtered.slice(0, 20).map(e => `
        <div class="aos-feed-item aos-feed-${e.type}">
          <span class="aos-feed-icon">${iconMap[e.type] ?? "•"}</span>
          <span class="aos-feed-msg">${escHtml(e.message)}</span>
          <span class="aos-feed-time">${new Date(e.timestamp).toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
        </div>
      `).join("");
}

// -- Agent cards ----------------------------------------------------------------

function renderAgentCards(container: HTMLElement, profiles: AgentProfile[]): void {
  if (profiles.length === 0) {
    container.innerHTML = `<div class="aos-empty-state">Aucun agent configuré</div>`;
    return;
  }
  container.innerHTML = profiles.map(p => `
    <div class="aos-agent-card" style="border-top: 3px solid ${p.color}">
      <div class="aos-agent-card-header">
        <div class="aos-agent-avatar" style="background:${p.color}22;color:${p.color}">${p.emoji}</div>
        <div>
          <div class="aos-agent-name">${escHtml(p.name)}</div>
          <div class="aos-agent-desc">${escHtml(p.description)}</div>
        </div>
        <div class="aos-agent-status">
          <span class="aos-status-dot online"><span class="aos-pulse"></span> prêt</span>
        </div>
      </div>
      <div class="aos-agent-card-body">
        <div class="aos-agent-quick-chat" id="qc-${escHtml(p.name)}">
          <input type="text" class="aos-agent-input" placeholder="Message rapide..." data-agent="${escHtml(p.name)}">
          <button class="aos-agent-send" data-agent="${escHtml(p.name)}">Envoyer</button>
        </div>
        ${p.has_memory ? `<div class="aos-agent-memory-indicator">🧠 Mémoire active</div>` : ""}
      </div>
    </div>
  `).join("");

  // Bind quick chat
  container.querySelectorAll<HTMLButtonElement>(".aos-agent-send").forEach(btn => {
    btn.addEventListener("click", () => {
      const agent = btn.dataset.agent!;
      const input = document.querySelector<HTMLInputElement>(`input[data-agent="${agent}"]`);
      if (!input?.value.trim()) return;
      const msg = input.value.trim();
      input.value = "";
      store.addActivity({
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        type: "agent_action",
        agent,
        message: `Message envoyé à ${agent}: ${msg}`,
      });
      fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: agent, message: msg }),
      })
        .then(r => r.json())
        .then(d => {
          store.addActivity({
            id: crypto.randomUUID(),
            timestamp: Date.now(),
            type: "success",
            agent,
            message: `Réponse de ${agent}`,
            details: d.response,
          });
        })
        .catch(e => {
          store.addActivity({
            id: crypto.randomUUID(),
            timestamp: Date.now(),
            type: "error",
            agent,
            message: `Erreur: ${e.message}`,
          });
        });
    });
  });

  container.querySelectorAll<HTMLInputElement>(".aos-agent-input").forEach(input => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const btn = input.parentElement?.querySelector<HTMLButtonElement>(".aos-agent-send");
        btn?.click();
      }
    });
  });
}

// -- Summary bar ----------------------------------------------------------------

function updateSummary(): void {
  const el = document.getElementById("aos-dash-summary");
  if (!el) return;
  const s = store.getState().status;
  if (!s) { el.innerHTML = ""; return; }
  const errRate = s.total_calls > 0 ? ((s.errors / s.total_calls) * 100).toFixed(1) : "0.0";
  const h = Math.floor(s.uptime_seconds / 3600);
  el.innerHTML = `
    <span class="aos-summary-chip">🟢 Online</span>
    <span class="aos-summary-chip">📊 ${s.total_calls} appels</span>
    <span class="aos-summary-chip">⚠️ ${errRate}% erreurs</span>
    <span class="aos-summary-chip">⏱️ ${h}h uptime</span>
    <span class="aos-summary-chip">🤖 ${s.profiles.length} agents</span>
  `;
}

// -- Panel lifecycle ------------------------------------------------------------

function onDashboardUpdate(): void {
  const state = store.getState();
  if (state.activePanel !== "overview") return;

  const widgetArea = document.getElementById("aos-widget-area");
  if (widgetArea) renderWidgetGrid(widgetArea);

  const agentGrid = document.getElementById("aos-agent-grid");
  if (agentGrid && state.profiles !== store.getState().profiles) {
    renderAgentCards(agentGrid, state.profiles);
  }

  updateSummary();
}

// -- Helpers --------------------------------------------------------------------

function escHtml(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
