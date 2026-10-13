// ============================================================================
// Agent OS — Panneau n8n (orchestration des agents)
// ============================================================================

import { store } from "../store";
import type { N8nWorkflow, N8nExecution } from "../types";

interface N8nState {
  online: boolean;
  workflows: N8nWorkflow[];
  executions: N8nExecution[];
  selectedWorkflow: string | null;
  orchestrating: boolean;
  results: { agent: string; response: string }[];
}

const state: N8nState = {
  online: false,
  workflows: [],
  executions: [],
  selectedWorkflow: null,
  orchestrating: false,
  results: [],
};

export function renderN8n(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-n8n" id="aos-n8n">
      <div class="aos-n8n-header">
        <div class="aos-n8n-title">⚡ Orchestration n8n</div>
        <div class="aos-n8n-status" id="aos-n8n-status">
          <span class="aos-status-dot"><span class="aos-pulse"></span> Vérification...</span>
        </div>
        <a class="aos-btn aos-btn-sm" href="https://n8n.apps.okdsnoapps.vmapps.home" target="_blank">Ouvrir n8n ↗</a>
      </div>

      <div class="aos-n8n-layout">
        <!-- Colonne gauche : workflows -->
        <div class="aos-n8n-col">
          <div class="aos-card aos-mb">
            <div class="aos-card-header">
              <span class="aos-card-title">Workflows</span>
              <button class="aos-btn aos-btn-sm" id="n8n-refresh">🔄 Rafraîchir</button>
            </div>
            <div class="aos-card-body" id="aos-n8n-workflows">
              <div class="aos-empty-state">Chargement...</div>
            </div>
          </div>

          <div class="aos-card">
            <div class="aos-card-header">
              <span class="aos-card-title">Exécutions récentes</span>
            </div>
            <div class="aos-card-body" id="aos-n8n-executions">
              <div class="aos-empty-state">Sélectionnez un workflow</div>
            </div>
          </div>
        </div>

        <!-- Colonne droite : orchestration -->
        <div class="aos-n8n-col">
          <div class="aos-card aos-mb">
            <div class="aos-card-header">
              <span class="aos-card-title">🔗 Orchestrer une chaîne d'agents</span>
            </div>
            <div class="aos-card-body">
              <div class="aos-form-group aos-mb">
                <label>Agents (dans l'ordre d'exécution)</label>
                <div class="aos-n8n-agents" id="aos-n8n-agents"></div>
              </div>
              <div class="aos-form-group aos-mb">
                <label>Mission</label>
                <textarea id="n8n-message" class="aos-input" rows="3" style="resize:vertical"
                  placeholder="Décris la mission... Les réponses de chaque agent alimentent le suivant."></textarea>
              </div>
              <div class="aos-form-actions">
                <button class="aos-btn aos-btn-primary" id="n8n-run">▶ Orchestrer</button>
                <button class="aos-btn aos-btn-sm" id="n8n-add-agent">+ Agent</button>
                <span class="aos-msg" id="n8n-msg"></span>
              </div>
            </div>
          </div>

          <div class="aos-card">
            <div class="aos-card-header">
              <span class="aos-card-title">Résultats</span>
            </div>
            <div class="aos-card-body" id="aos-n8n-results">
              <div class="aos-empty-state">Aucune exécution</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  renderAgentCheckboxes();
  bindEvents();
  loadWorkflows();
  loadStatus();
}

// -- Sélection des agents -------------------------------------------------------

function renderAgentCheckboxes(): void {
  const el = document.getElementById("aos-n8n-agents");
  if (!el) return;
  const profiles = store.getState().profiles;
  el.innerHTML = profiles.map((p, i) => `
    <label class="aos-perm-chip ${i < 2 ? "aos-perm-chip-active" : ""}">
      <input type="checkbox" class="aos-n8n-agent-cb" value="${p.name}" ${i < 2 ? "checked" : ""}>
      ${p.emoji} ${p.name}
    </label>
  `).join("");

  el.querySelectorAll<HTMLInputElement>(".aos-n8n-agent-cb").forEach(cb => {
    cb.addEventListener("change", () => {
      const chip = cb.closest(".aos-perm-chip");
      chip?.classList.toggle("aos-perm-chip-active", cb.checked);
    });
  });
}

// -- Events ---------------------------------------------------------------------

function bindEvents(): void {
  document.getElementById("n8n-refresh")?.addEventListener("click", () => {
    loadWorkflows();
    loadStatus();
  });
  document.getElementById("n8n-run")?.addEventListener("click", runOrchestration);
  document.getElementById("n8n-add-agent")?.addEventListener("click", () => {
    const el = document.getElementById("aos-n8n-agents");
    if (!el) return;
    // Coche tous les agents
    el.querySelectorAll<HTMLInputElement>(".aos-n8n-agent-cb").forEach(cb => {
      cb.checked = true;
      cb.closest(".aos-perm-chip")?.classList.add("aos-perm-chip-active");
    });
  });
  store.subscribe(onStoreUpdate);
}

// -- Data -----------------------------------------------------------------------

async function loadStatus(): Promise<void> {
  try {
    const r = await fetch("/api/n8n/status");
    const d = await r.json();
    state.online = !!d.online;
  } catch {
    state.online = false;
  }
  const statusEl = document.getElementById("aos-n8n-status");
  if (statusEl) {
    statusEl.innerHTML = state.online
      ? `<span class="aos-status-dot online"><span class="aos-pulse"></span> n8n en ligne</span>`
      : `<span class="aos-status-dot" style="color:var(--aos-red)"><span class="aos-pulse"></span> n8n hors ligne</span>`;
  }
}

async function loadWorkflows(): Promise<void> {
  const el = document.getElementById("aos-n8n-workflows");
  if (!el) return;
  try {
    const r = await fetch("/api/n8n/workflows");
    const d = await r.json();
    state.workflows = d.workflows || [];
    state.online = !!d.online;
  } catch {
    state.workflows = [];
    state.online = false;
  }
  loadStatus();

  if (state.workflows.length === 0) {
    el.innerHTML = `<div class="aos-empty-state">Aucun workflow — créez-en un dans l'éditeur n8n</div>`;
    return;
  }
  el.innerHTML = state.workflows.map(w => `
    <div class="aos-n8n-wf ${state.selectedWorkflow === w.id ? "aos-n8n-wf-active" : ""}" data-wf-id="${w.id}">
      <div class="aos-n8n-wf-info">
        <div class="aos-n8n-wf-name">${esc(w.name)}</div>
        <div class="aos-n8n-wf-meta">
          <span class="aos-badge ${w.active ? "aos-badge-success" : ""}">${w.active ? "actif" : "inactif"}</span>
        </div>
      </div>
      <div class="aos-n8n-wf-actions">
        <button class="aos-btn aos-btn-sm aos-btn-primary" data-wf-run="${w.id}" title="Exécuter">▶</button>
        <button class="aos-btn aos-btn-sm" data-wf-exec="${w.id}" title="Voir les exécutions">📜</button>
      </div>
    </div>
  `).join("");

  el.querySelectorAll<HTMLButtonElement>("[data-wf-run]").forEach(btn => {
    btn.addEventListener("click", () => triggerWorkflow(btn.dataset.wfRun!));
  });
  el.querySelectorAll<HTMLButtonElement>("[data-wf-exec]").forEach(btn => {
    btn.addEventListener("click", () => selectWorkflow(btn.dataset.wfExec!));
  });
}

async function selectWorkflow(wfId: string): Promise<void> {
  state.selectedWorkflow = wfId;
  // Met en evidence la selection
  document.querySelectorAll(".aos-n8n-wf").forEach(el => {
    el.classList.toggle("aos-n8n-wf-active", (el as HTMLElement).dataset.wfId === wfId);
  });
  const el = document.getElementById("aos-n8n-executions");
  if (!el) return;
  el.innerHTML = `<div class="aos-empty-state">Chargement...</div>`;
  try {
    const r = await fetch(`/api/n8n/workflows/${wfId}/executions`);
    const d = await r.json();
    const execs: N8nExecution[] = d.executions || [];
    if (execs.length === 0) {
      el.innerHTML = `<div class="aos-empty-state">Aucune exécution</div>`;
      return;
    }
    el.innerHTML = execs.map(e => `
      <div class="aos-n8n-exec">
        <span class="aos-badge aos-badge-${e.status === "success" ? "success" : e.status === "error" ? "danger" : "admin"}">${e.status}</span>
        <span class="aos-n8n-exec-time">${new Date(e.started_at).toLocaleString("fr")}</span>
      </div>
    `).join("");
  } catch {
    el.innerHTML = `<div class="aos-empty-state">Erreur de chargement</div>`;
  }
}

async function triggerWorkflow(wfId: string): Promise<void> {
  const msg = document.getElementById("n8n-msg");
  try {
    const r = await fetch("/api/n8n/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow_id: wfId, payload: {} }),
    });
    const d = await r.json();
    if (msg) {
      msg.textContent = d.success ? "Workflow déclenché !" : d.error || "Erreur";
      msg.className = "aos-msg " + (d.success ? "aos-msg-success" : "aos-msg-error");
    }
    if (state.selectedWorkflow === wfId) selectWorkflow(wfId);
  } catch {
    if (msg) { msg.textContent = "Erreur réseau"; msg.className = "aos-msg aos-msg-error"; }
  }
}

async function runOrchestration(): Promise<void> {
  const message = (document.getElementById("n8n-message") as HTMLTextAreaElement)?.value.trim();
  const agents = Array.from(
    document.querySelectorAll<HTMLInputElement>(".aos-n8n-agent-cb:checked")
  ).map(cb => cb.value);
  const msg = document.getElementById("n8n-msg");
  const resultsEl = document.getElementById("aos-n8n-results");

  if (!message || agents.length === 0) {
    if (msg) { msg.textContent = "Mission et au moins un agent requis"; msg.className = "aos-msg aos-msg-error"; }
    return;
  }
  state.orchestrating = true;
  const btn = document.getElementById("n8n-run") as HTMLButtonElement;
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Orchestration..."; }
  if (resultsEl) resultsEl.innerHTML = `<div class="aos-empty-state">Exécution en cours...</div>`;

  try {
    const r = await fetch("/api/n8n/orchestrate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agents, message }),
    });
    const d = await r.json();
    state.results = d.results || [];
    if (resultsEl) {
      resultsEl.innerHTML = state.results.length === 0
        ? `<div class="aos-empty-state">${d.error || "Aucun résultat"}</div>`
        : state.results.map(res => `
          <div class="aos-n8n-result">
            <div class="aos-n8n-result-agent">${esc(res.agent)}</div>
            <div class="aos-n8n-result-text">${esc(res.response).slice(0, 600)}</div>
          </div>
        `).join("");
    }
  } catch (e) {
    if (resultsEl) resultsEl.innerHTML = `<div class="aos-empty-state">Erreur réseau</div>`;
  }
  state.orchestrating = false;
  if (btn) { btn.disabled = false; btn.textContent = "▶ Orchestrer"; }
}

// -- Store sync -----------------------------------------------------------------

function onStoreUpdate(): void {
  if (store.getState().activePanel !== "n8n") return;
  renderAgentCheckboxes();
}

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
